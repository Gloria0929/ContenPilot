"""领域模型表定义。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    cover_image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    source: Mapped[str] = mapped_column(String(64), default="manual")


class ArticleVersion(TimestampMixin, Base):
    __tablename__ = "article_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[str] = mapped_column(Text, default="[]")  # JSON 数组字符串
    cover_image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1)


class Platform(TimestampMixin, Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # juejin / xiaohongshu ...
    mode: Mapped[str] = mapped_column(String(16), default="browser")  # api / browser / manual
    capabilities: Mapped[str] = mapped_column(Text, default="{}")  # JSON


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)  # 业务标识
    platform: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_blocked: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewPolicy(TimestampMixin, Base):
    """策略表：无行 = 未配置 = 继承上级。"""

    __tablename__ = "review_policies"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", name="uq_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(32))  # PolicyScope
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_mode: Mapped[str] = mapped_column(String(32))  # ReviewMode
    publish_mode: Mapped[str] = mapped_column(String(32))  # PublishMode
    # 仅 platform / account 层可为 true，且仅当 review_mode=always 时允许
    is_floor: Mapped[bool] = mapped_column(Boolean, default=False)


class PublishTask(TimestampMixin, Base):
    __tablename__ = "publish_tasks"
    __table_args__ = (
        # 非终态部分唯一索引：幂等（见文档第 30 节）
        Index(
            "uq_task_active",
            "article_version_id",
            "platform",
            "account_id",
            unique=True,
            sqlite_where=text(
                "status NOT IN ('success','failed','cancelled','timeout')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    article_version_id: Mapped[int] = mapped_column(
        ForeignKey("article_versions.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )

    review_policy: Mapped[str] = mapped_column(String(32))  # 快照
    publish_policy: Mapped[str] = mapped_column(String(32))  # 快照
    policy_floor_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    remote_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    remote_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timeout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("publish_tasks.id"), index=True)
    article_version_id: Mapped[int] = mapped_column(
        ForeignKey("article_versions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")  # ReviewStatus
    reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class PublishLog(TimestampMixin, Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_tasks.id"), nullable=True, index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info")
    event: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column("metadata", Text, default="{}")  # 已脱敏 JSON


class AIGeneration(TimestampMixin, Base):
    __tablename__ = "ai_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id"), nullable=True
    )


class BrowserSession(TimestampMixin, Base):
    __tablename__ = "browser_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(String(32), default="idle")
    session_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    current_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class APIKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    key_hash: Mapped[str] = mapped_column(String(256), unique=True)
    allow_override_review: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Media(TimestampMixin, Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    path: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)


class Setting(TimestampMixin, Base):
    """KV 设置表（§47）。V1 承载 Web 可改的运行时开关。

    - content_safety_enabled：内容安全兜底检测（§55，Web 可显式关闭）
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")