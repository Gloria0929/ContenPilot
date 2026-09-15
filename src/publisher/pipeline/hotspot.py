"""每日技术热点聚合与筛选模块。

对应文档需求：
“每日定时任务：早上9点搜集当天行业新闻热点信息。
结合国内和海外的AI搜集结果，选出 2-3 个与软件开发行业 / AT Work 产品关联度最高的热点。”

支持双引擎驱动：
1. ChatGPT (OpenAI API)：自动获取全球科技动态与深度行业事实；
2. 本地或远程 Ollama：支持局域网或本地算力（如 qwen2.5 / llama3.1 / deepseek-r1 等模型）离线聚合热点。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..ai import OllamaProvider, OpenAICompatProvider, get_provider

logger = logging.getLogger(__name__)


def _provider_label(provider) -> str:
    """根据实际 Provider 实例显示引擎，不能根据是否传参猜测。"""
    model = getattr(provider, "model", "")
    suffix = f"（模型 {model}）" if model else ""
    if isinstance(provider, OllamaProvider):
        return f"Ollama{suffix}"
    if isinstance(provider, OpenAICompatProvider):
        return f"OpenAI 兼容服务{suffix}"
    return f"{provider.__class__.__name__}{suffix}"


def _parse_hotspot_items(raw: str) -> list[dict[str, Any]]:
    """解析代码块或夹带说明文字的热点 JSON 数组。"""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("AI 返回内容为空")

    clean = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", clean, re.IGNORECASE | re.DOTALL)
    candidates = [fenced.group(1).strip(), clean] if fenced else [clean]
    decoder = json.JSONDecoder()
    last_error: Exception | None = None

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            data = None
            for match in re.finditer(r"\[", candidate):
                try:
                    data, _ = decoder.raw_decode(candidate[match.start():])
                    break
                except json.JSONDecodeError as nested_exc:
                    last_error = nested_exc
        if not isinstance(data, list):
            continue

        items: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if not str(item.get("title") or "").strip() or not str(
                item.get("summary") or ""
            ).strip():
                continue
            normalized = dict(item)
            normalized["id"] = normalized.get("id") or len(items) + 1
            items.append(normalized)
        if items:
            return items

    if last_error:
        raise last_error
    raise ValueError("AI 返回内容不是有效的热点 JSON 数组")


def _repair_prompt(raw: str) -> str:
    return f"""请将下面内容修复为合法 JSON 数组。
只修复 JSON 语法和字段结构，不增加事实，不输出 Markdown 或解释。
每项必须包含 id、title、summary、conflict_point、relevance_angle。

待修复内容：
{raw[:12000]}
"""


async def fetch_daily_hotspots(
    provider_type: str | None = None,  # "openai" (ChatGPT) 或 "ollama"
    ollama_url: str | None = None,      # 本地 http://localhost:11434 或远程 http://IP:11434
    ollama_model: str | None = None,    # 如 qwen2.5 / llama3.1
    session=None,
    custom_sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    """搜集当天全球及国内软件研发与 AI 领域的行业技术热点。

    支持通过 ChatGPT (OpenAI) 自动抓取生成，同时支持本地或远程 Ollama。
    """
    prompt = """请作为顶级科技资讯分析专家，整理今天在国内外技术与软件工程圈（Hacker News、GitHub Trending、技术博客及AI前沿领域）最受关注的 4 个重磅热点。
    特别聚焦于：大模型工程落地、AI Agent 智能体协同研发、自动化编程与代码审查、研发效能提升。

    请为每个热点提供：
    1. 标题 (title): 引人注目的技术新闻或观点标题
    2. 事件简述与事实出处 (summary): 100字左右的事实概括
    3. 核心概念冲突点或争议焦点 (conflict_point): 传统模式 vs AI/Agent 模式的剧烈对抗点
    4. 与「研发效能 / Agent工作台 / 敖行客 AT Work」的结合角度 (relevance_angle)

    请以严格的 JSON 数组格式直接输出，不要附带多余文字说明：
    [
    {
        "id": 1,
        "title": "热点标题",
        "summary": "热点事件简述...",
        "conflict_point": "概念冲突与争议...",
        "relevance_angle": "如何与AT Work研发工作台结合..."
    }
    ]
"""
    engine_label = provider_type or "当前配置的 AI 引擎"
    try:
        # 获取对应的 Provider（ChatGPT 或 本地/远程 Ollama）
        provider = get_provider(
            name=provider_type,
            base_url=ollama_url if provider_type == "ollama" else None,
            model=ollama_model if provider_type == "ollama" else None,
            session=session,
        )
        engine_label = _provider_label(provider)
        logger.info("使用 %s生成最新热点", engine_label)
        raw = await provider.generate(prompt)
        try:
            return _parse_hotspot_items(raw)
        except (json.JSONDecodeError, TypeError, ValueError) as first_error:
            logger.info(
                "%s首次返回结构无效，使用同一引擎修复 JSON：%s",
                engine_label,
                first_error,
            )
            repaired = await provider.generate(_repair_prompt(raw))
            return _parse_hotspot_items(repaired)
    except Exception as e:
        logger.warning(f"通过 {engine_label} 抓取最新热点未返回有效结构 ({e})，返回空列表")
        # 默认为空：不再用本地写死的精选热点兜底，前端展示空状态引导配置引擎
        return []


async def select_top_hotspots(
    count: int = 2,
    provider_type: str | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
) -> list[dict[str, Any]]:
    """筛选出 2~3 个与产品关联度最高的热点。"""
    hotspots = await fetch_daily_hotspots(
        provider_type=provider_type,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
    )
    return hotspots[:count]
