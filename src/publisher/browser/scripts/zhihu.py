"""知乎专栏/文章浏览器发布脚本。

知乎专栏创作地址：https://zhuanlan.zhihu.com/write
流程：填标题 → 填富文本正文 → 点「发布」→ 确认发布 → 轮询跳转文章详情页。
"""
from __future__ import annotations

from ._common import CommonScript


class ZhihuScript(CommonScript):
    platform = "zhihu"
    creator_url = "https://zhuanlan.zhihu.com/write"
    manual_keywords = ("安全验证", "验证码", "请进行人机验证", "短信验证")

    TITLE_SELECTORS = (
        "textarea[placeholder*='标题']",
        "input[placeholder*='请输入标题']",
        ".WriteIndex-titleInput textarea",
    )
    EDITOR_SELECTORS = (
        ".DraftEditor-root",
        ".public-DraftEditor-content",
        "div[contenteditable='true']",
    )
    PUBLISH_TEXTS = ("发布", "下一步")
    PUBLISH_EXCLUDE = ("草稿", "取消", "定时")
    CONFIRM_TEXTS = ("确认发布", "发布")
    CONFIRM_EXCLUDE = ("取消",)
    DRAFT_TEXTS = ("保存草稿", "保存")
    SUCCESS_URL_MARKS = ("/p/", "zhuanlan.zhihu.com/p/")
    SUCCESS_TEXTS = ("发布成功", "文章已发布")
    LOGIN_URL_MARKS = ("signin", "login", "passport")
    LOGIN_TEXTS = ("密码登录", "短信登录", "微信登录", "扫码登录")
    CONFIRM_TIMEOUT_MS = 30000


script = ZhihuScript()
