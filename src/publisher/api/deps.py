"""FastAPI 依赖注入：数据库会话 + 鉴权。"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from ..auth import AuthService, has_override_review_permission, session_store
from ..database import SessionLocal
from ..models import APIKey


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def get_current_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> dict:
    """返回鉴权上下文。优先级：API Key > Session Cookie。"""
    # Session cookie（Web 登录态）
    token = request.cookies.get("session")
    sess = session_store.validate(token)
    if sess:
        return {"username": sess["username"], "source": "session", "api_key": None}

    # API Key
    bearer = _extract_bearer(authorization)
    if bearer:
        auth = AuthService(db)
        key = auth.validate_api_key(bearer)
        if key:
            return {"username": key.name, "source": "api_key", "api_key": key}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def require_override_review(auth=Depends(get_current_auth)) -> APIKey | None:
    """用于 --no-review 类操作：需要 allow_override_review 权限位。"""
    if auth["source"] == "session":
        # Web 管理员默认具备（人类显式操作）
        return None
    key: APIKey | None = auth.get("api_key")
    if has_override_review_permission(key):
        return key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="requires allow_override_review permission",
    )


def auth_to_requester(auth: dict) -> str:
    return auth.get("username") or auth.get("source") or "unknown"