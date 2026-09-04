"""文章服务：文章与版本管理。"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article, ArticleStatus, ArticleVersion


class ArticleService:
    def __init__(self, session: Session):
        self.session = session

    def create(self, title="", content="", summary="", cover_image=None, source="manual") -> Article:
        article = Article(
            title=title,
            content=content,
            summary=summary,
            cover_image=cover_image,
            source=source,
            status=ArticleStatus.draft.value,
        )
        self.session.add(article)
        self.session.commit()
        return article

    def get(self, article_id: int) -> Article | None:
        return self.session.get(Article, article_id)

    def list(self) -> list[Article]:
        return list(self.session.scalars(select(Article).order_by(Article.id.desc())))

    def update(self, article_id: int, **fields) -> Article | None:
        article = self.get(article_id)
        if not article:
            return None
        for k, v in fields.items():
            if v is not None and hasattr(article, k):
                setattr(article, k, v)
        self.session.commit()
        return article

    def mark_ready(self, article_id: int) -> Article | None:
        return self.update(article_id, status=ArticleStatus.ready.value)

    def archive(self, article_id: int) -> Article | None:
        return self.update(article_id, status=ArticleStatus.archived.value)

    def delete(self, article_id: int) -> bool:
        """删除文章。已关联发布任务的文章拒绝删除（保留历史归因），版本一并删除。"""
        from sqlalchemy import delete as sa_delete

        from ..models import PublishTask

        article = self.get(article_id)
        if not article:
            return False
        has_tasks = self.session.scalar(
            select(PublishTask.id).where(PublishTask.article_id == article_id).limit(1)
        )
        if has_tasks:
            raise ValueError("该文章已关联发布任务，无法删除")
        # 显式按依赖顺序删除：ORM unit-of-work 的 flush 顺序对无
        # relationship 声明的表不保证先删子表，会导致外键约束失败
        self.session.execute(
            sa_delete(ArticleVersion).where(ArticleVersion.article_id == article_id)
        )
        self.session.execute(
            sa_delete(Article).where(Article.id == article_id)
        )
        self.session.commit()
        return True

    # ---- 版本 ----

    def create_version(
        self,
        article_id: int,
        platform: str,
        title: str,
        content: str,
        images: list[str] | None = None,
        cover_image: str | None = None,
        metadata: dict | None = None,
    ) -> ArticleVersion:
        version = self.session.scalar(
            select(ArticleVersion)
            .where(
                ArticleVersion.article_id == article_id,
                ArticleVersion.platform == platform,
            )
            .order_by(ArticleVersion.version.desc())
            .limit(1)
        )
        next_ver = (version.version + 1) if version else 1
        av = ArticleVersion(
            article_id=article_id,
            platform=platform,
            title=title,
            content=content,
            images=json.dumps(images or [], ensure_ascii=False),
            cover_image=cover_image,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            version=next_ver,
        )
        self.session.add(av)
        self.session.commit()
        return av

    def latest_version(self, article_id: int, platform: str) -> ArticleVersion | None:
        return self.session.scalar(
            select(ArticleVersion)
            .where(
                ArticleVersion.article_id == article_id,
                ArticleVersion.platform == platform,
            )
            .order_by(ArticleVersion.version.desc())
            .limit(1)
        )

    def get_version(self, version_id: int) -> ArticleVersion | None:
        return self.session.get(ArticleVersion, version_id)