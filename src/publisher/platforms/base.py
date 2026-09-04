"""平台 Adapter 基类（文档第 31 节）。

平台发布必须通过统一 Adapter。不同平台可用不同实现（API/Browser/Manual/Hybrid）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PublishResult:
    def __init__(
        self,
        success: bool,
        remote_id: str | None = None,
        remote_url: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        needs_auth: bool = False,
        needs_manual: bool = False,
        unconfirmed: bool = False,
    ):
        self.success = success
        self.remote_id = remote_id
        self.remote_url = remote_url
        self.error_code = error_code
        self.error_message = error_message
        self.needs_auth = needs_auth
        self.needs_manual = needs_manual
        # 已点击发布但无法确认结果（§26），Worker 据此置为 blocked 防止重复发布
        self.unconfirmed = unconfirmed


class PlatformAdapter(ABC):
    """所有平台 Adapter 统一接口。"""

    platform: str = ""
    # 发布模式：api（官方 API，不占浏览器锁）/ browser（Playwright）/ manual。
    # capabilities() 应引用该值，保持类属性与运行时能力一致。
    mode: str = "browser"
    # 同步静态能力声明（§32/§63）：不支持发布/仅草稿的平台在 pre_publish_check 拦截
    supports_publish: bool = True

    @abstractmethod
    async def capabilities(self) -> dict[str, Any]: ...

    @abstractmethod
    async def check_account(self, account) -> bool: ...

    @abstractmethod
    async def authorize(self, account) -> bool: ...

    @abstractmethod
    async def validate(self, content) -> list[str]: ...

    @abstractmethod
    async def create_draft(self, content, account=None, task_id=None) -> PublishResult: ...

    @abstractmethod
    async def publish(self, content, account=None, task_id=None) -> PublishResult: ...

    @abstractmethod
    async def get_status(self, remote_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def cancel(self, task) -> bool: ...