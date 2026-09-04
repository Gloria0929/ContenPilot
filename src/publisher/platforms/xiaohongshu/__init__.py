"""小红书平台 Adapter（浏览器自动化类示例，文档第 69 节 Browser Platform x1）。

小红书无官方开放发布 API，使用 Playwright 自动化。
具体 selector / 操作由 Browser 层负责，不在此硬编码业务。
"""
from __future__ import annotations

from typing import Any

from ..base import PlatformAdapter, PublishResult
from ..registry import register


@register("xiaohongshu")
class XiaohongshuAdapter(PlatformAdapter):
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
        return bool(account and account.encrypted_credentials)

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