"""思否（SegmentFault）浏览器发布脚本。

思否无官方发布 API，通过 Playwright 在写作页发布
（https://segmentfault.com/write）。
流程：填标题 → 填 Markdown 正文 → 点「发布」→ 标签必填浮层选标签 →
确认发布 → 轮询跳转 segmentfault.com/a/<id> 确认（§26）。

selector 按 2026-09 常见 DOM 编写（多候选 + 文案匹配兜底），
平台改版时只需更新本文件常量。
"""
from __future__ import annotations

import re

from ._common import CommonScript


class SegmentFaultScript(CommonScript):
    platform = "segmentfault"
    creator_url = "https://segmentfault.com/write"
    manual_keywords = ("安全验证", "验证码")

    TITLE_SELECTORS = (
        "input#title",
        "input[placeholder*='标题']",
        "[class*='title'] input",
    )
    EDITOR_SELECTORS = (
        "textarea.editor-area",
        ".CodeMirror",
        "textarea",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "存草稿")
    CONFIRM_TEXTS = ("确认发布", "发布", "确认")
    CONFIRM_EXCLUDE = ("取消",)
    # 标签必填浮层：搜索框输入后点候选
    TAG_INPUT_SELECTORS = (
        "input[placeholder*='标签']",
        "[class*='tag'] input[type='text']",
        ".modal input[type='text']",
    )
    TAG_OPTION_SELECTORS = (
        "[class*='tag-option']",
        "[class*='drop'] li",
        ".modal li",
    )
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    SUCCESS_URL_PATTERN = re.compile(r"/a/(\d{6,})")
    SUCCESS_TEXTS = ("发布成功", "已发布")
    LOGIN_URL_MARKS = ("login", "signin", "userauth")
    CONFIRM_TIMEOUT_MS = 25000

    async def _ensure_publish_fields(self, page, version) -> None:
        """标签必填：标题关键词搜索 → 点第一个候选。失败不阻断。"""
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


script = SegmentFaultScript()
