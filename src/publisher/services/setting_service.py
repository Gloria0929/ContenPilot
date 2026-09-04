"""运行时设置（§47 settings 表）。

内容安全兜底开关（§55）：环境变量是出厂默认，settings 表中的值优先；
Web Settings 页修改即写这张表。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings as app_settings
from ..models import Setting


def get_setting(session: Session, key: str, default: str = "") -> str:
    row = session.get(Setting, key)
    return row.value if row else default


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


def content_safety_enabled(session: Session) -> bool:
    """内容安全兜底是否开启（§55）：表值优先，缺省回退环境变量默认。"""
    v = get_setting(session, "content_safety_enabled")
    if v == "":
        return app_settings.content_safety_enabled
    return v == "true"


# Web 可修改的设置项清单（Settings 页动态渲染）
EDITABLE_SETTINGS = {
    "content_safety_enabled": {
        "type": "bool",
        "label": "内容安全兜底检测",
        "description": "发布前的违禁词检测；命中转入等待人工而非直接发布。关闭前请确认全自动链路的内容质量。",
        "fallback": lambda: app_settings.content_safety_enabled,
    },
}
