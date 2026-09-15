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
from typing import Any

from ..ai import get_provider

logger = logging.getLogger(__name__)


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
    try:
        # 获取对应的 Provider（ChatGPT 或 本地/远程 Ollama）
        provider = get_provider(
            name=provider_type,
            base_url=ollama_url if provider_type == "ollama" else None,
            model=ollama_model if provider_type == "ollama" else None,
            session=session,
        )
        raw = await provider.generate(prompt)

        clean = raw.strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
        items = json.loads(clean)
        if isinstance(items, list) and len(items) > 0:
            # 补齐 id
            for idx, item in enumerate(items):
                if not item.get("id"):
                    item["id"] = idx + 1
            return items
    except Exception as e:
        engine_label = f"Ollama ({ollama_url or '默认'})" if provider_type == "ollama" else "ChatGPT"
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
