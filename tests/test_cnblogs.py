"""博客园 MetaWeblog Adapter 测试（mock XML-RPC 客户端，不打真实 API）。

覆盖：
- 发布成功 → remote_id / remote_url（§26 远程确认）
- 草稿 publish=False
- 凭据缺失 → 明确错误
- Worker 全链路：review=never + publish=automatic 自动发布（§64）
"""
from __future__ import annotations

import os
import tempfile

import pytest

# 在导入 publisher 前固定数据目录（与 test_api.py 相同模式，避免污染项目 data/）
os.environ.setdefault("PUBLISHER_DATA_DIR", tempfile.mkdtemp(prefix="publisher_cnblogs_"))

from publisher.models import Account  # noqa: E402
from publisher.platforms.base import PublishResult  # noqa: E402
from publisher.platforms.cnblogs import CnblogsAdapter  # noqa: E402
from publisher.security import decrypt_json, encrypt_json  # noqa: E402
from types import SimpleNamespace  # noqa: E402


class FakeXmlRpc:
    """模拟博客园 MetaWeblog 服务。"""

    def __init__(self):
        self.blogs = [{"blogid": "12345", "url": "https://www.cnblogs.com/tester/"}]
        self.posts: dict[str, dict] = {}
        self.next_id = 1001
        # 与真实 ServerProxy 一致的命名空间结构（blogger.* / metaWeblog.*）
        self.blogger = SimpleNamespace(getUsersBlogs=self.getUsersBlogs)
        self.metaWeblog = SimpleNamespace(
            newPost=self.newPost, getPost=self.getPost
        )

    def getUsersBlogs(self, *args):
        return self.blogs

    def newPost(self, blogid, username, password, post, publish):
        pid = str(self.next_id)
        self.next_id += 1
        self.posts[pid] = {"post": post, "publish": publish}
        return pid

    def getPost(self, postid, username, password):
        p = self.posts[postid]
        return {
            "postid": postid,
            "title": p["post"]["title"],
            "link": f"https://www.cnblogs.com/tester/p/{postid}.html",
        }


@pytest.fixture()
def adapter(monkeypatch):
    a = CnblogsAdapter()
    fake = FakeXmlRpc()
    monkeypatch.setattr(a, "_client", lambda blog_name: fake)
    a.fake = fake
    return a


def _account(creds: dict | None):
    return SimpleNamespace(
        encrypted_credentials=encrypt_json(creds) if creds else None
    )


CREDS = {"username": "tester", "token": "tok-xxx", "blog_name": "tester"}


@pytest.mark.asyncio
async def test_capabilities_api_mode(adapter):
    caps = await adapter.capabilities()
    assert caps["mode"] == "api"
    assert caps["supports_publish"] is True


@pytest.mark.asyncio
async def test_check_account_with_valid_creds(adapter):
    assert await adapter.check_account(_account(CREDS)) is True
    assert await adapter.check_account(_account(None)) is False


@pytest.mark.asyncio
async def test_publish_success_returns_remote_id_url(adapter):
    version = SimpleNamespace(title="Hello Cnblogs", content="# 正文\n内容", images="[]")
    result = await adapter.publish(version, account=_account(CREDS))

    assert isinstance(result, PublishResult)
    assert result.success is True
    assert result.remote_id == "1001"
    assert result.remote_url == "https://www.cnblogs.com/tester/p/1001.html"
    # newPost 必须以 publish=True 调用
    assert adapter.fake.posts["1001"]["publish"] is True
    assert adapter.fake.posts["1001"]["post"]["title"] == "Hello Cnblogs"


# ---- Markdown → HTML 转换（MetaWeblog description 按 HTML 渲染）----

def test_md_to_html_converts_markdown():
    from publisher.platforms.cnblogs import _md_to_html

    html = _md_to_html("# 标题\n\n- a\n- b")
    assert "<h1>标题</h1>" in html
    assert "<li>a</li>" in html


def test_md_to_html_keeps_html_passthrough():
    from publisher.platforms.cnblogs import _md_to_html

    raw = "<p>已是 HTML</p>"
    assert _md_to_html(raw) == raw


@pytest.mark.asyncio
async def test_publish_sends_html_description(adapter):
    """发布到博客园的 description 必须是渲染后的 HTML，不能是原始 Markdown。"""
    version = SimpleNamespace(
        title="md", content="# 标题\n\n- 项目一\n- 项目二", images="[]"
    )
    result = await adapter.publish(version, account=_account(CREDS))
    assert result.success is True
    desc = adapter.fake.posts[result.remote_id]["post"]["description"]
    assert "<h1>标题</h1>" in desc
    assert "- 项目一" not in desc  # 原始 md 列表语法不应残留


@pytest.mark.asyncio
async def test_create_draft_publishes_false(adapter):
    version = SimpleNamespace(title="Draft", content="draft body", images="[]")
    result = await adapter.create_draft(version, account=_account(CREDS))

    assert result.success is True
    assert adapter.fake.posts[result.remote_id]["publish"] is False


@pytest.mark.asyncio
async def test_publish_without_credentials_fails_cleanly(adapter):
    version = SimpleNamespace(title="t", content="c", images="[]")
    result = await adapter.publish(version, account=_account(None))

    assert result.success is False
    assert result.error_code == "account_credentials_missing"


@pytest.mark.asyncio
async def test_publish_rejects_empty_title(adapter):
    version = SimpleNamespace(title="  ", content="c", images="[]")
    result = await adapter.publish(version, account=_account(CREDS))

    assert result.success is False
    assert result.error_code == "content_invalid"


# ---- Worker 全链路（§64 全自动发布）----

@pytest.mark.asyncio
async def test_worker_auto_publish_flow(monkeypatch):
    from publisher.database import SessionLocal, init_db
    from publisher.services.account_service import AccountService
    from publisher.services.article_service import ArticleService
    from publisher.services.policy_service import PolicyService
    from publisher.services.publish_service import PublishService
    from publisher.workers import Worker
    from publisher.platforms.cnblogs import CnblogsAdapter

    init_db()
    fake = FakeXmlRpc()
    monkeypatch.setattr(CnblogsAdapter, "_client", lambda self, blog_name: fake)

    s = SessionLocal()
    try:
        # 文章层策略：never + automatic（作用于本文，不污染其他用例）
        article = ArticleService(s).create(title="cnblogs e2e", content="正常技术内容")
        ArticleService(s).mark_ready(article.id)
        PolicyService(s).set_policy(
            "article", article.id, review_mode="never", publish_mode="automatic"
        )

        account = AccountService(s).create(
            key="cnblogs_e2e", platform="cnblogs", credentials=CREDS
        )

        tasks = PublishService(s).create_tasks(
            article.id, ["cnblogs"], account_ids={"cnblogs": account.id}
        )
        assert len(tasks) == 1
        assert tasks[0].status == "queued"  # never + automatic → 直接排队

        processed = await Worker().run_once()
        assert processed == 1

        # Worker 在独立 session 中更新了任务，本会话需刷新后再读
        s.expire_all()
        task = PublishService(s).get_task(tasks[0].id)
        assert task.status == "success"
        assert task.remote_id == "1001"
        assert task.remote_url == "https://www.cnblogs.com/tester/p/1001.html"
        assert fake.posts["1001"]["publish"] is True

        # 凭据确认：数据库中不落明文（§53）
        raw = s.get(Account, account.id).encrypted_credentials
        assert "tok-xxx" not in (raw or "")
        assert decrypt_json(raw)["token"] == "tok-xxx"
    finally:
        s.close()
