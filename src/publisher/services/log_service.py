"""日志服务：所有日志写入前先经过脱敏中间件。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import PublishLog
from ..security import redact_json


class LogService:
    def __init__(self, session: Session):
        self.session = session

    def log(
        self,
        event: str,
        task_id: int | None = None,
        level: str = "info",
        message: str = "",
        metadata: dict | None = None,
    ) -> PublishLog:
        entry = PublishLog(
            task_id=task_id,
            level=level,
            event=event,
            message=message,
            metadata=redact_json(metadata or {}),
        )
        self.session.add(entry)
        self.session.commit()
        return entry

    def policy_override(
        self,
        task_id: int | None,
        message: str,
        metadata: dict | None = None,
    ) -> PublishLog:
        """审计日志：突破下限授权时必须记录。"""
        return self.log(
            "policy_override",
            task_id=task_id,
            level="warning",
            message=message,
            metadata=metadata,
        )