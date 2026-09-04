"""策略服务：对 review_policies 表的读写，并封装 PolicyResolver。

所有入口（Web/CLI/AI/API）通过这里解析与写入策略，
保证「无行 = 未配置 = 继承上级」的语义统一实现。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    PolicyScope,
    PublishMode,
    ReviewMode,
    ReviewPolicy,
)
from .policy import PolicyResolver, ResolvedPolicy


class PolicyService:
    def __init__(self, session: Session):
        self.session = session

    def get_rows(
        self,
        platform_id: int | None = None,
        account_id: int | None = None,
        article_id: int | None = None,
        task_id: int | None = None,
    ) -> list[ReviewPolicy]:
        """一次性查出所有相关作用域的行。"""
        conds = [ReviewPolicy.scope_type == PolicyScope.global_.value]
        if platform_id is not None:
            conds.append(
                (ReviewPolicy.scope_type == PolicyScope.platform.value)
                & (ReviewPolicy.scope_id == platform_id)
            )
        if account_id is not None:
            conds.append(
                (ReviewPolicy.scope_type == PolicyScope.account.value)
                & (ReviewPolicy.scope_id == account_id)
            )
        if article_id is not None:
            conds.append(
                (ReviewPolicy.scope_type == PolicyScope.article.value)
                & (ReviewPolicy.scope_id == article_id)
            )
        if task_id is not None:
            conds.append(
                (ReviewPolicy.scope_type == PolicyScope.task.value)
                & (ReviewPolicy.scope_id == task_id)
            )
        stmt = select(ReviewPolicy)
        # OR 组合
        from sqlalchemy import or_

        stmt = stmt.where(or_(*conds))
        return list(self.session.scalars(stmt))

    def resolve(
        self,
        platform_id: int | None = None,
        account_id: int | None = None,
        article_id: int | None = None,
        task_id: int | None = None,
    ) -> ResolvedPolicy:
        rows = self.get_rows(platform_id, account_id, article_id, task_id)
        return PolicyResolver.from_rows(rows).resolve(
            platform_id=platform_id,
            account_id=account_id,
            article_id=article_id,
            task_id=task_id,
        )

    def set_policy(
        self,
        scope_type: str,
        scope_id: int | None,
        review_mode: str | None,
        publish_mode: str | None,
        is_floor: bool = False,
    ) -> ReviewPolicy | None:
        """写入或删除某 scope 的策略。

        review_mode 与 publish_mode 均为 None 时删除该行。
        """
        scope = PolicyScope(scope_type)

        existing = self.session.scalar(
            select(ReviewPolicy).where(
                ReviewPolicy.scope_type == scope.value,
                ReviewPolicy.scope_id == scope_id,
            )
        )

        if review_mode is None and publish_mode is None:
            if existing:
                self.session.delete(existing)
                self.session.commit()
            return None

        review_mode = review_mode or (existing.review_mode if existing else ReviewMode.optional.value)
        publish_mode = publish_mode or (existing.publish_mode if existing else PublishMode.manual.value)

        # 校验
        ReviewMode(review_mode)
        PublishMode(publish_mode)

        if is_floor:
            # is_floor 只允许在 platform/account 层，且 review_mode=always
            if scope not in (PolicyScope.platform, PolicyScope.account):
                raise ValueError("is_floor 仅允许 platform/account 层")
            if review_mode != ReviewMode.always.value:
                raise ValueError("is_floor=true 要求 review_mode=always")

        if existing:
            existing.review_mode = review_mode
            existing.publish_mode = publish_mode
            existing.is_floor = is_floor
            row = existing
        else:
            row = ReviewPolicy(
                scope_type=scope.value,
                scope_id=scope_id,
                review_mode=review_mode,
                publish_mode=publish_mode,
                is_floor=is_floor,
            )
            self.session.add(row)
        self.session.commit()
        return row

    def can_ai_override(self, target_review: str, resolved: ResolvedPolicy) -> bool:
        """AI 是否能把策略调松。

        规则（文档第 12 节）：如果 resolved.is_floor_locked 才允许突破，
        但普通 AI 默认不允许突破下限。这里返回是否违反下限。
        """
        if not resolved.is_floor_locked:
            return True
        # 已被下限锁定：不允许调松为 non-always
        return target_review == ReviewMode.always.value