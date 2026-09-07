"""通用浏览器平台 Adapter 基类。

无官方发布 API 的平台（CSDN / 思否 / FreeBuf / 百家号 / 企鹅号 / 51CTO /
腾讯云开发者社区等）共用同一套浏览器自动化流程：
Adapter 只做接口适配，selector / 页面操作在 browser/scripts/<platform>.py。

新增浏览器平台：建 platforms/<name>/__init__.py 继承本类并
@register("<name>") 即可，无需复制本文件。
"""
from __future__ import annotations

from typing import Any

from .base import PlatformAdapter, PublishResult


class BrowserModeAdapter(PlatformAdapter):
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
        # _browser.py 位于 publisher.platforms 包内（非子包），相对导入为两级
        from ..browser import run_browser_publish

        return await run_browser_publish(
            self.platform, content, account=account, task_id=task_id, mode="draft"
        )

    async def publish(self, content, account=None, task_id=None) -> PublishResult:
        from ..browser import run_browser_publish

        return await run_browser_publish(
            self.platform, content, account=account, task_id=task_id, mode="publish"
        )

    async def get_status(self, remote_id: str) -> dict[str, Any]:
        return {}

    async def cancel(self, task) -> bool:
        return False
