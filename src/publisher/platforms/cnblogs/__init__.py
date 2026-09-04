"""博客园平台 Adapter（官方 MetaWeblog XML-RPC API）。

对应文档 §2.3（官方 API 优先）、§26（发布成功确认）、§69（API Platform x1）。
博客园提供稳定的 MetaWeblog API：
- Endpoint: https://rpc.cnblogs.com/metaweblog/{blog_name}
- 用户名 = 博客园登录用户名；密码 = MetaWeblog 访问令牌（即用户手中的 API Key）

凭据以 Fernet 加密存放在账号 encrypted_credentials（§53）：
    {"username": "...", "token": "...", "blog_name": "..."}

发布确认（§26）：newPost 返回 postid 即官方 API 的成功确认，
再通过 getPost 换取真实文章链接作为 remote_url，无法取得时回退拼接链接。
"""
from __future__ import annotations

import asyncio
import xmlrpc.client
from typing import Any

from ..base import PlatformAdapter, PublishResult
from ..registry import register
from ...security import decrypt_json


class CnblogsError(Exception):
    """博客园 API 调用失败。"""


def _md_to_html(text: str) -> str:
    """Markdown → HTML。已是 HTML 的内容原样返回（避免二次转换）。"""
    import re

    if not text:
        return text
    # 粗判已含块级 HTML 标签 → 视为 HTML，不再转换
    if re.search(r"<(p|h[1-6]|ul|ol|table|div|blockquote)\b", text, re.I):
        return text
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark").enable("table").render(text)


@register("cnblogs")
class CnblogsAdapter(PlatformAdapter):
    platform = "cnblogs"
    mode = "api"  # 官方 MetaWeblog API，不占用账号浏览器锁（§50）
    RPC_BASE = "https://rpc.cnblogs.com/metaweblog"

    # ---- 凭据与 RPC 客户端 ----

    @staticmethod
    def _credentials(account) -> dict:
        if account is None or not getattr(account, "encrypted_credentials", None):
            raise CnblogsError(
                "账号缺少博客园凭据，请执行: publisher account add cnblogs --username <用户名> "
                "--token <MetaWeblog访问令牌> --blog-name <博客名>"
            )
        data = decrypt_json(account.encrypted_credentials)
        for field in ("username", "token", "blog_name"):
            if not data.get(field):
                raise CnblogsError(f"博客园凭据缺少 {field}")
        return data

    def _client(self, blog_name: str) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(
            f"{self.RPC_BASE}/{blog_name}", allow_none=True
        )

    async def _call(self, blog_name: str, method: str, *args):
        """同步 XML-RPC 调用放到线程，避免阻塞事件循环。

        method 形如 "metaWeblog.newPost"，逐段解析以同时兼容
        真实 ServerProxy 与测试替身。
        """

        def _invoke():
            target = self._client(blog_name)
            for part in method.split("."):
                target = getattr(target, part)
            return target(*args)

        try:
            return await asyncio.to_thread(_invoke)
        except xmlrpc.client.Fault as e:
            raise CnblogsError(f"cnblogs api fault {e.faultCode}: {e.faultString}") from e
        except xmlrpc.client.ProtocolError as e:
            raise CnblogsError(f"cnblogs api protocol error: {e.errmsg}") from e
        except OSError as e:
            raise CnblogsError(f"cnblogs api network error: {e}") from e

    # ---- PlatformAdapter 接口 ----

    async def capabilities(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "mode": self.mode,
            "supports_text": True,
            "supports_images": False,  # MetaWeblog 图片需 media 媒体接口，V1 暂不支持
            "supports_video": False,
            "supports_draft": True,
            "supports_publish": True,
            "supports_status": True,
        }

    async def check_account(self, account) -> bool:
        try:
            creds = self._credentials(account)
            blogs = await self._call(
                creds["blog_name"],
                "blogger.getUsersBlogs",
                "publisher",
                creds["username"],
                creds["token"],
            )
            return bool(blogs)
        except CnblogsError:
            return False

    async def authorize(self, account) -> bool:
        return await self.check_account(account)

    async def validate(self, content) -> list[str]:
        errors = []
        if not getattr(content, "title", "").strip():
            errors.append("title required")
        if not getattr(content, "content", "").strip():
            errors.append("content required")
        return errors

    async def create_draft(self, content, account=None, task_id=None) -> PublishResult:
        return await self._new_post(content, account, publish=False)

    async def publish(self, content, account=None, task_id=None) -> PublishResult:
        return await self._new_post(content, account, publish=True)

    async def get_status(self, remote_id: str) -> dict[str, Any]:
        # 需要 account 上下文才能调用，接口签名保持 §31 最小形态；
        # 发布确认已在 publish() 内通过 getPost 完成（§26）。
        return {}

    async def cancel(self, task) -> bool:
        # 博客园 API 删除已发布文章风险大，V1 不提供取消
        return False

    # ---- 发布核心 ----

    async def _new_post(self, content, account, publish: bool) -> PublishResult:
        try:
            creds = self._credentials(account)
        except CnblogsError as e:
            return PublishResult(success=False, error_code="account_credentials_missing", error_message=str(e))

        errors = await self.validate(content)
        if errors:
            return PublishResult(success=False, error_code="content_invalid", error_message="; ".join(errors))

        post = {
            "title": content.title,
            # MetaWeblog description 按 HTML 渲染：Markdown 先转 HTML，否则原文显示
            "description": _md_to_html(content.content),
            "categories": [],
        }
        try:
            postid = await self._call(
                creds["blog_name"],
                "metaWeblog.newPost",
                creds["blog_name"],
                creds["username"],
                creds["token"],
                post,
                publish,
            )
            postid = str(postid)
        except CnblogsError as e:
            return PublishResult(success=False, error_code="cnblogs_api_error", error_message=str(e))

        # 远程确认：getPost 换取真实链接（§26）
        remote_url = None
        try:
            info = await self._call(
                creds["blog_name"],
                "metaWeblog.getPost",
                postid,
                creds["username"],
                creds["token"],
            )
            remote_url = (info or {}).get("link")
        except CnblogsError:
            pass
        if not remote_url:
            remote_url = f"https://www.cnblogs.com/{creds['blog_name']}/p/{postid}.html"
        # getPost 返回的 link 可能不带 .html（会 301），统一补齐
        if remote_url and not remote_url.rstrip("/").endswith(".html"):
            remote_url = remote_url.rstrip("/") + ".html"

        return PublishResult(success=True, remote_id=postid, remote_url=remote_url)
