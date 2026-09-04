"""Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Article ----

class ArticleIn(BaseModel):
    title: str = ""
    content: str = ""
    summary: str = ""
    cover_image: str | None = None
    source: str = "manual"


class ArticleUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    cover_image: str | None = None
    status: str | None = None


class ArticleOut(ORMModel):
    id: int
    title: str
    content: str
    summary: str
    cover_image: str | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class ArticleVersionOut(ORMModel):
    id: int
    article_id: int
    platform: str
    title: str
    content: str
    images: str
    cover_image: str | None
    metadata: str = Field(validation_alias="metadata_json")
    version: int
    created_at: datetime


# ---- AI ----

class AIGenerateIn(BaseModel):
    prompt: str
    provider: str | None = None
    model: str | None = None


class AIReviseIn(BaseModel):
    content: str
    instruction: str
    provider: str | None = None
    model: str | None = None


class AIAdaptIn(BaseModel):
    article_id: int
    platform: str
    provider: str | None = None
    model: str | None = None


# ---- Review ----

class ReviewAction(BaseModel):
    comment: str | None = None


# ---- Publish ----

class PublishRequest(BaseModel):
    article_id: int
    platforms: list[str] = Field(default_factory=list)  # 空 = 由策略决定
    account_ids: dict[str, int] = Field(default_factory=dict)  # platform -> account_id
    review_override: str | None = None  # always/optional/never，本次任务覆盖
    publish_override: str | None = None


class PublishTaskOut(ORMModel):
    id: int
    article_id: int
    article_version_id: int
    platform: str
    account_id: int | None
    review_policy: str
    publish_policy: str
    policy_floor_locked: bool
    status: str
    attempt: int
    max_attempts: int
    remote_id: str | None
    remote_url: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    timeout_at: datetime | None
    created_at: datetime


class ResolvedPolicyOut(BaseModel):
    review_policy: str
    publish_policy: str
    is_floor_locked: bool
    review_scope: str | None = None
    publish_scope: str | None = None


class PolicySetIn(BaseModel):
    """设置/覆盖某 scope 的策略。None 表示删除该 scope 行（跟随上级）。"""

    scope_type: str
    scope_id: int | None = None
    review_mode: str | None = None
    publish_mode: str | None = None
    is_floor: bool = False


# ---- Account ----

class AccountIn(BaseModel):
    key: str
    platform: str
    name: str = ""


class AccountOut(ORMModel):
    id: int
    key: str
    platform: str
    name: str
    status: str
    last_published_at: datetime | None
    consecutive_blocked: int
    cooldown_until: datetime | None


# ---- Auth ----

class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str


class WhoamiOut(BaseModel):
    authenticated: bool
    username: str | None = None
    source: str | None = None  # session / api_key


# ---- Suggest ----

class SuggestOut(BaseModel):
    """AI 生成 / 适配的结果建议。"""

    title: str
    content: str
    summary: str = ""
    platform: str | None = None
    images: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)