"""API 鉴权 + 发布流程集成测试（使用 TestClient，确定性无进程竞态）。

覆盖文档 §52（鉴权）、§2.6（下限）、§30（幂等）关键验收点。
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# 在导入 app 前固定数据目录，避免污染项目 data/
_tmp = tempfile.mkdtemp(prefix="publisher_test_")
os.environ["PUBLISHER_DATA_DIR"] = _tmp
os.environ["PUBLISHER_ADMIN_PASSWORD"] = "secret123"
os.environ["PUBLISHER_SESSION_SECRET"] = "test-secret"

from publisher.api.app import app  # noqa: E402
from publisher.auth import session_store  # noqa: E402


@pytest.fixture()
def client():
    # 每个测试前清空会话，避免跨测试污染
    session_store._sessions.clear()
    with TestClient(app) as c:
        yield c


def _login(client) -> None:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200


def test_unauthorized_requires_login(client):
    r = client.get("/api/articles")
    assert r.status_code == 401


def test_login_and_access(client):
    _login(client)
    r = client.get("/api/auth/whoami")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    assert r.status_code == 401


def test_video_render_maps_browser_loopback_to_compose_service(client, monkeypatch):
    """浏览器填写 localhost 时，容器后端应使用 Compose 内部 API 地址。"""
    from publisher.pipeline import MoneyPrinterTurboClient

    requested_urls: list[str] = []

    async def fake_create_video_task(self, **kwargs):
        requested_urls.append(self.base_url)
        return {"status": 200, "data": {"task_id": "task-123"}}

    monkeypatch.setenv(
        "MONEYPRINTERTURBO_URL", "http://moneyprinterturbo:8081"
    )
    monkeypatch.setattr(
        MoneyPrinterTurboClient, "create_video_task", fake_create_video_task
    )
    _login(client)

    response = client.post(
        "/api/pipeline/video/render",
        json={
            "video_script": "测试文案",
            "video_subject": "测试主题",
            "money_printer_url": "http://localhost:8081",
        },
    )

    assert response.status_code == 200
    assert requested_urls == ["http://moneyprinterturbo:8081"]


def test_video_render_maps_old_service_name_to_host_service(client, monkeypatch):
    """浏览器残留的 Compose 服务名应映射到服务器宿主机配置。"""
    from publisher.pipeline import MoneyPrinterTurboClient

    requested_urls: list[str] = []

    async def fake_create_video_task(self, **kwargs):
        requested_urls.append(self.base_url)
        return {"status": 200, "data": {"task_id": "task-host"}}

    monkeypatch.setenv(
        "MONEYPRINTERTURBO_URL", "http://192.168.3.100:8081"
    )
    monkeypatch.setattr(
        MoneyPrinterTurboClient, "create_video_task", fake_create_video_task
    )
    _login(client)

    response = client.post(
        "/api/pipeline/video/render",
        json={
            "video_script": "测试文案",
            "video_subject": "测试主题",
            "money_printer_url": "http://moneyprinterturbo:8081",
        },
    )

    assert response.status_code == 200
    assert requested_urls == ["http://192.168.3.100:8081"]


def test_video_task_status_and_authenticated_download(client, monkeypatch, tmp_path):
    """完成任务应返回共享存储中的安全下载链接。"""
    from publisher.pipeline import MoneyPrinterTurboClient

    task_id = "2f629337-0db4-46d2-90a3-a911943d9016"
    storage = tmp_path / "moneyprinterturbo"
    output_dir = storage / "tasks" / task_id / "output"
    output_dir.mkdir(parents=True)
    video_file = output_dir / "final-1.mp4"
    video_file.write_bytes(b"test-video")

    async def fake_get_video_task(self, requested_task_id):
        assert requested_task_id == task_id
        return {
            "status": 200,
            "data": {
                "task_id": task_id,
                "state": 1,
                "progress": 100,
                "videos": [f"/tasks/{task_id}/output/final-1.mp4"],
            },
        }

    monkeypatch.setenv("MONEYPRINTERTURBO_STORAGE_DIR", str(storage))
    monkeypatch.setattr(
        MoneyPrinterTurboClient, "get_video_task", fake_get_video_task
    )
    _login(client)

    status_response = client.get(f"/api/pipeline/video/tasks/{task_id}")

    assert status_response.status_code == 200
    task = status_response.json()
    assert task["status"] == "completed"
    assert task["download_ready"] is True
    assert task["outputs"][0]["name"] == "final-1.mp4"

    download_response = client.get(task["outputs"][0]["download_url"])
    assert download_response.status_code == 200
    assert download_response.content == b"test-video"
    assert "final-1.mp4" in download_response.headers["content-disposition"]


def test_video_download_rejects_path_traversal(client, monkeypatch, tmp_path):
    task_id = "2f629337-0db4-46d2-90a3-a911943d9016"
    storage = tmp_path / "moneyprinterturbo"
    (storage / "tasks" / task_id).mkdir(parents=True)
    monkeypatch.setenv("MONEYPRINTERTURBO_STORAGE_DIR", str(storage))
    _login(client)

    response = client.get(
        f"/api/pipeline/video/tasks/{task_id}/download",
        params={"file": "../../outside.mp4"},
    )

    assert response.status_code == 403


def test_video_task_list_recovers_completed_files_when_upstream_is_unavailable(
    client, monkeypatch, tmp_path
):
    """MPT 重启丢失内存任务后，仍应从共享卷恢复已完成成片。"""
    from publisher.pipeline import MoneyPrinterTurboClient

    task_id = "2f629337-0db4-46d2-90a3-a911943d9016"
    storage = tmp_path / "moneyprinterturbo"
    output_dir = storage / "tasks" / task_id / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "final-1.mp4").write_bytes(b"recovered-video")

    async def fake_list_video_tasks(self, page=1, page_size=20):
        return {"error": "MoneyPrinterTurbo service unreachable"}

    monkeypatch.setenv("MONEYPRINTERTURBO_STORAGE_DIR", str(storage))
    monkeypatch.setattr(
        MoneyPrinterTurboClient, "list_video_tasks", fake_list_video_tasks
    )
    _login(client)

    response = client.get("/api/pipeline/video/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["upstream_available"] is False
    assert body["tasks"][0]["task_id"] == task_id
    assert body["tasks"][0]["download_ready"] is True


def test_full_publish_flow_with_floor(client):
    _login(client)
    # 创建文章
    r = client.post("/api/articles", json={"title": "t", "content": "c"})
    assert r.status_code == 200
    aid = r.json()["id"]
    client.patch(f"/api/articles/{aid}", json={"status": "ready"})

    # 创建账号
    r = client.post("/api/accounts", json={"key": "jj", "platform": "juejin", "name": "官方"})
    acc = r.json()["id"]

    # 设置 account 层 floor (always + is_floor)
    r = client.post("/api/policies", json={
        "scope_type": "account", "scope_id": acc,
        "review_mode": "always", "publish_mode": "automatic", "is_floor": True,
    })
    assert r.status_code == 200

    # 解析：应 always + floor_locked
    r = client.get(f"/api/policies/resolve", params={"account_id": acc, "article_id": aid})
    assert r.status_code == 200
    assert r.json()["review_policy"] == "always"
    assert r.json()["is_floor_locked"] is True

    # 发布：应创建 waiting_review 任务
    r = client.post("/api/publish", json={
        "article_id": aid, "platforms": ["juejin"],
        "account_ids": {"juejin": acc},
    })
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) == 1
    assert tasks[0]["review_policy"] == "always"
    assert tasks[0]["status"] == "waiting_review"
    assert tasks[0]["policy_floor_locked"] is True


def test_publish_idempotent_non_terminal(client):
    """同一组合非终态任务只创建一次（文档 §30）。"""
    _login(client)
    r = client.post("/api/articles", json={"title": "t", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/api/articles/{aid}", json={"status": "ready"})
    r = client.post("/api/accounts", json={"key": "a1", "platform": "juejin"})
    acc = r.json()["id"]

    p1 = client.post("/api/publish", json={
        "article_id": aid, "platforms": ["juejin"], "account_ids": {"juejin": acc},
    })
    p2 = client.post("/api/publish", json={
        "article_id": aid, "platforms": ["juejin"], "account_ids": {"juejin": acc},
    })
    t1 = [t["id"] for t in p1.json()]
    t2 = [t["id"] for t in p2.json()]
    assert t1 == t2  # 第二次复用同一任务


def test_article_delete(client):
    """无关联任务的文章可删除；已关联发布任务的拒绝删除（保留历史归因）。"""
    _login(client)
    aid = client.post("/api/articles", json={"title": "del", "content": "c"}).json()["id"]
    assert client.delete(f"/api/articles/{aid}").status_code == 200
    assert client.get(f"/api/articles/{aid}").status_code == 404

    aid2 = client.post("/api/articles", json={"title": "keep", "content": "c"}).json()["id"]
    client.patch(f"/api/articles/{aid2}", json={"status": "ready"})
    acc = client.post(
        "/api/accounts", json={"key": "del-acc", "platform": "juejin"}
    ).json()["id"]
    client.post("/api/publish", json={
        "article_id": aid2, "platforms": ["juejin"],
        "account_ids": {"juejin": acc},
    })
    assert client.delete(f"/api/articles/{aid2}").status_code == 400


def test_article_delete_with_versions(client):
    """删除带版本的文章（曾因 ORM flush 顺序触发外键 500）。"""
    _login(client)
    aid = client.post("/api/articles", json={"title": "ver", "content": "c"}).json()["id"]
    from publisher.database import SessionLocal
    from publisher.services.article_service import ArticleService

    s = SessionLocal()
    try:
        ArticleService(s).create_version(aid, "cnblogs", "t", "c")
    finally:
        s.close()
    assert client.delete(f"/api/articles/{aid}").status_code == 200
    assert client.get(f"/api/articles/{aid}").status_code == 404


def test_account_delete_with_browser_session(client):
    """删除带残留浏览器会话的账号（曾因 ORM flush 顺序触发外键 500）。"""
    _login(client)
    acc = client.post(
        "/api/accounts", json={"key": "bs-acc", "platform": "cnblogs"}
    ).json()["id"]
    from publisher.database import SessionLocal
    from publisher.models import BrowserSession

    s = SessionLocal()
    try:
        s.add(BrowserSession(account_id=acc, platform="juejin", status="idle"))
        s.commit()
    finally:
        s.close()
    assert client.delete(f"/api/accounts/{acc}").status_code == 200
    assert client.get(f"/api/accounts/{acc}").status_code == 404


def test_task_delete(client):
    """终态任务可删除（连带 Review/日志）；非终态任务拒绝删除。"""
    _login(client)
    r = client.post("/api/articles", json={"title": "td", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/api/articles/{aid}", json={"status": "ready"})
    acc = client.post(
        "/api/accounts", json={"key": "td-acc", "platform": "juejin"}
    ).json()["id"]
    tid = client.post("/api/publish", json={
        "article_id": aid, "platforms": ["juejin"],
        "account_ids": {"juejin": acc},
    }).json()[0]["id"]

    # 非终态：拒绝
    assert client.delete(f"/api/tasks/{tid}").status_code == 400
    # 取消 → 终态：可删
    client.post(f"/api/tasks/{tid}/cancel")
    assert client.delete(f"/api/tasks/{tid}").status_code == 200
    assert client.get(f"/api/tasks/{tid}").status_code == 404
    assert client.delete(f"/api/tasks/{tid}").status_code == 404


def test_ai_cannot_relax_floor_locked(client):
    """普通 API Key（无 override 权限）不能把 floor-locked always 调松。"""
    _login(client)
    r = client.post("/api/articles", json={"title": "t", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/api/articles/{aid}", json={"status": "ready"})
    r = client.post("/api/accounts", json={"key": "jj2", "platform": "juejin"})
    acc = r.json()["id"]
    client.post("/api/policies", json={
        "scope_type": "account", "scope_id": acc,
        "review_mode": "always", "publish_mode": "automatic", "is_floor": True,
    })

    # 创建无 override 权限的 API Key
    r = client.post("/api/auth/api_keys", json={"name": "nooverride", "allow_override_review": False})
    key = f'{r.json()["access_key"]}:{r.json()["secret_key"]}'

    # 用「纯 API Key」（无 session cookie，模拟 AI Skill）尝试 review_override=never，
    # 应被 403 拒绝——session 优先于 API Key，故必须新建不带 cookie 的 client。
    with TestClient(app) as ai_client:  # 不登录，无 session cookie
        r = ai_client.post("/api/publish", headers={"Authorization": f"Bearer {key}"}, json={
            "article_id": aid, "platforms": ["juejin"],
            "account_ids": {"juejin": acc}, "review_override": "never",
        })
    assert r.status_code == 403
