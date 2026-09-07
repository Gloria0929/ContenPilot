"""百家号浏览器发布脚本。

百家号无官方发布 API，通过 Playwright 在创作中心发布
（https://baijiahao.baidu.com/builder/rc/edit?type=newArticle）。
流程：填标题 → 填富文本正文 → 点「发布」→ 面板确认 → 轮询跳转
内容管理页 / 成功提示确认（§26）。

正文为富文本编辑器（contenteditable），Markdown 原文以纯文本插入，
样式由平台自动识别换行。selector 按 2026-09 常见 DOM 编写，
平台改版时只需更新本文件常量。
"""
from __future__ import annotations

from ._common import CommonScript


class BaijiahaoScript(CommonScript):
    platform = "baijiahao"
    creator_url = "https://baijiahao.baidu.com/builder/rc/edit?type=newArticle"
    manual_keywords = ("安全验证", "验证码", "实名认证")

    TITLE_SELECTORS = (
        "textarea[placeholder*='标题']",
        "input[placeholder*='标题']",
        ".doc-title textarea",
        "[class*='title'] textarea",
    )
    EDITOR_SELECTORS = (
        ".edui-body-container",
        ".ql-editor",
        ".tui-editor-contents",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消")
    CONFIRM_TEXTS = ("确认发布", "发布", "确定")
    CONFIRM_EXCLUDE = ("取消", "定时")
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    # 发布成功后跳转内容管理页
    SUCCESS_URL_MARKS = ("/builder/rc/home", "/builder/rc/finished", "/builder/rc/manage")
    SUCCESS_TEXTS = ("发布成功", "已发布", "文章提交成功")
    LOGIN_URL_MARKS = ("login", "passport", "signin")
    LOGIN_TEXTS = ("扫码登录", "立即登录", "登录百度账号")
    CONFIRM_TIMEOUT_MS = 30000


script = BaijiahaoScript()
