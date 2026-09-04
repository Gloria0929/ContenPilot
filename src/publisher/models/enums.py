"""统一枚举定义，避免各模块散落字符串。"""
from enum import Enum


class ReviewMode(str, Enum):
    always = "always"
    optional = "optional"
    never = "never"


class PublishMode(str, Enum):
    automatic = "automatic"
    manual = "manual"
    scheduled = "scheduled"
    disabled = "disabled"


class PolicyScope(str, Enum):
    global_ = "global"
    platform = "platform"
    account = "account"
    article = "article"
    task = "task"


class ArticleStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    archived = "archived"


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TaskStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    processing = "processing"
    waiting_review = "waiting_review"
    waiting_auth = "waiting_auth"
    waiting_manual = "waiting_manual"
    blocked = "blocked"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"
    timeout = "timeout"


# 幂等唯一索引约束要排除的「已结束」状态
TASK_TERMINAL_STATES = {
    TaskStatus.success,
    TaskStatus.failed,
    TaskStatus.cancelled,
    TaskStatus.timeout,
}


class AccountStatus(str, Enum):
    active = "active"
    auth_expired = "auth_expired"
    cooling = "cooling"
    disabled = "disabled"


class BrowserSessionStatus(str, Enum):
    idle = "idle"
    busy = "busy"
    error = "error"