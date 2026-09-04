"""掘金平台 Adapter（浏览器自动化）。

掘金没有公开稳定的官方发布 API，实际发布走浏览器自动化：
Adapter 只做接口适配，selector / 页面操作在 browser/scripts/juejin.py。
"""
from __future__ import annotations

from typing import Any

from ..base import PlatformAdapter, PublishResult
from ..registry import register


@register("juejin")
class JuejinAdapter(PlatformAdapter):
    mode = "browser"

    async def capabilities(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "mode": self.mode,
            "supports_text": True,
            "supports_images": True,
            "supports_video": False,
            "supports_draft": True,
            "supports_publish": True,
            "supports_status": False,
        }

    async def check_account(self, account) -> bool:
        # 浏览器平台依赖 storage_state 登录态（发布时校验），不要求加密凭据
        return bool(account)

    async def authorize(self, account) -> bool:
        return True

    async def validate(self, content) -> list[str]:
        errors = []
        if not getattr(content, "title", "").strip():
            errors.append("title required")
        if not getattr(content, "content", "").strip():
            errors.append("content required")
        return errors

    async def create_draft(self, content, account=None, task_id=None) -> PublishResult:
        from ...browser import run_browser_publish

        return await run_browser_publish(
            self.platform, content, account=account, task_id=task_id, mode="draft"
        )

    async def publish(self, content, account=None, task_id=None) -> PublishResult:
        from ...browser import run_browser_publish

        return await run_browser_publish(
            self.platform, content, account=account, task_id=task_id, mode="publish"
        )

    async def get_status(self, remote_id: str) -> dict[str, Any]:
        return {}

    async def cancel(self, task) -> bool:
        return False
