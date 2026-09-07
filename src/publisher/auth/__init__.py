"""鉴权与访问控制（文档第 52 节）。

Web 登录态 + API Key 校验 + allow_override_review 权限位。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import APIKey
from ..security import hash_secret


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    """简单的内存 + 签名 session token（个人本地部署适用）。"""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {
            "username": username,
            "expires": time.time() + settings.session_max_age,
        }
        return token

    def validate(self, token: str | None) -> dict | None:
        if not token:
            return None
        sess = self._sessions.get(token)
        if not sess:
            return None
        if sess["expires"] < time.time():
            self._sessions.pop(token, None)
            return None
        return sess

    def revoke(self, token: str) -> None:
        self._sessions.pop(token, None)


session_store = SessionStore()


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def login(self, username: str, password: str) -> str | None:
        # 恒定时间比较，避免时序攻击
        if not hmac.compare_digest(username, settings.admin_username):
            return None
        if not hmac.compare_digest(password, settings.admin_password):
            return None
        return session_store.create_session(username)

    def logout(self, token: str) -> None:
        session_store.revoke(token)

    # ---- API Key ----

    def create_api_key(
        self, name: str, allow_override_review: bool = False
    ) -> tuple[str, str]:
        """生成 Access Key / Secret Key 密钥对。

        - Access Key（ak_...）：明文标识，存库可展示；
        - Secret Key（sk_...）：仅此一次返回明文，库里只存哈希。
        API 调用时使用完整凭证 "ak_...:sk_..." 作为 Bearer。
        """
        access_key = f"ak_{secrets.token_urlsafe(9)}"
        secret_key = f"sk_{secrets.token_urlsafe(24)}"
        key = APIKey(
            name=name,
            access_key=access_key,
            key_hash=hash_secret(secret_key),
            allow_override_review=allow_override_review,
        )
        self.session.add(key)
        self.session.commit()
        return access_key, secret_key

    def validate_api_key(self, raw: str) -> APIKey | None:
        """校验凭证。支持：
        - "ak_...:sk_..."（Access Key 定位 + Secret Key 哈希比对）
        - 旧格式单 token（pk_... / sk_...，直接哈希直查）
        """
        key: APIKey | None = None
        if raw.startswith("ak_") and ":" in raw:
            ak, sk = raw.split(":", 1)
            key = self.session.scalar(
                select(APIKey).where(APIKey.access_key == ak)
            )
            if not key or not hmac.compare_digest(
                hash_secret(sk), key.key_hash
            ):
                return None
        else:
            key = self.session.scalar(
                select(APIKey).where(APIKey.key_hash == hash_secret(raw))
            )
        if not key:
            return None
        key.last_used_at = _utcnow()
        self.session.commit()
        return key

    def delete_api_key(self, key_id: int) -> None:
        key = self.session.get(APIKey, key_id)
        if key:
            self.session.delete(key)
            self.session.commit()

    def list_api_keys(self) -> list[APIKey]:
        return list(self.session.scalars(select(APIKey).order_by(APIKey.id)))


def has_override_review_permission(api_key: APIKey | None) -> bool:
    """是否具备突破下限的权限"""
    return bool(api_key and api_key.allow_override_review)