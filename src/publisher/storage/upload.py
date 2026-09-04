"""存储辅助：上传文件保存。"""
from __future__ import annotations

import uuid
from pathlib import Path

from ..config import settings
from ..database import SessionLocal
from ..models import Media


def save_upload(filename: str, data: bytes, content_type: str = "") -> Media:
    settings.ensure_dirs()
    ext = Path(filename).suffix
    stored = Path(settings.uploads_dir) / f"{uuid.uuid4().hex}{ext}"
    stored.write_bytes(data)
    media = Media(
        filename=filename,
        path=str(stored),
        content_type=content_type,
        size=len(data),
    )
    session = SessionLocal()
    try:
        session.add(media)
        session.commit()
    finally:
        session.close()
    return media