"""51CTO 浏览器发布脚本。

51CTO 博客无官方发布 API，通过 Playwright 在发布页发布
（https://blog.51cto.com/blogger/publish?old=1&newBloger=2）。
流程：填标题 → 填正文（Markdown / WuKong 编辑器）→ 点「发布」→
面板选分类/标签 → 确认 → 轮询跳转文章页确认（§26）。

模块文件名用 cto51（Python 标识符不能以数字开头），平台 key 为 51cto。
selector 按 2026-09 常见 DOM 编写，平台改版时只需更新本文件常量。
"""
from __future__ import annotations

import re

from ._common import CommonScript


class Cto51Script(CommonScript):
    platform = "51cto"
    creator_url = "https://blog.51cto.com/blogger/publish?old=1&newBloger=2"
    manual_keywords = ("安全验证", "验证码")

    TITLE_SELECTORS = (
        "input[placeholder*='标题']",
        "input.title",
        "[class*='title'] input",
    )
    EDITOR_SELECTORS = (
        "div[contenteditable='true']",
        ".CodeMirror",
        "textarea",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "存草稿")
    CONFIRM_TEXTS = ("确认发布", "发布", "确定")
    CONFIRM_EXCLUDE = ("取消", "定时")
    # 发布面板：标签输入（输入关键词后出候选，点第一个）
    TAG_INPUT_SELECTORS = (
        "input[placeholder*='标签']",
        "[class*='tag'] input[type='text']",
        ".modal input[type='text']",
    )
    TAG_OPTION_SELECTORS = (
        "[class*='tag-item']",
        "[class*='drop'] li",
        ".modal li",
    )
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    # 文章页 /u_<uid>/<id>，或跳转我的文章列表
    SUCCESS_URL_PATTERN = re.compile(r"/u_\d+/(\d+)")
    SUCCESS_URL_MARKS = ("/blogger/my",)
    SUCCESS_TEXTS = ("发布成功", "已发布", "提交成功")
    LOGIN_URL_MARKS = ("login", "signin", "passport")
    CONFIRM_TIMEOUT_MS = 25000

    async def _ensure_publish_fields(self, page, version) -> None:
        """面板必填标签：标题关键词搜索 → 点第一个候选。失败不阻断。"""
        keyword = (version.title or "技术")[:10]
        try:
            box = await self._first(page, self.TAG_INPUT_SELECTORS, timeout=4000)
            if box is None:
                return
            await box.click()
            await box.fill(keyword)
            await page.wait_for_timeout(1000)
            for sel in self.TAG_OPTION_SELECTORS:
                opts = page.locator(sel)
                count = await opts.count()
                for i in range(count):
                    o = opts.nth(i)
                    try:
                        if not await o.is_visible():
                            continue
                        text = ((await o.inner_text()) or "").strip()
                    except Exception:
                        continue
                    if text:
                        await o.click()
                        await page.wait_for_timeout(500)
                        return
        except Exception:
            pass


script = Cto51Script()
