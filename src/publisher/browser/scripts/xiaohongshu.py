"""小红书浏览器发布脚本（§69 Browser Platform x1，浏览器入口 §23）。

小红书无官方发布 API，通过 Playwright 在创作者中心发布。
所有 selector 集中在本文件常量中，平台改版时只需更新这里。
流程：传图（可选）→ 填标题 → 填正文 → 点发布 → 轮询成功确认（§26）。
"""
from __future__ import annotations

import json
import re

from ...platforms.base import PublishResult
from . import BrowserScript


class XiaohongshuScript(BrowserScript):
    platform = "xiaohongshu"
    creator_url = "https://creator.xiaohongshu.com/publish/publish?source=official"
    manual_keywords = ("安全验证", "滑块", "验证码", "异常环境", "captcha")

    # ---- selector 多候选，按顺序尝试 ----
    FILE_INPUT = "input[type='file']"
    TITLE_SELECTORS = (
        "#title-textarea",
        "input[placeholder*='标题']",
        "textarea[placeholder*='标题']",
        ".d-title input",
    )
    EDITOR_SELECTORS = (
        "#post-textarea",
        ".ql-editor",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布", "发布笔记")
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    SUCCESS_URL_MARK = "/publish/success"
    SUCCESS_TEXTS = ("发布成功", "已发布", "发布完成")
    CONFIRM_TIMEOUT_MS = 20000

    # 平台硬限制（超限会被平台拒绝，这里直接截断保护）
    TITLE_MAX = 20
    CONTENT_MAX = 1000

    async def is_logged_in(self, page) -> bool:
        """未登录时创作者中心会跳转登录页或展示扫码登录。"""
        if "login" in (page.url or ""):
            return False
        try:
            content = await page.content()
        except Exception:
            return False
        markers = ("扫码登录", "请使用小红书APP", "登录后即可", "手机号登录")
        return not any(m in content for m in markers)

    async def publish(self, page, version, mode: str = "publish") -> PublishResult:
        submitted = False
        try:
            images = self._local_images(version)
            if images:
                await self._upload_images(page, images)
            await self._fill_title(page, version.title or "")
            await self._fill_content(page, version.content or "")

            if mode == "draft":
                return await self._save_draft(page)

            submitted = True
            return await self._submit_and_confirm(page)
        except Exception as exc:  # noqa: BLE001
            # 点击发布之后发生的异常无法确认是否已发布成功，
            # 标记 unconfirmed 防止自动重试造成重复发布（§26）。
            return PublishResult(
                success=False,
                error_code="script_failed",
                error_message=str(exc),
                unconfirmed=submitted,
            )

    # ---- 内部步骤 ----

    @staticmethod
    def _local_images(version) -> list[str]:
        try:
            images = json.loads(version.images or "[]")
        except Exception:
            images = []
        return [p for p in images if isinstance(p, str) and not p.startswith("http")]

    async def _first(self, page, selectors, timeout: int = 8000):
        """按顺序尝试多个 selector，返回第一个可见的 locator。"""
        per = max(1500, timeout // max(len(selectors), 1))
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=per)
                return loc
            except Exception:
                continue
        return None

    async def _button_by_text(self, page, texts, exclude=()):
        """按按钮文案查找可见按钮，排除定时发布/草稿等干扰项。"""
        buttons = page.locator("button")
        count = await buttons.count()
        for i in range(count):
            b = buttons.nth(i)
            try:
                text = (await b.inner_text()).strip()
            except Exception:
                continue
            if text in texts and not any(x in text for x in exclude):
                if await b.is_visible():
                    return b
        return None

    async def _upload_images(self, page, images: list[str]) -> None:
        file_input = page.locator(self.FILE_INPUT).first
        try:
            await file_input.wait_for(state="attached", timeout=10000)
        except Exception as exc:
            raise RuntimeError("未找到图片上传入口") from exc
        await file_input.set_input_files(images)
        # 上传完成后才出现内容编辑区
        editor = await self._first(page, self.EDITOR_SELECTORS, timeout=60000)
        if editor is None:
            raise RuntimeError("图片上传后未出现内容编辑器")

    async def _fill_title(self, page, title: str) -> None:
        if not title:
            return
        loc = await self._first(page, self.TITLE_SELECTORS, timeout=6000)
        if loc is None:
            raise RuntimeError("未找到标题输入框")
        await loc.fill(title[: self.TITLE_MAX])

    async def _fill_content(self, page, content: str) -> None:
        if not content:
            return
        loc = await self._first(page, self.EDITOR_SELECTORS, timeout=6000)
        if loc is None:
            raise RuntimeError("未找到内容编辑器")
        await loc.click()
        # insert_text 对中文输入友好（不走 keypress 模拟）
        await page.keyboard.insert_text(content[: self.CONTENT_MAX])

    async def _save_draft(self, page) -> PublishResult:
        btn = await self._button_by_text(page, self.DRAFT_TEXTS)
        if btn is None:
            return PublishResult(success=False, error_code="draft_button_not_found")
        await btn.click()
        # 草稿没有远程 ID 可确认，点击成功即认为已保存
        return PublishResult(success=True)

    async def _submit_and_confirm(self, page) -> PublishResult:
        btn = await self._button_by_text(page, self.PUBLISH_TEXTS, exclude=("定时", "草稿"))
        if btn is None:
            return PublishResult(success=False, error_code="publish_button_not_found")
        await btn.click()

        # 成功确认（§26）：发布成功提示 + 尽可能提取远程 ID/URL
        elapsed = 0
        while elapsed < self.CONFIRM_TIMEOUT_MS:
            await page.wait_for_timeout(1000)
            elapsed += 1000
            url = page.url or ""
            confirmed = self.SUCCESS_URL_MARK in url
            if not confirmed:
                try:
                    content = await page.content()
                except Exception:
                    continue
                confirmed = any(t in content for t in self.SUCCESS_TEXTS)
            if confirmed:
                note_id = self._extract_note_id(url)
                remote_url = (
                    f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None
                )
                return PublishResult(success=True, remote_id=note_id, remote_url=remote_url)

        return PublishResult(
            success=False,
            unconfirmed=True,
            error_code="publish_unconfirmed",
            error_message="点击发布后未检测到成功提示，无法确认是否发布成功（§26）",
        )

    @staticmethod
    def _extract_note_id(url: str) -> str | None:
        m = re.search(r"noteId=([0-9a-zA-Z]+)", url or "")
        if m:
            return m.group(1)
        m = re.search(r"/explore/([0-9a-f]{16,})", url or "")
        if m:
            return m.group(1)
        return None


script = XiaohongshuScript()
