"""内容安全兜底检测（文档第 55 节）。

独立于 review_policy，即使 review=never 也生效，除非用户在 Settings 关闭。
命中则转入 waiting_manual 而不是强行发布或失败。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from ..models import ReviewPolicy

# 默认违禁词库（可配置，存于 settings 表或 data 目录）
_DEFAULT_WORDS = [
    "赌博",
    "色情",
    "违禁品",
    "欺诈",
]

_CUSTOM_WORDS_FILE = Path("data") / "banned_words.json"


def load_banned_words() -> list[str]:
    words = list(_DEFAULT_WORDS)
    try:
        if _CUSTOM_WORDS_FILE.exists():
            data = json.loads(_CUSTOM_WORDS_FILE.read_text(encoding="utf-8"))
            words.extend(data.get("words", []))
    except Exception:
        pass
    return words


def check_content_safety(content: str, title: str = "") -> tuple[bool, list[str]]:
    """返回 (是否通过, 命中词列表)。"""
    if not settings.content_safety_enabled:
        return True, []
    words = load_banned_words()
    text = f"{title}\n{content}"
    hits = [w for w in words if w and w in text]
    return (len(hits) == 0, hits)