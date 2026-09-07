"""CSDN 浏览器发布脚本（selector 已按 2026-09 真实 DOM 实测校准）。

CSDN 无官方发布 API，通过 Playwright 在 Markdown 编辑器发布
（https://editor.csdn.net/md?not_checkout=1）。

实测 DOM 要点（2026-09，探测日志见会话记录）：
- 标题：可见区是 .article-bar__title-display（显示【无标题】），点击后
  激活隐藏的 input.article-bar__title（aria-hidden + display:none）；
  受控组件，fill 会被失焦清空，必须 全选删除 + insert_text。
- 正文：pre.editor__inner（自定义 MD 编辑器，非 CodeMirror），
  点击聚焦 + 全选删除模板 + insert_text。
- 发布流程：底部 button.btn-publish「发布文章」→ 弹发布面板
  （.modal__publish-article）→ 标签必填（红 *）：点「+ 添加文章标签」
  （button.tag__btn-tag）→ 搜索框输入（placeholder 含「Enter键入可添加
  自定义标签」）→ Enter 添加自定义标签 → 面板底部 button.btn-b-red
  「发布文章」确认 → 轮询跳转 blog.csdn.net/<user>/article/details/<id>。
"""
from __future__ import annotations

import re

from ._common import CommonScript


class CsdnScript(CommonScript):
    platform = "csdn"
    creator_url = "https://editor.csdn.net/md?not_checkout=1"
    manual_keywords = ("安全验证", "滑块", "验证码", "异常访问")

    # 标题特殊交互：显示区（div）点击激活隐藏 input（受控组件）
    TITLE_DISPLAY = ".article-bar__title-display"
    TITLE_INPUT = "input.article-bar__title"
    # 正文编辑器（实测为自定义 pre，非 CodeMirror）
    EDITOR_SELECTORS = (
        "pre.editor__inner",
        ".CodeMirror",
        "div[contenteditable='true']",
    )
    # 底部主按钮「发布文章」打开发布面板
    PUBLISH_TEXTS = ("发布文章",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消")
    # 面板内确认按钮（面板独有的红色主按钮 class）
    CONFIRM_BUTTON = "button.btn-b-red"
    CONFIRM_TEXTS = ("发布文章",)
    CONFIRM_EXCLUDE = ("定时", "取消")
    # 发布面板：标签必填（红色星号），「添加文章标签」按钮 + 搜索框
    TAG_ADD_BUTTON = "button.tag__btn-tag"
    TAG_ADD_TEXT = "添加文章标签"
    TAG_SEARCH = "input[placeholder*='Enter']"
    DRAFT_TEXTS = ("保存草稿",)
    # 成功：跳转文章页 /article/details/<id>
    SUCCESS_URL_PATTERN = re.compile(r"/article/details/(\d+)")
    SUCCESS_TEXTS = ("发布成功",)
    LOGIN_URL_MARKS = ("login", "passport", "signin")
    CONFIRM_TIMEOUT_MS = 30000

    # 登录会话 cookie 特征（CSDN 账号体系）
    SESSION_COOKIE_HINTS = ("usernametoken", "uniquelytoken", "p_uid", "logined")

    async def is_logged_in(self, page) -> bool:
        """登录判定：passport 跳转 / cookie 特征 / 编辑器 DOM 三级兜底。"""
        url = (page.url or "").lower()
        if "passport.csdn.net" in url or "login" in url:
            return False
        try:
            cookies = await page.context.cookies("https://editor.csdn.net")
            for c in cookies:
                name = (c.get("name") or "").lower()
                if any(h in name for h in self.SESSION_COOKIE_HINTS):
                    return True
        except Exception:
            pass
        return await super().is_logged_in(page)

    # ---- CSDN 特有步骤 ----

    async def _fill_title(self, page, title: str) -> None:
        """标题：点击显示区激活隐藏 input（fill 会被受控组件清空，
        必须 全选删除 + insert_text 触发原生 input 事件）。"""
        if not title:
            return
        disp = page.locator(self.TITLE_DISPLAY).first
        try:
            await disp.wait_for(state="visible", timeout=5000)
            await disp.click()
        except Exception:
            pass  # 显示区可能已激活
        inp = page.locator(self.TITLE_INPUT).first
        await inp.wait_for(state="visible", timeout=5000)
        await inp.click()
        await page.keyboard.press("ControlOrMeta+a")
        await page.keyboard.press("Delete")
        await page.keyboard.insert_text(title[: self.TITLE_MAX])

    async def _ensure_publish_fields(self, page, version) -> None:
        """发布面板必填标签：点「+ 添加文章标签」→ 输入关键词 → Enter
        添加自定义标签（实测无需从候选列表选）。失败不阻断。"""
        keyword = (version.title or "技术")[:10]
        try:
            btn = page.locator(
                self.TAG_ADD_BUTTON, has_text=self.TAG_ADD_TEXT
            ).first
            try:
                await btn.wait_for(state="visible", timeout=5000)
            except Exception:
                return  # 面板无标签入口（可能已带默认标签）
            await btn.click()
            await page.wait_for_timeout(1200)
            search = page.locator(self.TAG_SEARCH).first
            await search.wait_for(state="visible", timeout=4000)
            await search.click()
            await page.keyboard.insert_text(keyword)
            await page.wait_for_timeout(1200)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(800)
        except Exception:
            pass  # 标签失败交由平台校验报错（面板会红字提示）

    async def _confirm_publish(self, page) -> bool:
        """面板确认：btn-b-red 是面板独有 class，避免与编辑器底部的
        btn-publish（同名文案「发布文章」）混淆。"""
        await page.wait_for_timeout(1500)  # 等面板渲染
        btn = page.locator(self.CONFIRM_BUTTON).first
        try:
            await btn.wait_for(state="visible", timeout=5000)
        except Exception:
            return await super()._confirm_publish(page)
        for _ in range(10):  # 最多等 5s 可点击
            try:
                if not await btn.is_disabled():
                    break
            except Exception:
                break
            await page.wait_for_timeout(500)
        await btn.click()
        return True


script = CsdnScript()
