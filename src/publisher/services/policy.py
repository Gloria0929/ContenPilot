"""统一 PolicyResolver。

这是全系统唯一允许实现的策略解析逻辑。Web / CLI / AI 三个入口
都必须调用这里，不允许各自实现（见文档第 61、62 节）。

算法（文档第 61 节伪代码）：
- 按 Global → Platform → Account → Article → Task 顺序读取
- 无行 = 未配置 = 跳过（继承上一级）
- platform/account 层 is_floor=true 且 review_mode=always 时锁定下限
- 下限锁定后，下游试图放松（非 always）的配置被忽略
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import PolicyScope, ReviewMode, ReviewPolicy


@dataclass
class ResolvedPolicy:
    review_policy: ReviewMode
    publish_policy: str
    is_floor_locked: bool

    # 命中的最具体 scope（用于审计/展示）
    review_scope: str | None = None
    publish_scope: str | None = None


# scope 读取顺序
_ORDER = [
    PolicyScope.global_,
    PolicyScope.platform,
    PolicyScope.account,
    PolicyScope.article,
    PolicyScope.task,
]

_FLOOR_SCOPES = {PolicyScope.platform, PolicyScope.account}


class PolicyResolver:
    """从 review_policies 表解析最终策略。"""

    def __init__(self, rows: list[ReviewPolicy] | None = None):
        # rows: 预先查出的所有相关行。None 表示调用时再逐层传入。
        self._rows = rows or []

    @classmethod
    def from_rows(cls, rows: list[ReviewPolicy]) -> "PolicyResolver":
        return cls(rows)

    def resolve(
        self,
        platform: str | None = None,
        account_id: int | None = None,
        article_id: int | None = None,
        task_id: int | None = None,
        platform_id: int | None = None,
    ) -> ResolvedPolicy:
        # 构建 lookup：scope_type -> 行
        plan: dict[PolicyScope, ReviewPolicy] = {
            PolicyScope.global_: None,  # type: ignore[assignment]
            PolicyScope.platform: None,  # type: ignore[assignment]
            PolicyScope.account: None,  # type: ignore[assignment]
            PolicyScope.article: None,  # type: ignore[assignment]
            PolicyScope.task: None,  # type: ignore[assignment]
        }

        scope_ids = {
            PolicyScope.global_: None,
            PolicyScope.platform: platform_id,
            PolicyScope.account: account_id,
            PolicyScope.article: article_id,
            PolicyScope.task: task_id,
        }

        for row in self._rows:
            try:
                scope = PolicyScope(row.scope_type)
            except ValueError:
                continue
            if scope not in plan:
                continue
            # 用 scope_id 精确匹配（global 的 scope_id 为 null）
            expected = scope_ids[scope]
            if expected is None and row.scope_id is not None:
                continue
            if expected is not None and row.scope_id != expected:
                continue
            plan[scope] = row

        result_row: ReviewPolicy | None = None
        floor_locked = False

        for scope in _ORDER:
            row = plan[scope]
            if row is None:
                continue
            if floor_locked and row.review_mode != ReviewMode.always.value:
                # 已锁定下限，忽略试图放松的配置
                continue
            result_row = row
            if (
                scope in _FLOOR_SCOPES
                and row.is_floor
                and row.review_mode == ReviewMode.always.value
            ):
                floor_locked = True

        if result_row is None:
            # 完全没有配置：使用系统默认（文档推荐 personal 默认 optional / manual）
            return ResolvedPolicy(
                review_policy=ReviewMode.optional,
                publish_policy="manual",
                is_floor_locked=False,
            )

        return ResolvedPolicy(
            review_policy=ReviewMode(result_row.review_mode),
            publish_policy=result_row.publish_mode,
            is_floor_locked=floor_locked,
            review_scope=result_row.scope_type,
            publish_scope=result_row.scope_type,
        )