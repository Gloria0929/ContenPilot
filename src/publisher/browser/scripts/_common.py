"""新平台浏览器脚本通用基类（Browser 层内部复用）。

提供多候选 selector 尝试、按文案找按钮、标题/正文填写、发布确认轮询
等通用流程；各平台脚本继承本类，只声明 selector 常量并按需覆盖钩子：

- _ensure_publish_fields(page, version)：主发布按钮点击后填写面板必填项
  （分类 / 标签 / 摘要等），默认无操作；
- _confirm_publish(page)：面板必填项填完后的确认点击（如「发布文章」），
  默认按 CONFIRM_TEXTS 再找一次确认按钮。

安全语义（§26）：主发布按钮点击后即视为无法回退，此后任何异常 /
无法确认结果都返回 unconfirmed=True，由 Worker 置 blocked 防重复发布。
"""
from __future__ import annotations

import re

from ...platforms.base import PublishResult
from . import BrowserScript


class CommonScript(BrowserScript):
    # ---- 子类声明的平台常量 ----
    TITLE_SELECTORS: tuple[str, ...] = ()
    EDITOR_SELECTORS: tuple[str, ...] = ()
    # 主发布按钮（打开发布面板或直接发布）
    PUBLISH_TEXTS: tuple[str, ...] = ("发布",)
    PUBLISH_EXCLUDE: tuple[str, ...] = ("定时", "草稿", "取消")
    # 发布面板内的确认按钮（CSDN「发布文章」/ 腾讯云「确认发布」等）
    CONFIRM_TEXTS: tuple[str, ...] = ("确认发布", "发布文章", "确认并发布", "发布")
    CONFIRM_EXCLUDE: tuple[str, ...] = ("定时", "取消")
    # 草稿按钮（无独立草稿按钮的平台留空 → 等自动保存）
    DRAFT_TEXTS: tuple[str, ...] = ()
    # 成功确认：URL 正则（group(1) 为远程文章 id）
    SUCCESS_URL_PATTERN: re.Pattern | None = None
    # URL 包含任一标记即成功（如 /published、/article/list）
    SUCCESS_URL_MARKS: tuple[str, ...] = ()
    # 成功提示文案
    SUCCESS_TEXTS: tuple[str, ...] = ()
    # 登录页 URL 特征
    LOGIN_URL_MARKS: tuple[str, ...] = ("login", "signin", "passport", "userauth")
    # 未登录页面特征文案（编辑器不可见时的兜底判定）
    LOGIN_TEXTS: tuple[str, ...] = ("扫码登录", "立即登录")
    CONFIRM_TIMEOUT_MS = 25000
    TITLE_MAX = 100
    CONTENT_MAX = 0  # 0 = 不截断

    async def is_logged_in(self, page) -> bool:
        """通用登录判定：登录页 URL → 未登录；编辑器可见 → 已登录；
        其余按页面登录特征文案兜底。"""
        url = (page.url or "").lower()
        if any(m in url for m in self.LOGIN_URL_MARKS):
            return False
        loc = await self._first(
            page, self.TITLE_SELECTORS + self.EDITOR_SELECTORS, timeout=4000
        )
        if loc is not None:
            return True
        try:
            content = await page.content()
        except Exception:
            return False
        return not any(t in content for t in self.LOGIN_TEXTS)

    async def publish(self, page, version, mode: str = "publish") -> PublishResult:
        submitted = [False]
        try:
            await self._fill_title(page, version.title or "")
            await self._fill_content(page, version.content or "")
            if mode == "draft":
                return await self._save_draft(page)
            return await self._submit_and_confirm(page, submitted, version)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                success=False,
                error_code="script_failed",
                error_message=str(exc),
                unconfirmed=submitted[0],
            )

    # ---- 钩子（平台按需覆盖）----

    async def _ensure_publish_fields(self, page, version) -> None:
        """发布面板必填项（分类 / 标签 / 摘要），默认无操作。"""

    async def _confirm_publish(self, page) -> bool:
        """面板必填项填完后的确认点击。返回 True 表示已点击确认。
        默认按 CONFIRM_TEXTS 找确认按钮；找不到返回 False（视为无面板，
        主按钮已直接提交）。"""
        await page.wait_for_timeout(1200)  # 等面板渲染
        confirm = await self._button_by_text(
            page, self.CONFIRM_TEXTS, exclude=self.CONFIRM_EXCLUDE
        )
        if confirm is None:
            return False
        await confirm.click()
        return True

    # ---- 通用步骤 ----

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

    async def _button_by_text(self, page, texts, exclude=(), scope=None):
        """按按钮文案查找可见按钮（精确匹配），排除干扰项。"""
        root = scope if scope is not None else page
        buttons = root.locator("button")
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

    async def _fill_title(self, page, title: str) -> None:
        if not title:
            return
        loc = await self._first(page, self.TITLE_SELECTORS, timeout=10000)
        if loc is None:
            raise RuntimeError("未找到标题输入框")
        await loc.fill(title[: self.TITLE_MAX])

    async def _fill_content(self, page, content: str) -> None:
        if not content:
            return
        if self.CONTENT_MAX:
            content = content[: self.CONTENT_MAX]
        loc = await self._first(page, self.EDITOR_SELECTORS, timeout=10000)
        if loc is None:
            raise RuntimeError("未找到内容编辑器")
        try:
            tag = (await loc.evaluate("el => el.tagName")).lower()
        except Exception:
            tag = ""
        if tag == "textarea":
            await loc.fill(content)
        else:
            # CodeMirror / contenteditable 富文本：点击聚焦后 insert_text
            await loc.click()
            try:
                await page.keyboard.press("ControlOrMeta+a")
                await page.keyboard.press("Delete")
            except Exception:
                pass
            await page.keyboard.insert_text(content)

    async def _save_draft(self, page) -> PublishResult:
        if self.DRAFT_TEXTS:
            btn = await self._button_by_text(page, self.DRAFT_TEXTS)
            if btn is not None:
                await btn.click()
                await page.wait_for_timeout(2000)
                return PublishResult(success=True)
        # 无独立草稿按钮：编辑器自动保存，等一轮即可
        await page.wait_for_timeout(3000)
        return PublishResult(success=True)

    async def _submit_and_confirm(
        self, page, submitted: list[bool], version
    ) -> PublishResult:
        btn = await self._button_by_text(
            page, self.PUBLISH_TEXTS, exclude=self.PUBLISH_EXCLUDE
        )
        if btn is None:
            await page.wait_for_timeout(2000)  # 编辑器还在渲染时再等一轮
            btn = await self._button_by_text(
                page, self.PUBLISH_TEXTS, exclude=self.PUBLISH_EXCLUDE
            )
        if btn is None:
            return PublishResult(success=False, error_code="publish_button_not_found")
        await btn.click()
        # 主按钮点击后即无法确认是否已发布（部分平台直接发布，部分弹面板）
        submitted[0] = True

        # 等发布面板渲染（面板必填项的按钮此时才可见，不等会静默跳过）
        await page.wait_for_timeout(2000)
        # 面板必填项（分类/标签/摘要）→ 确认按钮（可能无面板）
        await self._ensure_publish_fields(page, version)
        await self._confirm_publish(page)
        return await self._wait_success(page)

    async def _wait_success(self, page) -> PublishResult:
        """轮询确认发布结果（§26）：URL 跳转 > 成功提示。"""
        elapsed = 0
        while elapsed < self.CONFIRM_TIMEOUT_MS:
            await page.wait_for_timeout(1000)
            elapsed += 1000
            result = self._check_success(page.url or "")
            if result is not None:
                return result
            try:
                content = await page.content()
            except Exception:
                continue
            if any(t in content for t in self.SUCCESS_TEXTS):
                # 成功提示已出；再给跳转几秒时间拿远程链接
                for _ in range(5):
                    await page.wait_for_timeout(1000)
                    result = self._check_success(page.url or "")
                    if result is not None:
                        return result
                return PublishResult(success=True)
        return PublishResult(
            success=False,
            unconfirmed=True,
            error_code="publish_unconfirmed",
            error_message="点击发布后未检测到跳转或成功提示，无法确认是否发布成功（§26）",
        )

    def _check_success(self, url: str) -> PublishResult | None:
        """按 URL 判定发布成功；不成功返回 None（继续轮询）。"""
        if self.SUCCESS_URL_PATTERN:
            m = self.SUCCESS_URL_PATTERN.search(url)
            if m:
                rid = m.group(1) if m.groups() else None
                return PublishResult(success=True, remote_id=rid, remote_url=url)
        if any(mark in url for mark in self.SUCCESS_URL_MARKS):
            return PublishResult(success=True, remote_url=url)
        return None
