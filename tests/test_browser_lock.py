"""账号浏览器并发锁测试（文档 §50、§21、§75-28）。

覆盖：
- browser 模式任务执行期间持有锁、结束后释放
- 锁被占用时 dequeue 跳过（队头不阻塞其它账号任务）
- waiting_* 持锁等待，cancel/超时释放
- api 模式（cnblogs）不占用浏览器锁
- platforms 表同步（platform 级策略与锁模式判断的数据基础）
- review_stale 事件去重（§21）
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

# 必须在导入 publisher 前固定数据目录，避免污染项目 data/
# （若同进程其它测试已先导入 publisher，engine 复用其临时目录，同样安全）
os.environ.setdefault("PUBLISHER_DATA_DIR", tempfile.mkdtemp(prefix="publisher_lock_test_"))

from publisher.database import SessionLocal, init_db  # noqa: E402
from publisher.models import (
    Account,
    Article,
    ArticleVersion,
    BrowserSession,
    Platform,
    PublishTask,
    Review,
)
from publisher.platforms import registry
from publisher.platforms.base import PlatformAdapter, PublishResult
from publisher.services.account_service import AccountService
from publisher.services.publish_service import PublishService, needs_browser_lock
from publisher.workers import Worker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecordingAdapter(PlatformAdapter):
    """browser 模式假 Adapter：记录执行时锁状态。"""

    platform = "fake_xhs"
    mode = "browser"
    lock_observed: bool | None = None

    async def capabilities(self):
        return {"platform": self.platform, "mode": self.mode}

    async def check_account(self, account):
        return True

    async def authorize(self, account):
        return True

    async def validate(self, content):
        return []

    async def create_draft(self, content, account=None, task_id=None):
        return PublishResult(success=True)

    async def publish(self, content, account=None, task_id=None):
        s = SessionLocal()
        try:
            bs = s.query(BrowserSession).filter_by(
                account_id=account.id, platform=self.platform
            ).one_or_none()
            type(self).lock_observed = bool(
                bs and bs.current_task_id == task_id
            )
        finally:
            s.close()
        return PublishResult(success=True, remote_id="r1", remote_url="https://x/1")

    async def get_status(self, remote_id):
        return {}

    async def cancel(self, task):
        return False


@pytest.fixture()
def db():
    init_db()
    s = SessionLocal()
    # 测试间共享同一临时 DB，逐用例清理（按外键依赖排序）
    for table in (
        "publish_logs", "reviews", "publish_tasks", "browser_sessions",
        "article_versions", "articles", "accounts",
    ):
        s.execute(text(f"DELETE FROM {table}"))
    s.commit()
    yield s
    s.close()


from sqlalchemy import text  # noqa: E402  (置于 fixture 后避免过早导入引擎)


def _mk_task(s, account_id: int, platform: str, version_id: int, article_id: int,
             status: str = "queued") -> PublishTask:
    t = PublishTask(
        article_id=article_id,
        article_version_id=version_id,
        platform=platform,
        account_id=account_id,
        review_policy="never",
        publish_policy="automatic",
        policy_floor_locked=False,
        status=status,
    )
    s.add(t)
    s.commit()
    return t


def _mk_article(s, n: int) -> tuple[int, int]:
    a = Article(title=f"t{n}", content="c", status="ready")
    s.add(a)
    s.flush()
    v = ArticleVersion(article_id=a.id, platform="fake_xhs", title=a.title, content=a.content, version=1)
    s.add(v)
    s.commit()
    return a.id, v.id


def _mk_account(s, n: int, platform: str = "fake_xhs") -> Account:
    acc = Account(key=f"acc{n}", platform=platform, name=f"acc{n}")
    s.add(acc)
    s.commit()
    return acc


def test_sync_platforms_populates_table(db):
    names = {p.name: p.mode for p in db.query(Platform).all()}
    assert names.get("cnblogs") == "api"
    assert names.get("xiaohongshu") == "browser"
    assert needs_browser_lock(db, "cnblogs") is False
    assert needs_browser_lock(db, "xiaohongshu") is True


async def test_worker_holds_and_releases_lock(db, monkeypatch):
    monkeypatch.setitem(registry._registry, "fake_xhs", RecordingAdapter)
    acc = _mk_account(db, 1)
    article_id, version_id = _mk_article(db, 1)
    task = _mk_task(db, acc.id, "fake_xhs", version_id, article_id)

    worker = Worker()
    processed = await worker.run_once()
    assert processed == 1
    db.expire_all()  # Worker 用独立 session 提交，刷新本地缓存
    assert task.status == "success"
    # 执行期间持有锁，结束后释放
    assert RecordingAdapter.lock_observed is True
    bs = db.query(BrowserSession).filter_by(account_id=acc.id).one()
    assert bs.current_task_id is None


async def test_locked_task_skipped_no_head_blocking(db, monkeypatch):
    """同账号锁被 waiting 任务占用 → 跳过它，其它账号任务正常调度。"""
    monkeypatch.setitem(registry._registry, "fake_xhs", RecordingAdapter)
    acc1 = _mk_account(db, 1)
    acc2 = _mk_account(db, 2)

    # 任务1：持锁等待人工（waiting_manual）
    a1, v1 = _mk_article(db, 1)
    t1 = _mk_task(db, acc1.id, "fake_xhs", v1, a1, status="waiting_manual")
    AccountService(db).try_lock(acc1.id, "fake_xhs", t1.id)

    # 任务2：同账号 queued，应被跳过
    a2, v2 = _mk_article(db, 2)
    t2 = _mk_task(db, acc1.id, "fake_xhs", v2, a2)

    # 任务3：另一账号 queued，应被处理
    a3, v3 = _mk_article(db, 3)
    t3 = _mk_task(db, acc2.id, "fake_xhs", v3, a3)

    worker = Worker()
    processed = await worker.run_once()
    assert processed == 1
    db.expire_all()
    assert t2.status == "queued"          # 被锁阻塞，保持 queued
    assert t3.status == "success"         # 未被队头阻塞
    # 任务1 的锁仍被持有（等待人工，超时才释放）
    bs = db.query(BrowserSession).filter_by(account_id=acc1.id).one()
    assert bs.current_task_id == t1.id


async def test_failed_task_releases_lock(db, monkeypatch):
    class FailingAdapter(RecordingAdapter):
        async def publish(self, content, account=None, task_id=None):
            return PublishResult(success=False, error_code="boom", error_message="boom")

    monkeypatch.setitem(registry._registry, "fake_xhs", FailingAdapter)
    acc = _mk_account(db, 1)
    a, v = _mk_article(db, 1)
    task = _mk_task(db, acc.id, "fake_xhs", v, a)

    worker = Worker()
    await worker.run_once()
    db.expire_all()
    assert task.status == "queued"  # 进入重试
    bs = db.query(BrowserSession).filter_by(account_id=acc.id).one()
    assert bs.current_task_id is None  # 重试间隙锁已释放


async def test_api_platform_never_locks(db, monkeypatch):
    class ApiAdapter(RecordingAdapter):
        platform = "fake_cnblogs"
        mode = "api"
        lock_observed = None

    monkeypatch.setitem(registry._registry, "fake_cnblogs", ApiAdapter)
    acc = _mk_account(db, 1, platform="fake_cnblogs")
    a, v = _mk_article(db, 1)
    _mk_task(db, acc.id, "fake_cnblogs", v, a)

    assert needs_browser_lock(db, "fake_cnblogs") is False
    worker = Worker()
    processed = await worker.run_once()
    assert processed == 1
    # api 模式不产生浏览器锁记录
    assert db.query(BrowserSession).filter_by(account_id=acc.id).count() == 0


def test_cancel_releases_lock(db):
    acc = _mk_account(db, 1)
    a, v = _mk_article(db, 1)
    task = _mk_task(db, acc.id, "fake_xhs", v, a, status="waiting_manual")
    AccountService(db).try_lock(acc.id, "fake_xhs", task.id)

    PublishService(db).cancel(task.id)
    bs = db.query(BrowserSession).filter_by(account_id=acc.id).one()
    assert bs.current_task_id is None


def test_stale_review_notified_once(db):
    acc = _mk_account(db, 1)
    a, v = _mk_article(db, 1)
    task = _mk_task(db, acc.id, "fake_xhs", v, a, status="waiting_review")
    review = Review(
        task_id=task.id,
        article_version_id=v,
        status="pending",
        reviewer="test",
    )
    review.created_at = _utcnow() - timedelta(days=4)
    db.add(review)
    db.commit()

    from publisher.events import event_bus

    worker = Worker()
    q = event_bus.subscribe("*")
    try:
        worker.process_stale_reviews(db)
        worker.process_stale_reviews(db)
        events = []
        while not q.empty():
            events.append(q.get_nowait()["event"])
        assert events.count("task.review_stale") == 1
    finally:
        event_bus.unsubscribe("*", q)
