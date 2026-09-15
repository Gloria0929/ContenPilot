"""今日头条 / 头条号浏览器发布脚本。

创作地址：https://mp.toutiao.com/profile_v4/graphic/publish
流程：填标题 → 填正文 → 点「发布」→ 确认发布 → 轮询确认。
"""
from __future__ import annotations

from ._common import CommonScript


class ToutiaoScript(CommonScript):
    platform = "toutiao"
    creator_url = "https://mp.toutiao.com/profile_v4/graphic/publish"
    manual_keywords = ("安全验证", "验证码", "实名认证", "滑块验证")

    TITLE_SELECTORS = (
        "textarea[placeholder*='标题']",
        "input[placeholder*='标题']",
        ".byte-input input",
    )
    EDITOR_SELECTORS = (
        ".ProseMirror",
        "div[contenteditable='true']",
        ".editor-comp",
    )
    PUBLISH_TEXTS = ("发布",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "存草稿")
    CONFIRM_TEXTS = ("确认发布", "确定", "发布")
    CONFIRM_EXCLUDE = ("取消", "定时")
    DRAFT_TEXTS = ("存草稿", "保存草稿")
    SUCCESS_URL_MARKS = ("/graphic/manage", "/profile_v4/graphic/publish?from=success")
    SUCCESS_TEXTS = ("发布成功", "已发布", "提交成功")
    LOGIN_URL_MARKS = ("login", "sso.toutiao.com")
    LOGIN_TEXTS = ("扫码登录", "账号密码登录", "手机验证码登录")
    CONFIRM_TIMEOUT_MS = 30000


script = ToutiaoScript()
