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
    r = client.post("/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200


def test_unauthorized_requires_login(client):
    r = client.get("/articles")
    assert r.status_code == 401


def test_login_and_access(client):
    _login(client)
    r = client.get("/auth/whoami")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_wrong_password_rejected(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "bad"})
    assert r.status_code == 401


def test_full_publish_flow_with_floor(client):
    _login(client)
    # 创建文章
    r = client.post("/articles", json={"title": "t", "content": "c"})
    assert r.status_code == 200
    aid = r.json()["id"]
    client.patch(f"/articles/{aid}", json={"status": "ready"})

    # 创建账号
    r = client.post("/accounts", json={"key": "xhs", "platform": "xiaohongshu", "name": "官方"})
    acc = r.json()["id"]

    # 设置 account 层 floor (always + is_floor)
    r = client.post("/policies", json={
        "scope_type": "account", "scope_id": acc,
        "review_mode": "always", "publish_mode": "automatic", "is_floor": True,
    })
    assert r.status_code == 200

    # 解析：应 always + floor_locked
    r = client.get(f"/policies/resolve", params={"account_id": acc, "article_id": aid})
    assert r.status_code == 200
    assert r.json()["review_policy"] == "always"
    assert r.json()["is_floor_locked"] is True

    # 发布：应创建 waiting_review 任务
    r = client.post("/publish", json={
        "article_id": aid, "platforms": ["xiaohongshu"],
        "account_ids": {"xiaohongshu": acc},
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
    r = client.post("/articles", json={"title": "t", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/articles/{aid}", json={"status": "ready"})
    r = client.post("/accounts", json={"key": "a1", "platform": "juejin"})
    acc = r.json()["id"]

    p1 = client.post("/publish", json={
        "article_id": aid, "platforms": ["juejin"], "account_ids": {"juejin": acc},
    })
    p2 = client.post("/publish", json={
        "article_id": aid, "platforms": ["juejin"], "account_ids": {"juejin": acc},
    })
    t1 = [t["id"] for t in p1.json()]
    t2 = [t["id"] for t in p2.json()]
    assert t1 == t2  # 第二次复用同一任务


def test_article_delete(client):
    """无关联任务的文章可删除；已关联发布任务的拒绝删除（保留历史归因）。"""
    _login(client)
    aid = client.post("/articles", json={"title": "del", "content": "c"}).json()["id"]
    assert client.delete(f"/articles/{aid}").status_code == 200
    assert client.get(f"/articles/{aid}").status_code == 404

    aid2 = client.post("/articles", json={"title": "keep", "content": "c"}).json()["id"]
    client.patch(f"/articles/{aid2}", json={"status": "ready"})
    acc = client.post(
        "/accounts", json={"key": "del-acc", "platform": "juejin"}
    ).json()["id"]
    client.post("/publish", json={
        "article_id": aid2, "platforms": ["juejin"],
        "account_ids": {"juejin": acc},
    })
    assert client.delete(f"/articles/{aid2}").status_code == 400


def test_article_delete_with_versions(client):
    """删除带版本的文章（曾因 ORM flush 顺序触发外键 500）。"""
    _login(client)
    aid = client.post("/articles", json={"title": "ver", "content": "c"}).json()["id"]
    from publisher.database import SessionLocal
    from publisher.services.article_service import ArticleService

    s = SessionLocal()
    try:
        ArticleService(s).create_version(aid, "cnblogs", "t", "c")
    finally:
        s.close()
    assert client.delete(f"/articles/{aid}").status_code == 200
    assert client.get(f"/articles/{aid}").status_code == 404


def test_account_delete_with_browser_session(client):
    """删除带残留浏览器会话的账号（曾因 ORM flush 顺序触发外键 500）。"""
    _login(client)
    acc = client.post(
        "/accounts", json={"key": "bs-acc", "platform": "cnblogs"}
    ).json()["id"]
    from publisher.database import SessionLocal
    from publisher.models import BrowserSession

    s = SessionLocal()
    try:
        s.add(BrowserSession(account_id=acc, platform="xiaohongshu", status="idle"))
        s.commit()
    finally:
        s.close()
    assert client.delete(f"/accounts/{acc}").status_code == 200
    assert client.get(f"/accounts/{acc}").status_code == 404


def test_task_delete(client):
    """终态任务可删除（连带 Review/日志）；非终态任务拒绝删除。"""
    _login(client)
    r = client.post("/articles", json={"title": "td", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/articles/{aid}", json={"status": "ready"})
    acc = client.post(
        "/accounts", json={"key": "td-acc", "platform": "juejin"}
    ).json()["id"]
    tid = client.post("/publish", json={
        "article_id": aid, "platforms": ["juejin"],
        "account_ids": {"juejin": acc},
    }).json()[0]["id"]

    # 非终态：拒绝
    assert client.delete(f"/tasks/{tid}").status_code == 400
    # 取消 → 终态：可删
    client.post(f"/tasks/{tid}/cancel")
    assert client.delete(f"/tasks/{tid}").status_code == 200
    assert client.get(f"/tasks/{tid}").status_code == 404
    assert client.delete(f"/tasks/{tid}").status_code == 404


def test_ai_cannot_relax_floor_locked(client):
    """普通 API Key（无 override 权限）不能把 floor-locked always 调松。"""
    _login(client)
    r = client.post("/articles", json={"title": "t", "content": "c"})
    aid = r.json()["id"]
    client.patch(f"/articles/{aid}", json={"status": "ready"})
    r = client.post("/accounts", json={"key": "xhs2", "platform": "xiaohongshu"})
    acc = r.json()["id"]
    client.post("/policies", json={
        "scope_type": "account", "scope_id": acc,
        "review_mode": "always", "publish_mode": "automatic", "is_floor": True,
    })

    # 创建无 override 权限的 API Key
    r = client.post("/auth/api_keys", params={"name": "nooverride", "allow_override_review": False})
    key = r.json()["key"]

    # 用「纯 API Key」（无 session cookie，模拟 AI Skill）尝试 review_override=never，
    # 应被 403 拒绝——session 优先于 API Key，故必须新建不带 cookie 的 client。
    with TestClient(app) as ai_client:  # 不登录，无 session cookie
        r = ai_client.post("/publish", headers={"Authorization": f"Bearer {key}"}, json={
            "article_id": aid, "platforms": ["xiaohongshu"],
            "account_ids": {"xiaohongshu": acc}, "review_override": "never",
        })
    assert r.status_code == 403