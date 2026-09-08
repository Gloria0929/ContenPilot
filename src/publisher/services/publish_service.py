"""发布任务核心服务：PublishTask 创建、调度、最终权限检查。

这是 Publisher Core 的中心。文档第 19、63 节的流程都在这里落地。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..events import emitter
from ..models import (
    Article,
    ArticleStatus,
    AccountStatus,
    Platform,
    PublishTask,
    Review,
    ReviewMode,
    ReviewStatus,
    TaskStatus,
    TASK_TERMINAL_STATES,
)
from .account_service import AccountService
from .article_service import ArticleService
from .content_safety import check_content_safety
from .log_service import LogService
from .policy_service import PolicyService
from .review_service import ReviewService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def platform_mode(session: Session, platform_name: str) -> str:
    """平台发布模式：优先 platforms 表，未注册时回退 Adapter 注册表。"""
    from ..platforms.registry import adapter_mode

    row = session.scalar(select(Platform).where(Platform.name == platform_name))
    return row.mode if row else adapter_mode(platform_name)


def needs_browser_lock(session: Session, platform_name: str) -> bool:
    """该平台任务是否需要持有账号浏览器锁（§50：browser/manual 模式）。"""
    return platform_mode(session, platform_name) in ("browser", "manual")


# §27 聚合规则：任一 waiting_* → processing；有败有成 → partial_success；
# 全败 → failed；全成 → published；无任务 → none。只读视图，不落库。
_WAITING_STATUSES = {
    TaskStatus.waiting_review.value,
    TaskStatus.waiting_auth.value,
    TaskStatus.waiting_manual.value,
    TaskStatus.processing.value,
    TaskStatus.queued.value,
    TaskStatus.pending.value,
}


def _aggregate_status(task_statuses: list[str]) -> str:
    if not task_statuses:
        return "none"
    if any(s in _WAITING_STATUSES for s in task_statuses):
        return "processing"
    has_success = TaskStatus.success.value in task_statuses
    has_failed = TaskStatus.failed.value in task_statuses
    if has_success and has_failed:
        return "partial_success"
    if has_failed:
        return "failed"
    if has_success:
        return "published"
    return "none"


class PublishService:
    """统一发布入口。Web / CLI / AI 都调用这里。"""

    def __init__(self, session: Session):
        self.session = session
        self.articles = ArticleService(session)
        self.accounts = AccountService(session)
        self.policies = PolicyService(session)
        self.reviews = ReviewService(session)
        self.logs = LogService(session)

    def create_tasks(
        self,
        article_id: int,
        platforms: list[str],
        account_ids: dict[str, int] | None = None,
        review_override: str | None = None,
        publish_override: str | None = None,
        allow_override_review: bool = False,
        requester: str | None = None,
    ) -> list[PublishTask]:
        """为文章+平台组合创建发布任务（文档第 19 节流程）。

        allow_override_review: 仅当请求方是带 allow_override_review 权限的
        人类/API Key 时可为 True，用于突破 is_floor 下限。
        """
        article = self.articles.get(article_id)
        if not article:
            raise ValueError("article not found")
        if article.status != ArticleStatus.ready.value:
            raise ValueError("article status must be ready")

        account_ids = account_ids or {}
        tasks: list[PublishTask] = []

        for platform_name in platforms:
            account_id = account_ids.get(platform_name)
            task = self._create_single_task(
                article, platform_name, account_id,
                review_override, publish_override,
                allow_override_review, requester,
            )
            tasks.append(task)

        return tasks

    def _create_single_task(
        self,
        article: Article,
        platform_name: str,
        account_id: int | None,
        review_override: str | None,
        publish_override: str | None,
        allow_override_review: bool,
        requester: str | None,
    ) -> PublishTask:
        # 平台 / 账号
        platform = self.session.scalar(
            select(Platform).where(Platform.name == platform_name)
        )
        platform_id = platform.id if platform else None
        if platform_id is None:
            # 平台未注册，仍可创建（后续 Adapter 会失败）
            platform_id = None

        account = self.accounts.get(account_id) if account_id else None

        # 生成 / 复用 ArticleVersion
        version = self.articles.latest_version(article.id, platform_name)
        if version is None:
            version = self.articles.create_version(
                article.id, platform_name, article.title, article.content
            )

        # 幂等检查：非终态唯一（DB 部分唯一索引兜底，这里先查询避免异常）
        existing = self.session.scalar(
            select(PublishTask).where(
                PublishTask.article_version_id == version.id,
                PublishTask.platform == platform_name,
                PublishTask.account_id == account_id,
                PublishTask.status.not_in([s.value for s in TASK_TERMINAL_STATES]),
            )
        )
        if existing:
            return existing

        # PolicyResolver
        resolved = self.policies.resolve(
            platform_id=platform_id,
            account_id=account_id,
            article_id=article.id,
        )

        review_policy = resolved.review_policy.value
        publish_policy = resolved.publish_policy

        # 应用任务层覆盖（含权限/下限校验）
        if review_override:
            ReviewMode(review_override)
            if review_override != review_policy:
                # 试图调松：需要下限锁定检查
                if resolved.is_floor_locked and review_override != ReviewMode.always.value:
                    if not allow_override_review:
                        raise PermissionError(
                            "cannot relax floor-locked always review policy "
                            "without allow_override_review"
                        )
                    self.logs.policy_override(
                        None, f"override floor-locked review to {review_override} by {requester}",
                        {"platform": platform_name, "account_id": account_id},
                    )
                review_policy = review_override
        if publish_override:
            publish_policy = publish_override

        floor_locked = resolved.is_floor_locked

        # 内容安全兜底（§55）：settings 表开关优先；命中转 waiting_manual
        from .setting_service import content_safety_enabled

        ok, hits = (
            check_content_safety(article.content, article.title)
            if content_safety_enabled(self.session)
            else (True, [])
        )
        if not ok:
            task = PublishTask(
                article_id=article.id,
                article_version_id=version.id,
                platform=platform_name,
                account_id=account_id,
                review_policy=review_policy,
                publish_policy=publish_policy,
                policy_floor_locked=floor_locked,
                status=TaskStatus.waiting_manual.value,
                max_attempts=settings.max_attempts_default,
                error_code="content_safety_hit",
                error_message=f"banned words: {', '.join(hits)}",
            )
            self.session.add(task)
            self.session.commit()
            self.logs.log(
                "waiting_manual", task.id, level="warning",
                message="content safety hit", metadata={"hits": hits},
            )
            emitter.task_created(task.id, platform_name)
            return task

        # 根据 review_policy 决定初始状态
        if review_policy == ReviewMode.always.value:
            task_status = TaskStatus.waiting_review.value
        else:
            task_status = TaskStatus.pending.value

        task = PublishTask(
            article_id=article.id,
            article_version_id=version.id,
            platform=platform_name,
            account_id=account_id,
            review_policy=review_policy,
            publish_policy=publish_policy,
            policy_floor_locked=floor_locked,
            status=task_status,
            max_attempts=settings.max_attempts_default,
        )
        self.session.add(task)
        self.session.commit()

        # review=always：创建 Review 记录
        if review_policy == ReviewMode.always.value:
            self.reviews.create_review(task.id, version.id, reviewer=requester)

        self.logs.log(
            "task_created", task.id,
            message=f"发布任务已创建（平台：{platform_name}）",
        )
        emitter.task_created(task.id, platform_name)

        # publish=automatic 且 review != always → 直接进入 queued
        if publish_policy == "automatic" and review_policy != ReviewMode.always.value:
            task.status = TaskStatus.queued.value
            self.session.commit()
            emitter.task_status(task.id, TaskStatus.queued.value)

        return task

    def pre_publish_check(self, task: PublishTask) -> tuple[bool, str]:
        """真正执行发布前的最终权限检查（文档第 63 节）。"""
        article = self.articles.get(task.article_id)
        if not article or article.status != ArticleStatus.ready.value:
            return False, "article not ready"

        if task.status not in (
            TaskStatus.queued.value,
            TaskStatus.processing.value,
            TaskStatus.pending.value,
        ):
            return False, f"invalid task status: {task.status}"

        # 审核状态 + 版本一致性
        if task.review_policy == ReviewMode.always.value:
            approved = self.session.scalar(
                select(Review).where(
                    Review.task_id == task.id,
                    Review.article_version_id == task.article_version_id,
                    Review.status == ReviewStatus.approved.value,
                )
            )
            if not approved:
                # 版本不一致/未通过：打回 waiting_review 重新审核（§35/§65），
                # 而不是 blocked —— 内容变更后必须重新走 Review 流程。
                return False, "review_version_mismatch"
            # §35 完整语义：待发布版本必须就是文章当前内容（防止审核后被篡改）
            from ..models import ArticleVersion

            version = self.session.get(ArticleVersion, task.article_version_id)
            if not version or version.content != article.content or version.title != article.title:
                return False, "review_version_mismatch"

        # 发布策略
        if task.publish_policy == "disabled":
            return False, "publish disabled"

        # Platform capability（§63 清单第 6 项）：平台声明不支持发布则拦截
        from ..platforms.registry import get_adapter

        adapter = get_adapter(task.platform)
        if adapter is None:
            return False, f"no adapter for platform {task.platform}"
        if not getattr(adapter, "supports_publish", True):
            return False, f"platform {task.platform} does not support publish"

        # 账号状态 + 频率
        if task.account_id:
            account = self.accounts.get(task.account_id)
            if not account:
                return False, "account not found"
            if account.status == AccountStatus.disabled.value:
                return False, "account disabled"
            allowed, reason = self.accounts.check_publish_allowed(account)
            if not allowed:
                return False, reason

            # 浏览器会话锁：非 API 模式需要
            if needs_browser_lock(self.session, task.platform):
                s = self.accounts.get_session(task.account_id, task.platform)
                if s and s.current_task_id not in (None, task.id):
                    return False, "account browser session locked by another task"

        return True, ""

    def retry(self, task_id: int) -> PublishTask:
        task = self.session.get(PublishTask, task_id)
        if not task:
            raise ValueError("task not found")
        if task.status not in (
            TaskStatus.failed.value,
            TaskStatus.blocked.value,
            TaskStatus.timeout.value,
        ):
            raise ValueError("task not retryable")
        if task.attempt >= task.max_attempts:
            task.attempt = 0  # 显式 retry 重置
        task.status = TaskStatus.queued.value
        task.error_code = None
        task.error_message = None
        self.session.commit()
        emitter.task_status(task.id, TaskStatus.queued.value)
        return task

    def cancel(self, task_id: int) -> PublishTask:
        task = self.session.get(PublishTask, task_id)
        if not task:
            raise ValueError("task not found")
        task.status = TaskStatus.cancelled.value
        task.finished_at = _utcnow()
        self.session.commit()
        # 任务终结，释放账号浏览器锁（§50）
        if task.account_id:
            self.accounts.unlock(task.account_id, task.platform, task.id)
        emitter.task_status(task.id, TaskStatus.cancelled.value)
        return task

    def resume(self, task_id: int) -> PublishTask:
        """恢复/放行任务：

        - timeout → waiting_manual（§21）
        - waiting_manual → queued（人工接管完成）
        - pending → queued（§66 审核通过后人工点击发布；optional+manual 直接发布也走这里）
        """
        task = self.session.get(PublishTask, task_id)
        if not task:
            raise ValueError("task not found")
        if task.status == TaskStatus.timeout.value:
            task.status = TaskStatus.waiting_manual.value
            task.timeout_at = None
            self.session.commit()
            emitter.task_status(task.id, TaskStatus.waiting_manual.value)
        elif task.status in (TaskStatus.waiting_manual.value, TaskStatus.pending.value):
            task.status = TaskStatus.queued.value
            task.started_at = None
            self.session.commit()
            emitter.task_status(task.id, TaskStatus.queued.value)
        else:
            raise ValueError("task not resumable")
        return task

    def delete(self, task_id: int) -> bool:
        """删除任务（含关联 Review 与日志）。

        仅允许删除终态任务；非终态先拒绝，避免与执行中的 Worker 竞态。
        """
        task = self.session.get(PublishTask, task_id)
        if not task:
            return False
        if task.status not in (
            TaskStatus.success.value,
            TaskStatus.failed.value,
            TaskStatus.cancelled.value,
            TaskStatus.timeout.value,
        ):
            raise ValueError("仅终态任务可删除，请先取消任务")
        # 保险：释放可能残留的账号浏览器锁（§50）
        if task.account_id:
            self.accounts.unlock(task.account_id, task.platform, task.id)
        from sqlalchemy import delete as sa_delete

        from ..models import PublishLog, Review

        # 显式按依赖顺序删除，避免 ORM flush 顺序不确定导致外键失败
        self.session.execute(
            sa_delete(Review).where(Review.task_id == task_id)
        )
        self.session.execute(
            sa_delete(PublishLog).where(PublishLog.task_id == task_id)
        )
        self.session.execute(
            sa_delete(PublishTask).where(PublishTask.id == task_id)
        )
        self.session.commit()
        return True

    def list_tasks(self, status: str | None = None) -> list[PublishTask]:
        stmt = select(PublishTask).order_by(PublishTask.id.desc())
        if status:
            stmt = stmt.where(PublishTask.status == status)
        return list(self.session.scalars(stmt))

    def get_task(self, task_id: int) -> PublishTask | None:
        return self.session.get(PublishTask, task_id)