"""微信公众平台（wechat_mp）平台 Adapter。

支持两种模式：
1. 官方草稿箱 API（推荐，稳定免风控）：通过 AppID + AppSecret 调用
   `POST /cgi-bin/draft/add` 接口，直接将排版后的富文本推入公众号草稿箱。
2. 凭据加密存储于 account.encrypted_credentials：
   {"appid": "...", "secret": "...", "author": "敖行客", "thumb_media_id": "..."}
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from cryptography.fernet import InvalidToken

from ..base import PlatformAdapter, PublishResult
from ..registry import register
from ...renderers import render_wechat_article
from ...security import decrypt_json


class WechatMpError(Exception):
    """微信公众平台 API 调用异常。"""


@register("wechat_mp")
class WechatMpAdapter(PlatformAdapter):
    platform = "wechat_mp"
    mode = "api"  # 官方草稿箱 API，不占用浏览器锁

    @staticmethod
    def _credentials(account) -> dict[str, Any]:
        if account is None or not getattr(account, "encrypted_credentials", None):
            raise WechatMpError(
                "账号缺少微信公众号凭据，请录入包含 appid 与 secret 的 JSON 凭据。"
            )
        try:
            return decrypt_json(account.encrypted_credentials)
        except InvalidToken:
            raise WechatMpError("凭据解密失败：加密密钥已变更，请重新录入公众号凭据。")

    async def capabilities(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "mode": self.mode,
            "supports_text": True,
            "supports_images": True,
            "supports_video": False,
            "supports_draft": True,
            "supports_publish": True,  # 将草稿推入草稿箱即视为完成自动化交付
            "supports_status": False,
        }

    async def check_account(self, account) -> bool:
        try:
            creds = self._credentials(account)
            token = await self._get_access_token(creds["appid"], creds["secret"])
            return bool(token)
        except Exception:
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

    async def _get_access_token(self, appid: str, secret: str) -> str:
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if "access_token" in data:
                return data["access_token"]
            raise WechatMpError(f"获取微信 AccessToken 失败: {data.get('errmsg', resp.text)}")

    async def create_draft(self, content, account=None, task_id=None) -> PublishResult:
        return await self._push_to_draft_box(content, account)

    async def publish(self, content, account=None, task_id=None) -> PublishResult:
        # 微信公众号群发通常需要管理员扫码，根据合规与风控，推送到草稿箱即为自动化发布的终点
        return await self._push_to_draft_box(content, account)

    async def _push_to_draft_box(self, content, account) -> PublishResult:
        try:
            creds = self._credentials(account)
        except WechatMpError as e:
            return PublishResult(success=False, error_code="account_credentials_missing", error_message=str(e))

        errors = await self.validate(content)
        if errors:
            return PublishResult(success=False, error_code="content_invalid", error_message="; ".join(errors))

        # 检查是否已经是排版好的 HTML
        body_text = content.content
        if not body_text.strip().startswith("<section") and not body_text.strip().startswith("<div"):
            body_html = render_wechat_article(
                body_text,
                title=content.title,
                digest=getattr(content, "summary", "") or "",
                theme="graphite",
            )
        else:
            body_html = body_text

        try:
            token = await self._get_access_token(creds["appid"], creds["secret"])
            draft_url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"

            payload = {
                "articles": [
                    {
                        "title": content.title,
                        "author": creds.get("author", "敖行客"),
                        "digest": getattr(content, "summary", "")[:120] if getattr(content, "summary", "") else "",
                        "content": body_html,
                        "thumb_media_id": creds.get("thumb_media_id", ""),
                        "need_open_comment": 1,
                        "only_fans_can_comment": 0,
                    }
                ]
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(draft_url, json=payload)
                data = resp.json()
                if data.get("errcode", 0) == 0 and "media_id" in data:
                    media_id = data["media_id"]
                    return PublishResult(
                        success=True,
                        remote_id=media_id,
                        remote_url="https://mp.weixin.qq.com",
                    )
                return PublishResult(
                    success=False,
                    error_code="wechat_api_error",
                    error_message=f"微信草稿箱接口报错: {data.get('errmsg', resp.text)}",
                )
        except Exception as e:
            return PublishResult(
                success=False,
                error_code="wechat_network_error",
                error_message=str(e),
            )

    async def get_status(self, remote_id: str) -> dict[str, Any]:
        return {}

    async def cancel(self, task) -> bool:
        return False
