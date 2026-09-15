"""微信公众号文章与贴图内容流水线。

涵盖：
1. 热点提炼与文章内容生成（结合研发痛点与 AT Work）
2. 5 个传播级公众号标题候选生成
3. 自动排版（调用 wechat_renderer，支持石墨极简、摸鱼绿等6种样式）
4. 贴图内容派生（300字文案 + 3:4醒目标题封面生图Prompt）
5. 存入 ContentPilot 库并生成可直接同步至微信草稿箱的数据
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..ai import get_provider
from ..knowledge.prompts import (
    build_wechat_article_prompt,
    build_wechat_poster_prompt,
    build_wechat_titles_prompt,
)
from ..models import Article, ArticleStatus, ArticleVersion
from ..renderers import render_wechat_article

logger = logging.getLogger(__name__)


async def generate_wechat_article(
    hotspot_summary: str,
    angle: str = "",
    theme: str = "graphite",
    provider_name: str | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """端到端生成一篇排版优美、带贴图文案的完整微信公众号文章资产。"""
    provider = get_provider(
        name=provider_name,
        base_url=ollama_url if provider_name == "ollama" else None,
        model=ollama_model if provider_name == "ollama" else None,
        session=session,
    )

    # 1. 生成长文正文 (Markdown)
    article_prompt = build_wechat_article_prompt(hotspot_summary, angle=angle)
    markdown_content = await provider.generate(article_prompt)

    # 2. 生成标题候选
    titles_prompt = build_wechat_titles_prompt(markdown_content)
    titles_raw = await provider.generate(titles_prompt)
    titles = []
    try:
        clean = titles_raw.strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
        titles = json.loads(clean)
    except Exception:
        titles = [t.strip().lstrip("0123456789.-、* ") for t in titles_raw.splitlines() if len(t.strip()) > 8]

    chosen_title = titles[0] if titles else "AI重塑软件开发：从代码补全到智能体全生命周期交付"

    # 3. 提取摘要
    digest = "本文结合最新行业动态，深度剖析 AI 研发协作痛点及 Agent 架构如何解放开发者。"

    # 4. 执行排版，生成微信原生支持的内联样式 HTML
    rendered_html = render_wechat_article(
        markdown_content,
        title=chosen_title,
        digest=digest,
        theme=theme,
    )

    # 5. 衍生 300 字贴图文案与 3:4 封面图提示词
    poster_prompts = build_wechat_poster_prompt(markdown_content)
    poster_copy = await provider.generate(poster_prompts["copy_prompt"])
    poster_image_prompt = (
        f"结合标题《{chosen_title}》，生成一张适合公众号贴图的主图，"
        f"比例 3:4，海报风格，标题文字占据版面上半部分并强烈醒目，科技感现代扁平插画。"
    )

    return {
        "title": chosen_title,
        "title_candidates": titles,
        "markdown_content": markdown_content,
        "rendered_html": rendered_html,
        "digest": digest,
        "theme": theme,
        "poster_copy": poster_copy.strip(),
        "poster_image_prompt": poster_image_prompt,
    }


def save_wechat_article_to_db(
    session: Session,
    article_data: dict[str, Any],
) -> Article:
    """将公众号图文保存至 ContentPilot 数据库。"""
    article = Article(
        title=article_data["title"],
        content=article_data["markdown_content"],
        summary=article_data["digest"],
        status=ArticleStatus.ready.value,
        source="wechat_workflow",
    )
    session.add(article)
    session.flush()

    # 微信公众平台专用版本（保存内联样式富文本）
    metadata = {
        "rendered_html": article_data["rendered_html"],
        "theme": article_data["theme"],
        "poster_copy": article_data["poster_copy"],
        "poster_image_prompt": article_data["poster_image_prompt"],
        "title_candidates": article_data["title_candidates"],
    }

    version = ArticleVersion(
        article_id=article.id,
        platform="wechat_mp",
        title=article_data["title"],
        content=article_data["rendered_html"],
        metadata_json=json.dumps(metadata),
        version=1,
    )
    session.add(version)
    session.commit()
    return article
