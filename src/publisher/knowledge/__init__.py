"""知识库与提示词规范模块。"""
from .docs import (
    KNOWLEDGE_AT_WORK_INTRO,
    KNOWLEDGE_CRAWL_SITES,
    KNOWLEDGE_DEV_PAIN_POINTS,
    KNOWLEDGE_GEO_CRITERIA,
    get_combined_knowledge_context,
)
from .prompts import (
    build_geo_article_prompt,
    build_geo_titles_prompt,
    build_short_video_script_prompt,
    build_video_cover_and_assets_prompt,
    build_wechat_article_prompt,
    build_wechat_poster_prompt,
    build_wechat_titles_prompt,
)

__all__ = [
    "KNOWLEDGE_AT_WORK_INTRO",
    "KNOWLEDGE_DEV_PAIN_POINTS",
    "KNOWLEDGE_GEO_CRITERIA",
    "KNOWLEDGE_CRAWL_SITES",
    "get_combined_knowledge_context",
    "build_geo_titles_prompt",
    "build_geo_article_prompt",
    "build_wechat_article_prompt",
    "build_wechat_titles_prompt",
    "build_wechat_poster_prompt",
    "build_short_video_script_prompt",
    "build_video_cover_and_assets_prompt",
]
