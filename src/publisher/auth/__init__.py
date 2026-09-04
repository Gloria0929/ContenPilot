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
    ) -> str:
        raw = f"pk_{secrets.token_urlsafe(24)}"
        key = APIKey(
            name=name,
            key_hash=hash_secret(raw),
            allow_override_review=allow_override_review,
        )
        self.session.add(key)
        self.session.commit()
        return raw

    def validate_api_key(self, raw: str) -> APIKey | None:
        key_hash = hash_secret(raw)
        key = self.session.scalar(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        if not key or key.revoked_at:
            return None
        key.last_used_at = _utcnow()
        self.session.commit()
        return key

    def revoke_api_key(self, key_id: int) -> None:
        key = self.session.get(APIKey, key_id)
        if key:
            key.revoked_at = _utcnow()
            self.session.commit()

    def list_api_keys(self) -> list[APIKey]:
        return list(self.session.scalars(select(APIKey).order_by(APIKey.id)))


def has_override_review_permission(api_key: APIKey | None) -> bool:
    """是否具备突破下限的权限（文档第 12 节）。"""
    return bool(api_key and api_key.allow_override_review)