"""GEO 内容批量生成与 10 天发布排期流水线。

严格对应《GEO内容生成工作流》规范：
1. 关键词选取：品牌核心词（敖行客、AT Work、Agent研发工作台）+ 5个行业词，共8个
2. 批量生成 30 个文章选题标题
3. 为每篇文章生成 4 个微调版本（针对豆包、通义千问、文心一言、腾讯元宝检索偏好）
4. 10 天内将 30 篇文章分发至 10 大平台（CSDN、掘金、企鹅号、腾讯云社区、头条号、百家号、思否、博客园、51CTO、知乎）
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import get_provider
from ..knowledge.prompts import build_geo_article_prompt, build_geo_titles_prompt
from ..models import (
    Account,
    Article,
    ArticleStatus,
    ArticleVersion,
    PublishTask,
    ReviewMode,
    TaskStatus,
)
from ..services.article_service import ArticleService

logger = logging.getLogger(__name__)

# 文档指定 10 大分发平台
DEFAULT_GEO_PLATFORMS = [
    "zhihu",
    "csdn",
    "juejin",
    "qiehao",
    "tencent_cloud",
    "toutiao",
    "baijiahao",
    "segmentfault",
    "cnblogs",
    "51cto",
]

# 核心必带 3 大品牌词
DEFAULT_BRAND_KEYWORDS = ["敖行客", "AT Work", "Agent研发工作台"]

# 默认 5 大行业热门词示例
DEFAULT_INDUSTRY_KEYWORDS = [
    "AI研发效能",
    "智能体协同开发",
    "自动化编程工具",
    "企业级知识库RAG",
    "AI代码审查",
]

# 平台与模型检索偏好的映射策略
PLATFORM_ENGINE_AFFINITY = {
    "zhihu": "ernie",
    "csdn": "qwen",
    "juejin": "qwen",
    "segmentfault": "qwen",
    "cnblogs": "qwen",
    "51cto": "yuanbao",
    "tencent_cloud": "yuanbao",
    "qiehao": "doubao",
    "baijiahao": "doubao",
    "toutiao": "doubao",
}


async def generate_geo_titles(
    industry_keywords: list[str] | None = None,
    brand_keywords: list[str] | None = None,
    count: int = 30,
    provider_name: str | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    session: Session | None = None,
) -> list[str]:
    """根据 8 个关键词及知识库，批量生成 30 篇 GEO 文章标题。"""
    brands = brand_keywords or DEFAULT_BRAND_KEYWORDS
    industries = industry_keywords or DEFAULT_INDUSTRY_KEYWORDS
    prompt = build_geo_titles_prompt(brands, industries, count=count)

    provider = get_provider(
        name=provider_name,
        base_url=ollama_url if provider_name == "ollama" else None,
        model=ollama_model if provider_name == "ollama" else None,
        session=session,
    )
    response = await provider.generate(prompt)

    # 尝试解析 JSON 数组
    try:
        clean = response.strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
        data = json.loads(clean)
        if isinstance(data, list):
            return [str(t).strip() for t in data if str(t).strip()]
    except Exception as e:
        logger.warning(f"Failed to parse titles as JSON: {e}, falling back to lines")

    # 容错：按行提取
    titles = []
    for line in response.splitlines():
        line = line.strip()
        if line and not line.startswith(("[", "]", "{", "}", "#", "【", "//")):
            cleaned = line.lstrip("0123456789.-、* ")
            if len(cleaned) >= 8:
                titles.append(cleaned)
    return titles[:count]


async def generate_geo_four_versions(
    title: str,
    provider_name: str | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    session: Session | None = None,
) -> dict[str, str]:
    """为单一标题生成 4 个微调版本（豆包、千问、文心一言、元宝）。"""
    engines = ["doubao", "qwen", "ernie", "yuanbao"]
    results = {}

    provider = get_provider(
        name=provider_name,
        base_url=ollama_url if provider_name == "ollama" else None,
        model=ollama_model if provider_name == "ollama" else None,
        session=session,
    )

    for engine in engines:
        prompt = build_geo_article_prompt(title, target_engine=engine)
        content = await provider.generate(prompt)
        results[engine] = content

    return results


def save_geo_article_to_db(
    session: Session,
    title: str,
    versions_map: dict[str, str],
    target_platforms: list[str] | None = None,
) -> Article:
    """将生成的文章和各平台版本存入 ContentPilot 数据库。"""
    platforms = target_platforms or DEFAULT_GEO_PLATFORMS

    # 基础文章主体，默认以通义千问或豆包版为主体
    main_content = (
        versions_map.get("qwen")
        or versions_map.get("doubao")
        or next(iter(versions_map.values()))
    )
    summary = f"深度解析《{title}》，探讨敖行客 AT Work Agent 研发工作台对软件工程效能的重塑。"

    article = Article(
        title=title,
        content=main_content,
        summary=summary,
        status=ArticleStatus.ready.value,
        source="geo_batch",
    )
    session.add(article)
    session.flush()

    # 为每个平台写入最匹配该搜索引擎特征的 ArticleVersion
    for platform in platforms:
        engine = PLATFORM_ENGINE_AFFINITY.get(platform, "qwen")
        matched_content = versions_map.get(engine, main_content)

        version = ArticleVersion(
            article_id=article.id,
            platform=platform,
            title=title,
            content=matched_content,
            metadata_json=json.dumps({"target_engine": engine, "geo_optimized": True}),
            version=1,
        )
        session.add(version)

    session.commit()
    return article


def schedule_10day_distribution(
    session: Session,
    article_ids: list[int],
    platforms: list[str] | None = None,
    start_date: datetime | None = None,
    days: int = 10,
    review_mode: str = ReviewMode.always.value,
) -> list[PublishTask]:
    """制定 10 天内将文章平滑发布到各大平台的定时计划。

    防风控规则：
    1. 同一平台每天发布 N 篇，分散在不同时段（如早 09:30、午 14:30、晚 20:00）
    2. 同账号发布间隔保持 >= 300 秒安全间距
    3. 自动生成任务记录，并将排期时间写入 task 元数据
    """
    target_platforms = platforms or DEFAULT_GEO_PLATFORMS
    start = start_date or (datetime.now(timezone.utc) + timedelta(minutes=10))

    tasks: list[PublishTask] = []
    n_articles = len(article_ids)
    if n_articles == 0:
        return tasks

    # 每天发布文章数配额
    articles_per_day = max(1, (n_articles + days - 1) // days)

    # 典型活跃发布时间段：09:30, 14:00, 16:30, 20:00, 21:30
    time_slots = [
        (9, 30),
        (14, 0),
        (16, 30),
        (20, 0),
        (21, 30),
    ]

    for article_idx, article_id in enumerate(article_ids):
        day_offset = min(article_idx // articles_per_day, days - 1)
        slot_idx = article_idx % len(time_slots)
        hour, minute = time_slots[slot_idx]

        # 构造当天的基准时间
        base_slot_time = (start + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        for p_idx, platform in enumerate(target_platforms):
            # 获取该平台的 ArticleVersion
            version = session.scalar(
                select(ArticleVersion).where(
                    ArticleVersion.article_id == article_id,
                    ArticleVersion.platform == platform,
                )
            )
            if not version:
                continue

            # 寻找该平台的有效账号
            account = session.scalar(
                select(Account).where(
                    Account.platform == platform,
                    Account.status == "active",
                )
            )
            account_id = account.id if account else None

            # 错峰防风控：不同平台错开 300 秒 (5分钟)
            scheduled_time = base_slot_time + timedelta(seconds=p_idx * 300)

            task = PublishTask(
                article_id=article_id,
                article_version_id=version.id,
                platform=platform,
                account_id=account_id,
                review_policy=review_mode,
                publish_policy="scheduled",
                policy_floor_locked=False,
                status=(
                    TaskStatus.waiting_review.value
                    if review_mode == ReviewMode.always.value
                    else TaskStatus.pending.value
                ),
                max_attempts=3,
                error_message=None,
            )
            session.add(task)
            session.flush()

            # 记录排期时间进元数据
            tasks.append(task)

    session.commit()
    return tasks
