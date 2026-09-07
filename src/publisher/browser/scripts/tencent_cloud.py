"""腾讯云开发者社区浏览器发布脚本。

腾讯云开发者社区无公开的个人发布 API，通过 Playwright 在写文章页发布
（https://cloud.tencent.com/developer/article/write）。
流程：填标题 → 填正文 → 点「发布」→ 右侧属性面板（专栏必选、来源、
标签）→「确认发布」→ 封面选择弹窗 →「确认并发布」→ 轮询跳转
cloud.tencent.com/developer/article/<id> 确认（§26）。

两步确认是本平台特有：_confirm_publish 先点「确认发布」，
再尝试点封面弹窗的「确认并发布」（无封面弹窗时跳过）。
selector 按 2026-09 常见 DOM 编写，平台改版时只需更新本文件常量。
"""
from __future__ import annotations

import re

from ._common import CommonScript


class TencentCloudScript(CommonScript):
    platform = "tencent_cloud"
    creator_url = "https://cloud.tencent.com/developer/article/write"
    manual_keywords = ("安全验证", "验证码", "实名认证")

    TITLE_SELECTORS = (
        "input[placeholder*='标题']",
        "input.title",
        "[class*='title'] input",
    )
    EDITOR_SELECTORS = (
        ".ql-editor",
        "textarea",
        ".CodeMirror",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "存草稿")
    CONFIRM_TEXTS = ("确认发布", "发布", "确定")
    CONFIRM_EXCLUDE = ("取消", "定时")
    # 封面选择弹窗的最终确认按钮
    FINAL_CONFIRM_TEXTS = ("确认并发布", "确认发布", "发布")
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    # 文章页 /developer/article/<id>
    SUCCESS_URL_PATTERN = re.compile(r"/developer/article/(\d+)")
    SUCCESS_URL_MARKS = ("/developer/article/write/done",)
    SUCCESS_TEXTS = ("发布成功", "已发布", "提交成功")
    LOGIN_URL_MARKS = ("login", "signin", "passport")
    CONFIRM_TIMEOUT_MS = 30000

    async def _confirm_publish(self, page) -> bool:
        """两步确认：属性面板「确认发布」→ 封面弹窗「确认并发布」。"""
        clicked = await super()._confirm_publish(page)
        await page.wait_for_timeout(2000)  # 等封面弹窗渲染
        final = await self._button_by_text(page, self.FINAL_CONFIRM_TEXTS)
        if final is not None:
            await final.click()
            clicked = True
        return clicked


script = TencentCloudScript()
