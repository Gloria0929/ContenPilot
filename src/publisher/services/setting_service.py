"""运行时设置（§47 settings 表）。

内容安全兜底开关（§55）：环境变量是出厂默认，settings 表中的值优先；
Web Settings 页修改即写这张表。
"""
from __future__ import annotations

import os

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
    # ---- AI 生产引擎（内容工坊全局驱动配置） ----
    # 取值优先级与 ai.get_provider 一致：settings 表 > 环境变量 > 出厂默认。
    "ai_provider": {
        "type": "str",
        "label": "AI 生产引擎",
        "description": "内容工坊生成内容的默认引擎：openai = ChatGPT / OpenAI 兼容 API；ollama = 本地或远程 Ollama。",
        "fallback": lambda: os.environ.get("PUBLISHER_AI_PROVIDER", "openai"),
    },
    "openai_base_url": {
        "type": "str",
        "label": "OpenAI API 地址",
        "description": "OpenAI 兼容服务的 Base URL，如 https://api.openai.com/v1 或自建反代 / 中转地址。",
        "fallback": lambda: os.environ.get("PUBLISHER_AI_BASE_URL", "https://api.openai.com/v1"),
    },
    "openai_api_key": {
        "type": "str",
        "label": "OpenAI API Key",
        "description": "ChatGPT / OpenAI 兼容服务的密钥（sk-...）。留空表示继续使用环境变量中的值。",
        "fallback": lambda: os.environ.get("OPENAI_API_KEY", ""),
    },
    "openai_model": {
        "type": "str",
        "label": "OpenAI 模型",
        "description": "如 gpt-4o-mini / gpt-4o，或兼容服务提供的模型名。",
        "fallback": lambda: os.environ.get("PUBLISHER_AI_MODEL", "gpt-4o-mini"),
    },
    "ollama_base_url": {
        "type": "str",
        "label": "Ollama 服务地址",
        "description": "本地 http://localhost:11434 或远程 http://<IP>:11434。",
        "fallback": lambda: os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    },
    "ollama_model": {
        "type": "str",
        "label": "Ollama 模型",
        "description": "已拉取的模型名，如 qwen2.5 / llama3.1 / deepseek-r1。",
        "fallback": lambda: os.environ.get("OLLAMA_MODEL", "qwen2.5"),
    },
}
