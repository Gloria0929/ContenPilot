"""FreeBuf 浏览器发布脚本。

FreeBuf 无官方发布 API（文章投稿后需平台审核），通过 Playwright 在
创作中心发布（https://www.freebuf.com/newpost）。
流程：填标题 → 填正文 → 点「提交」→ 轮询提交成功确认（§26）。

FreeBuf 文章提交后进入人工审核，任务以「提交成功」为发布成功；
最终是否过审由平台决定（unconfirmed 语义不适用于审核环节）。
selector 按 2026-09 常见 DOM 编写（多候选 + 文案匹配兜底），
平台改版时只需更新本文件常量。
"""
from __future__ import annotations

from ._common import CommonScript


class FreebufScript(CommonScript):
    platform = "freebuf"
    creator_url = "https://www.freebuf.com/newpost"
    manual_keywords = ("安全验证", "验证码", "滑块")

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
    # FreeBuf 提交按钮为「提交」（投稿语义）
    PUBLISH_TEXTS = ("提交", "发布")
    PUBLISH_EXCLUDE = ("草稿", "取消", "定时")
    CONFIRM_TEXTS = ("确认提交", "提交", "确认")
    CONFIRM_EXCLUDE = ("取消",)
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    # 提交后跳转个人文章列表 / 新文章页
    SUCCESS_URL_MARKS = ("/my/articles", "/u_", "/articles/")
    SUCCESS_TEXTS = ("提交成功", "投稿成功", "发布成功")
    LOGIN_URL_MARKS = ("login", "signin", "passport")
    CONFIRM_TIMEOUT_MS = 25000


script = FreebufScript()
