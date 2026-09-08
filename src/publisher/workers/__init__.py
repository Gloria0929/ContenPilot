"""异步任务 Worker（文档第 28、29、21 节）。

从队列取 pending/queued 任务，通过 Platform Adapter 执行发布，
处理重试、超时、账号锁、等待类状态的超时释放。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..events import emitter
from ..models import (
    Account,
    PublishTask,
    TaskStatus,
)
from ..platforms.registry import get_adapter, import_platforms
from ..services.account_service import AccountService
from ..services.log_service import LogService
from ..services.publish_service import PublishService, needs_browser_lock

logger = logging.getLogger("publisher.worker")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite 的 DateTime(timezone=True) 读回是 naive，统一按 UTC 补齐再比较。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Worker:
    def __init__(self):
        import_platforms()
        # review_stale 已通知去重：避免每轮轮询对同一批超期审核重复发事件（§21）
        self._stale_notified: set[int] = set()
        self._recover_orphans()

    def _recover_orphans(self) -> None:
        """启动时回收孤儿任务（§73-10：进程重启/崩溃不能让任务卡死）。

        历史上 Worker 崩溃可能把任务遗留在 processing —— 单 Worker 模式下
        启动时刻不可能有正在执行的任务，全部复位回 queued。
        """
        session = SessionLocal()
        try:
            orphans = session.scalars(
                select(PublishTask).where(PublishTask.status == TaskStatus.processing.value)
            ).all()
            for t in orphans:
                t.status = TaskStatus.queued.value
                logger.warning("recovered orphan task #%s -> queued", t.id)
            if orphans:
                session.commit()
        finally:
            session.close()

    def _dequeue(self, session: Session) -> PublishTask | None:
        """取下一个可执行任务。

        跳过账号浏览器锁被其它任务占用的任务，避免队头阻塞
        （§50：同账号任务保持 queued，不影响其它账号的任务被调度）。
        """
        accounts = AccountService(session)
        tasks = session.scalars(
            select(PublishTask)
            .where(PublishTask.status == TaskStatus.queued.value)
            .order_by(PublishTask.id)
        )
        for task in tasks:
            if (
                task.account_id
                and needs_browser_lock(session, task.platform)
                and self._lock_held(session, accounts, task)
            ):
                continue
            task.status = TaskStatus.processing.value
            task.started_at = _utcnow()
            session.commit()
            return task
        return None

    @staticmethod
    def _lock_held(session: Session, accounts: AccountService, task: PublishTask) -> bool:
        s = accounts.get_session(task.account_id, task.platform)
        return bool(s and s.current_task_id not in (None, task.id))

    async def run_once(self) -> int:
        """处理一个任务，返回处理的任务数。"""
        session = SessionLocal()
        try:
            task = self._dequeue(session)
            if not task:
                return 0
            await self._process(session, task)
            return 1
        finally:
            session.close()

    async def _process(self, session: Session, task: PublishTask) -> None:
        logs = LogService(session)
        accounts = AccountService(session)
        publish = PublishService(session)

        # 最终权限检查（文档第 63 节）
        ok, reason = publish.pre_publish_check(task)
        if not ok:
            if reason == "review_version_mismatch":
                # 版本不一致 → 打回 waiting_review 重新审核（§35/§65）
                task.status = TaskStatus.waiting_review.value
                task.error_code = "review_version_mismatch"
                task.error_message = "内容已更新，需重新审核后发布"
                session.commit()
                logs.log(
                    "waiting_review", task.id, level="warning",
                    message="内容已更新，需重新审核后发布",
                )
                emitter.task_status(task.id, TaskStatus.waiting_review.value)
                return
            task.status = TaskStatus.blocked.value
            task.error_code = "pre_publish_check_failed"
            task.error_message = reason
            task.finished_at = _utcnow()
            session.commit()
            logs.log("publish_failed", task.id, level="error", message=f"发布失败：{reason}")
            emitter.task_status(task.id, TaskStatus.blocked.value)
            return

        # 频率校验（§54）
        if task.account_id:
            account = accounts.get(task.account_id)
            try:
                allowed, freq_reason = accounts.check_publish_allowed(account)
            except Exception:  # noqa: BLE001 —— 校验异常不能让任务卡死在 processing
                logger.exception("check_publish_allowed error")
                allowed, freq_reason = True, ""
            if not allowed:
                task.status = TaskStatus.queued.value  # 稍后重试
                session.commit()
                logger.info("deferred: %s", freq_reason)
                return

        # 账号浏览器并发锁：browser/manual 模式执行前必须持有（§50、§75-28）
        if task.account_id and needs_browser_lock(session, task.platform):
            if not accounts.try_lock(task.account_id, task.platform, task.id):
                task.status = TaskStatus.queued.value  # 被并发抢占，稍后再试
                session.commit()
                logger.info("deferred: account browser session locked, task %s", task.id)
                return

        # 执行发布
        try:
            adapter = get_adapter(task.platform)
            if adapter is None:
                raise RuntimeError(f"no adapter for {task.platform}")

            from ..models import ArticleVersion

            version = session.get(ArticleVersion, task.article_version_id)
            account = (
                session.get(Account, task.account_id) if task.account_id else None
            )

            result = await adapter.publish(version, account=account, task_id=task.id)
            self._handle_result(session, task, result, logs, accounts)
        except Exception as exc:  # noqa: BLE001
            logger.exception("publish error")
            task.status = TaskStatus.failed.value
            task.error_code = "exception"
            task.error_message = str(exc)
            task.finished_at = _utcnow()
            session.commit()
            logs.log("publish_failed", task.id, level="error", message=f"发布异常：{exc}")
            emitter.task_status(task.id, TaskStatus.failed.value)
            self._release_lock(session, accounts, task)

    @staticmethod
    def _release_lock(session: Session, accounts: AccountService, task: PublishTask) -> None:
        """任务离开执行/等待态时释放账号浏览器锁（§50）。"""
        if task.account_id:
            accounts.unlock(task.account_id, task.platform, task.id)

    def _handle_result(self, session, task, result, logs, accounts):
        if result.success:
            task.status = TaskStatus.success.value
            task.remote_id = result.remote_id
            task.remote_url = result.remote_url
            task.finished_at = _utcnow()
            session.commit()
            logs.log("publish_success", task.id, message=f"发布链接：{task.remote_url}" if task.remote_url else "发布成功")
            if task.account_id:
                accounts.mark_published(accounts.get(task.account_id))
            emitter.task_status(task.id, TaskStatus.success.value)
            self._release_lock(session, accounts, task)
        elif result.needs_auth:
            # waiting_auth 持锁等待人工授权，超时由 process_timeouts 释放（§21/§50）
            task.status = TaskStatus.waiting_auth.value
            task.timeout_at = _utcnow() + timedelta(seconds=settings.waiting_auth_timeout)
            session.commit()
            logs.log("waiting_auth", task.id, level="warning", message="登录态缺失或已失效，等待重新授权")
            emitter.task_status(task.id, TaskStatus.waiting_auth.value)
        elif result.needs_manual:
            # waiting_manual 持锁等待人工接管，超时由 process_timeouts 释放（§21/§50）
            task.status = TaskStatus.waiting_manual.value
            task.timeout_at = _utcnow() + timedelta(seconds=settings.waiting_manual_timeout)
            session.commit()
            logs.log("waiting_manual", task.id, level="warning", message=result.error_message or "需要人工接管处理")
            if task.account_id:
                accounts.mark_blocked(accounts.get(task.account_id))
            emitter.task_status(task.id, TaskStatus.waiting_manual.value)
        elif getattr(result, "unconfirmed", False):
            # 已点击发布但无法确认结果 → blocked，禁止自动重试，防止重复发布（§26）
            task.status = TaskStatus.blocked.value
            task.error_code = result.error_code or "publish_unconfirmed"
            task.error_message = result.error_message
            task.finished_at = _utcnow()
            session.commit()
            logs.log("publish_unconfirmed", task.id, level="warning", message=result.error_message or "")
            emitter.task_status(task.id, TaskStatus.blocked.value)
            self._release_lock(session, accounts, task)
        else:
            # 失败 → 重试或终结
            task.attempt += 1
            if task.attempt < task.max_attempts:
                task.status = TaskStatus.queued.value
                session.commit()
                logs.log("task_retry", task.id, level="warning", message=f"发布失败将自动重试：{result.error_message or '未知原因'}")
                emitter.task_status(task.id, TaskStatus.queued.value)
            else:
                task.status = TaskStatus.failed.value
                task.error_code = result.error_code
                task.error_message = result.error_message
                task.finished_at = _utcnow()
                session.commit()
                logs.log("publish_failed", task.id, level="error", message=f"发布失败：{result.error_message or '未知原因'}")
                emitter.task_status(task.id, TaskStatus.failed.value)
            self._release_lock(session, accounts, task)

    # ---- 超时处理 ----

    def process_timeouts(self, session: Session) -> None:
        now = _utcnow()
        for task in session.scalars(
            select(PublishTask).where(
                PublishTask.status.in_(
                    [TaskStatus.waiting_auth.value, TaskStatus.waiting_manual.value]
                ),
                PublishTask.timeout_at.is_not(None),
            )
        ):
            if _aware(task.timeout_at) <= now:
                task.status = TaskStatus.timeout.value
                task.finished_at = now
                session.commit()
                # 释放账号锁
                if task.account_id:
                    AccountService(session).unlock(
                        task.account_id, task.platform, task.id
                    )
                emitter.timeout(task.id)
                LogService(session).log("task.timeout", task.id, level="warning")

    def process_stale_reviews(self, session: Session) -> None:
        """review_stale 事件：超过 N 天未处理，每条只发一次（文档第 21 节）。"""
        from ..models import Review, ReviewStatus

        cutoff = _utcnow() - timedelta(days=settings.review_stale_days)
        for review in session.scalars(
            select(Review).where(Review.status == ReviewStatus.pending.value)
        ):
            if _aware(review.created_at) <= cutoff and review.id not in self._stale_notified:
                self._stale_notified.add(review.id)
                emitter.review_stale(review.id, review.task_id)


async def run_worker_loop() -> None:
    worker = Worker()
    logger.info("worker started")
    while True:
        try:
            processed = await worker.run_once()
            session = SessionLocal()
            try:
                worker.process_timeouts(session)
                worker.process_stale_reviews(session)
            finally:
                session.close()
            if processed == 0:
                await asyncio.sleep(settings.worker_poll_interval)
        except asyncio.CancelledError:
            logger.info("worker cancelled")
            break
        except Exception:  # noqa: BLE001
            logger.exception("worker loop error")
            await asyncio.sleep(1.0)
