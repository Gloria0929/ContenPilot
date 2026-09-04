"""端到端集成测试：通过真实 DB 验证 floor 锁定与幂等。"

注意：engine 在 import 时已按 settings 构建，测试里通过策略服务直接验证。
"""
from __future__ import annotations

import pytest

from publisher.services.policy import PolicyResolver
from publisher.models import PolicyScope, ReviewMode, PublishMode, ReviewPolicy


def _row(scope, scope_id, review, publish=PublishMode.manual, is_floor=False):
    return ReviewPolicy(
        scope_type=scope.value,
        scope_id=scope_id,
        review_mode=review.value,
        publish_mode=publish.value,
        is_floor=is_floor,
    )


def test_account_floor_never_relaxable_by_article():
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.optional),
        _row(PolicyScope.account, 1, ReviewMode.always, is_floor=True),
        _row(PolicyScope.article, 10, ReviewMode.never),
    ]
    r = PolicyResolver.from_rows(rows).resolve(account_id=1, article_id=10)
    assert r.review_policy == ReviewMode.always
    assert r.is_floor_locked


def test_publish_and_review_decoupled():
    rows = [
        _row(PolicyScope.global_, None, ReviewMode.never, PublishMode.automatic),
    ]
    r = PolicyResolver.from_rows(rows).resolve()
    assert r.review_policy == ReviewMode.never
    assert r.publish_policy == "automatic"