"""企鹅号（腾讯内容开放平台）浏览器发布脚本。

企鹅号无官方发布 API，通过 Playwright 在创作后台发布
（https://om.qq.com/article/articleCreate）。
流程：填标题 → 填富文本正文 → 点「发布」→ 面板确认 → 轮询跳转
文章管理页 / 成功提示确认（§26）。发布内容自动分发到腾讯网 /
腾讯新闻 / QQ浏览器等腾讯系渠道。

正文为富文本编辑器（contenteditable），Markdown 原文以纯文本插入。
selector 按 2026-09 常见 DOM 编写，平台改版时只需更新本文件常量。
"""
from __future__ import annotations

from ._common import CommonScript


class QiehaoScript(CommonScript):
    platform = "qiehao"
    creator_url = "https://om.qq.com/article/articleCreate"
    manual_keywords = ("安全验证", "验证码", "实名认证")

    TITLE_SELECTORS = (
        "input[placeholder*='标题']",
        "textarea[placeholder*='标题']",
        "[class*='title'] input",
        "[class*='title'] textarea",
    )
    EDITOR_SELECTORS = (
        ".edui-body-container",
        ".ql-editor",
        ".editor-content",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "存草稿")
    CONFIRM_TEXTS = ("确认发布", "发布", "确定")
    CONFIRM_EXCLUDE = ("取消", "定时")
    DRAFT_TEXTS = ("保存草稿", "存草稿")
    # 发布成功后跳转文章管理页
    SUCCESS_URL_MARKS = ("/article/articleList", "/article/articleManage", "/publish/success")
    SUCCESS_TEXTS = ("发布成功", "已发布", "文章提交成功")
    # om.qq.com 登录走 userAuth 路由
    LOGIN_URL_MARKS = ("login", "signin", "userauth", "passport")
    LOGIN_TEXTS = ("扫码登录", "立即登录", "QQ登录", "微信登录")
    CONFIRM_TIMEOUT_MS = 30000


script = QiehaoScript()
