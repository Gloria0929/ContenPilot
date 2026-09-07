"""审核服务：Review 记录绑定具体 ArticleVersion（文档第 35 节）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PublishTask, Review, ReviewStatus, TaskStatus


class ReviewService:
    def __init__(self, session: Session):
        self.session = session

    def create_review(
        self,
        task_id: int,
        article_version_id: int,
        reviewer: str | None = None,
    ) -> Review:
        review = Review(
            task_id=task_id,
            article_version_id=article_version_id,
            status=ReviewStatus.pending.value,
            reviewer=reviewer,
        )
        self.session.add(review)
        self.session.commit()
        return review

    def list_pending(self) -> list[Review]:
        return list(
            self.session.scalars(
                select(Review).where(Review.status == ReviewStatus.pending.value)
            )
        )

    def get(self, review_id: int) -> Review | None:
        return self.session.get(Review, review_id)

    def approve(
        self, review_id: int, reviewer: str | None = None, comment: str | None = None
    ) -> Review:
        review = self.get(review_id)
        if not review:
            raise ValueError("review not found")
        if review.status != ReviewStatus.pending.value:
            raise ValueError(
                f"review #{review_id} 当前状态为 {review.status}，仅待审核记录可审批"
            )
        review.status = ReviewStatus.approved.value
        review.reviewer = reviewer
        if comment:
            review.comment = comment
        # 任务流转（§65/§66，CLI 与 API 共用）：
        # publish=automatic → queued 直接发布；manual → pending 等待人工放行
        task = self.session.get(PublishTask, review.task_id)
        if task and task.status == TaskStatus.waiting_review.value:
            if task.publish_policy == "automatic":
                task.status = TaskStatus.queued.value
            elif task.publish_policy == "manual":
                task.status = TaskStatus.pending.value
        self.session.commit()
        return review

    def reject(
        self, review_id: int, reviewer: str | None = None, comment: str | None = None
    ) -> Review:
        review = self.get(review_id)
        if not review:
            raise ValueError("review not found")
        if review.status != ReviewStatus.pending.value:
            raise ValueError(
                f"review #{review_id} 当前状态为 {review.status}，仅待审核记录可驳回"
            )
        review.status = ReviewStatus.rejected.value
        review.reviewer = reviewer
        if comment:
            review.comment = comment
        # 关联任务留在 waiting_review：文档 9.2 推荐「编辑新版本后重新送审」
        # （Web 审核页的 refresh 接口负责重绑新版本并把 review 恢复 pending）。
        # 注意不要无条件改写任务状态——review 与任务的流转可能不同步
        # （如任务已 success/failed 终态），强行拉回 waiting_review 会破坏终态。
        self.session.commit()
        return review

    def is_version_approved(self, task: PublishTask) -> bool:
        """校验存在与 Task 相同 article_version_id 的已通过审核记录。"""
        if task.review_policy != "always":
            return True
        return (
            self.session.scalar(
                select(Review).where(
                    Review.task_id == task.id,
                    Review.article_version_id == task.article_version_id,
                    Review.status == ReviewStatus.approved.value,
                )
            )
            is not None
        )