"""PolicyResolver 测试（文档第 75.24 条要求：完整优先级 + 下限规则测试）。"""
from __future__ import annotations

import pytest

from publisher.models import (
    PolicyScope,
    PublishMode,
    ReviewMode,
    ReviewPolicy,
)
from publisher.services.policy import PolicyResolver, ResolvedPolicy


def _row(
    scope: PolicyScope,
    scope_id: int | None,
    review: ReviewMode,
    publish: PublishMode = PublishMode.manual,
    is_floor: bool = False,
) -> ReviewPolicy:
    return ReviewPolicy(
        scope_type=scope.value,
        scope_id=scope_id,
        review_mode=review.value,
        publish_mode=publish.value,
        is_floor=is_floor,
    )


def _resolve(rows):
    return PolicyResolver.from_rows(rows).resolve(
        platform_id=1, account_id=10, article_id=100, task_id=1000
    )


def test_empty_uses_default():
    r = _resolve([])
    assert r.review_policy == ReviewMode.optional
    assert r.publish_policy == "manual"
    assert not r.is_floor_locked


def test_global_only():
    r = _resolve([_row(PolicyScope.global_, None, ReviewMode.always)])
    assert r.review_policy == ReviewMode.always


def test_platform_overrides_global():
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.platform, 1, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.never


def test_article_overrides_platform():
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.platform, 1, ReviewMode.never),
        _row(PolicyScope.article, 100, ReviewMode.optional),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.optional


def test_task_highest_priority():
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.article, 100, ReviewMode.optional),
        _row(PolicyScope.task, 1000, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.never


def test_missing_middle_scope_skipped():
    """account 未配置时，article 直接生效。"""
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.article, 100, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.never


def test_account_floor_blocks_article_relaxation():
    """关键用例：account 显式 always + is_floor 时，article 无法调松。"""
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.account, 10, ReviewMode.always, is_floor=True),
        _row(PolicyScope.article, 100, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.always
    assert r.is_floor_locked


def test_account_mere_always_without_floor_is_relaxable():
    """account 显式 always 但未标 is_floor 时，article 可以调松。"""
    rows = [
        _row(PolicyScope.account, 10, ReviewMode.always, is_floor=False),
        _row(PolicyScope.article, 100, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.never
    assert not r.is_floor_locked


def test_platform_floor_blocks_task_relaxation():
    rows = [
        _row(PolicyScope.platform, 1, ReviewMode.always, is_floor=True),
        _row(PolicyScope.task, 1000, ReviewMode.never),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.always
    assert r.is_floor_locked


def test_floor_does_not_block_tightening():
    """下限只阻止调松，不阻止调严。"""
    rows = [
        _row(PolicyScope.account, 10, ReviewMode.always, is_floor=True),
        _row(PolicyScope.article, 100, ReviewMode.always),
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.always


def test_scope_id_mismatch_ignored():
    """scope_id 不匹配的行不影响解析。"""
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.always),
        _row(PolicyScope.account, 999, ReviewMode.never),  # 不匹配 account_id=10
    ]
    r = _resolve(rows)
    assert r.review_policy == ReviewMode.always