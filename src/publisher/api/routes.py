"""API 路由（文档第 60 节）。除 /auth/login 外全部要求鉴权。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..auth import AuthService
from ..events import event_bus
from ..schemas import (
    ArticleIn,
    ArticleOut,
    ArticleUpdate,
    LoginIn,
    PublishRequest,
    ResolvedPolicyOut,
    ReviewAction,
    WhoamiOut,
)
from ..services.article_service import ArticleService
from ..services.policy_service import PolicyService
from ..services.publish_service import PublishService
from ..services.review_service import ReviewService
from .deps import (
    auth_to_requester,
    get_current_auth,
    get_db,
    require_override_review,
)

router = APIRouter()


# ---- Auth ----

@router.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    auth = AuthService(db)
    token = auth.login(payload.username, payload.password)
    if not token:
        raise HTTPException(status_code=401, detail="invalid credentials")
    resp = JSONResponse({"token": token})
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if token:
        AuthService(db).logout(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp


@router.get("/auth/whoami", response_model=WhoamiOut)
def whoami(auth=Depends(get_current_auth)):
    return WhoamiOut(
        authenticated=True,
        username=auth.get("username"),
        source=auth.get("source"),
    )


@router.get("/auth/api_keys")
def list_api_keys(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    return [{"id": k.id, "name": k.name, "allow_override_review": k.allow_override_review}
            for k in AuthService(db).list_api_keys()]


@router.post("/auth/api_keys")
def create_api_key(
    name: str = "default", allow_override_review: bool = False,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    key = AuthService(db).create_api_key(name, allow_override_review)
    return {"key": key, "allow_override_review": allow_override_review}


# ---- Articles ----

@router.post("/articles", response_model=ArticleOut)
def create_article(payload: ArticleIn, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    return ArticleService(db).create(
        payload.title, payload.content, payload.summary, payload.cover_image, payload.source
    )


@router.get("/articles")
def list_articles(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """文章列表 + 只读聚合状态（§9.3/§27：按该文章全部 PublishTask 实时计算）。"""
    from sqlalchemy import select

    from ..models import PublishTask
    from ..schemas import ArticleOut
    from ..services.publish_service import _aggregate_status

    tasks_by_article: dict[int, list[str]] = {}
    for t in db.scalars(select(PublishTask)).all():
        tasks_by_article.setdefault(t.article_id, []).append(t.status)

    out = []
    for a in ArticleService(db).list():
        d = ArticleOut.model_validate(a).model_dump(mode="json")
        d["aggregate_status"] = _aggregate_status(tasks_by_article.get(a.id, []))
        out.append(d)
    return out


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    a = ArticleService(db).get(article_id)
    if not a:
        raise HTTPException(404, "not found")
    return a


@router.patch("/articles/{article_id}", response_model=ArticleOut)
def update_article(
    article_id: int, payload: ArticleUpdate,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    a = ArticleService(db).update(article_id, **payload.model_dump(exclude_unset=True))
    if not a:
        raise HTTPException(404, "not found")
    return a


@router.delete("/articles/{article_id}")
def delete_article(
    article_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)
):
    try:
        ok = ArticleService(db).delete(article_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True}


@router.get("/articles/{article_id}/versions")
def list_versions(article_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    from sqlalchemy import select

    from ..models import ArticleVersion

    return db.scalars(
        select(ArticleVersion).where(ArticleVersion.article_id == article_id)
    ).all()


# ---- Policies ----

@router.get("/policies")
def get_policy(
    scope_type: str,
    scope_id: int | None = None,
    db: Session = Depends(get_db),
    auth=Depends(get_current_auth),
):
    """读取某 scope 的策略行。返回 null = 未配置 = 跟随上级（§2.5）。"""
    from sqlalchemy import select

    from ..models import ReviewPolicy

    stmt = select(ReviewPolicy).where(ReviewPolicy.scope_type == scope_type)
    stmt = stmt.where(
        ReviewPolicy.scope_id.is_(None) if scope_id is None
        else ReviewPolicy.scope_id == scope_id
    )
    return db.scalar(stmt)


@router.post("/policies")
def set_policy(
    payload: dict, db: Session = Depends(get_db), auth=Depends(get_current_auth)
):
    """按 scope 设置策略。review_mode/publish_mode 为 null 表示删除（跟随上级）。"""
    svc = PolicyService(db)
    row = svc.set_policy(
        payload.get("scope_type"),
        payload.get("scope_id"),
        payload.get("review_mode"),
        payload.get("publish_mode"),
        payload.get("is_floor", False),
    )
    return {"ok": True, "row_id": row.id if row else None}


@router.get("/policies/resolve", response_model=ResolvedPolicyOut)
def resolve_policy(
    platform_id: int | None = None,
    account_id: int | None = None,
    article_id: int | None = None,
    task_id: int | None = None,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    r = PolicyService(db).resolve(platform_id, account_id, article_id, task_id)
    return ResolvedPolicyOut(
        review_policy=r.review_policy.value,
        publish_policy=r.publish_policy,
        is_floor_locked=r.is_floor_locked,
        review_scope=r.review_scope,
        publish_scope=r.publish_scope,
    )


# ---- Reviews ----

@router.get("/reviews")
def list_reviews(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """审核列表（§38）：附带文章 / 平台 / 策略 / 版本信息与「版本已过期」标记。"""
    from sqlalchemy import select

    from ..models import Review
    from ..services.article_service import ArticleService
    from ..services.publish_service import PublishService

    svc = ArticleService(db)
    from datetime import datetime, timedelta, timezone

    from ..config import settings as app_settings

    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        days=app_settings.review_stale_days
    )

    def _aware(dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt

    out = []
    for r in db.scalars(select(Review).order_by(Review.id.desc())):
        task = PublishService(db).get_task(r.task_id)
        article = svc.get(task.article_id) if task else None
        version = svc.get_version(r.article_version_id)
        latest = (
            svc.latest_version(task.article_id, task.platform) if task else None
        )
        # 审核绑定版本落后于最新版本，或最新版本内容 ≠ 当前文章内容（编辑过未重绑）
        outdated = bool(
            latest
            and (
                r.article_version_id != latest.id
                or latest.content != (article.content if article else "")
                or latest.title != (article.title if article else "")
            )
        )
        out.append({
            "id": r.id,
            "task_id": r.task_id,
            "article_id": task.article_id if task else None,
            "article_title": article.title if article else None,
            "platform": task.platform if task else None,
            "review_policy": task.review_policy if task else None,
            "publish_policy": task.publish_policy if task else None,
            "article_version_id": r.article_version_id,
            "version": version.version if version else None,
            "version_outdated": outdated,
            "status": r.status,
            "stale": bool(
                r.status == "pending" and _aware(r.created_at) < stale_cutoff
            ),
            "reviewer": r.reviewer,
            "comment": r.comment,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        })
    return out


@router.post("/reviews/{review_id}/refresh")
def refresh_review(
    review_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)
):
    """刷新到最新版本重新审核（§35/§38）。

    文章内容有变更时生成新版本，并把 Task 与 Review 一并重绑到该版本，
    保证「审核的内容 = 实际发布的内容」。
    """
    from ..models import Review, ReviewStatus, TaskStatus
    from ..services.article_service import ArticleService
    from ..services.log_service import LogService
    from ..services.publish_service import PublishService

    r = db.get(Review, review_id)
    if not r:
        raise HTTPException(404, "review not found")
    if r.status not in (ReviewStatus.pending.value, ReviewStatus.rejected.value):
        raise HTTPException(400, "仅待审核/已拒绝的记录可以刷新版本")

    task = PublishService(db).get_task(r.task_id)
    if not task:
        raise HTTPException(404, "task not found")

    svc = ArticleService(db)
    article = svc.get(task.article_id)
    if not article:
        raise HTTPException(404, "article not found")

    latest = svc.latest_version(article.id, task.platform)
    if (
        latest
        and (latest.title != article.title or latest.content != article.content)
    ):
        latest = svc.create_version(
            article.id, task.platform, article.title, article.content
        )

    if latest and latest.id != r.article_version_id:
        task.article_version_id = latest.id
        r.article_version_id = latest.id
    # rejected → pending：编辑新版本后重新送审（§9.2 推荐去向）
    if r.status == ReviewStatus.rejected.value:
        r.status = ReviewStatus.pending.value
        if task.status == TaskStatus.waiting_review.value:
            pass  # 保持 waiting_review，等待新一轮审核
    db.commit()
    LogService(db).log(
        "review_refreshed", task.id,
        message=f"review #{r.id} rebound to version {r.article_version_id}",
    )
    return {"ok": True, "article_version_id": r.article_version_id, "status": r.status}


@router.post("/reviews/{review_id}/approve")
def approve_review(
    review_id: int, payload: ReviewAction | None = None,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    svc = ReviewService(db)
    try:
        review = svc.approve(review_id, auth_to_requester(auth), (payload.comment if payload else None))
    except ValueError as e:
        raise HTTPException(404, str(e))
    # 任务流转（automatic→queued / manual→pending）已在 ReviewService.approve 内处理
    return review


@router.post("/reviews/{review_id}/reject")
def reject_review(
    review_id: int, payload: ReviewAction | None = None,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    svc = ReviewService(db)
    try:
        return svc.reject(review_id, auth_to_requester(auth), (payload.comment if payload else None))
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---- Publish / Tasks ----

@router.post("/publish")
def publish(
    payload: PublishRequest,
    db: Session = Depends(get_db),
    auth=Depends(get_current_auth),
):
    svc = PublishService(db)
    # 突破下限权限：仅 session（人类）或带 allow_override_review 的 API Key
    allow_override = auth.get("source") == "session" or (
        auth.get("api_key") is not None
        and auth["api_key"].allow_override_review
    )
    try:
        tasks = svc.create_tasks(
            payload.article_id,
            payload.platforms,
            payload.account_ids,
            payload.review_override,
            payload.publish_override,
            allow_override_review=allow_override,
            requester=auth_to_requester(auth),
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return tasks


@router.get("/publish/{task_id}")
def get_publish_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """§60 列出的任务详情接口（与 /tasks/{id} 等价）。"""
    t = PublishService(db).get_task(task_id)
    if not t:
        raise HTTPException(404, "not found")
    return t


@router.get("/tasks")
def list_tasks(status: str | None = None, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    return PublishService(db).list_tasks(status)


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    t = PublishService(db).get_task(task_id)
    if not t:
        raise HTTPException(404, "not found")
    return t


@router.get("/tasks/{task_id}/logs")
def list_task_logs(
    task_id: int, limit: int = 200,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    """单个任务的发布日志（按时间正序）。"""
    from sqlalchemy import select

    from ..models import PublishLog

    rows = db.scalars(
        select(PublishLog)
        .where(PublishLog.task_id == task_id)
        .order_by(PublishLog.id.desc())
        .limit(min(max(limit, 1), 1000))
    ).all()
    return list(reversed(rows))


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    try:
        return PublishService(db).retry(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    try:
        return PublishService(db).resume(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    try:
        return PublishService(db).cancel(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    try:
        ok = PublishService(db).delete(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True}


# ---- Accounts ----

@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    from ..services.account_service import AccountService
    return AccountService(db).list()


@router.post("/accounts")
def create_account(payload: dict, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    from ..services.account_service import AccountService
    return AccountService(db).create(
        payload.get("key"), payload.get("platform"), payload.get("name", ""),
        credentials=payload.get("credentials"),
    )


@router.get("/accounts/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    from ..services.account_service import AccountService
    a = AccountService(db).get(account_id)
    if not a:
        raise HTTPException(404, "not found")
    return a


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: int, payload: dict,
    db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    from ..services.account_service import AccountService
    try:
        a = AccountService(db).update(
            account_id,
            platform=payload.get("platform"),
            name=payload.get("name"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not a:
        raise HTTPException(404, "not found")
    return a


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    from ..services.account_service import AccountService
    try:
        ok = AccountService(db).delete(account_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True}


# ---- Platforms ----

@router.get("/platforms")
def list_platforms(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """平台列表（含 id/mode）。发布页用 id 调 /policies/resolve，用 mode 提示发布方式。"""
    from sqlalchemy import select

    from ..models import Platform
    from ..platforms.registry import sync_platforms

    sync_platforms(db)  # 幂等：老库补齐 platforms 行
    return db.scalars(select(Platform).order_by(Platform.id)).all()


# ---- Browser Sessions ----

@router.get("/browser/sessions")
def list_browser_sessions(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """浏览器会话与账号锁状态（§50）。"""
    from sqlalchemy import select

    from ..models import BrowserSession

    return db.scalars(select(BrowserSession).order_by(BrowserSession.id)).all()


# ---- Settings ----

@router.get("/settings")
def get_settings(db: Session = Depends(get_db), auth=Depends(get_current_auth)):
    """可编辑运行时设置（§47/§55）。返回当前生效值与出厂默认。"""
    from ..services.setting_service import EDITABLE_SETTINGS, get_setting

    out = []
    for key, meta in EDITABLE_SETTINGS.items():
        v = get_setting(db, key)
        out.append({
            "key": key,
            "type": meta["type"],
            "label": meta["label"],
            "description": meta["description"],
            "value": (v == "true") if meta["type"] == "bool" and v else (v if v else meta["fallback"]()),
        })
    return out


@router.post("/settings")
def update_settings(
    payload: dict, db: Session = Depends(get_db), auth=Depends(get_current_auth),
):
    """更新设置项。body: {"key": "...", "value": bool}"""
    from ..services.setting_service import EDITABLE_SETTINGS, set_setting

    key = payload.get("key")
    value = payload.get("value")
    if key not in EDITABLE_SETTINGS:
        raise HTTPException(400, f"unknown setting: {key}")
    if EDITABLE_SETTINGS[key]["type"] == "bool":
        if not isinstance(value, bool):
            raise HTTPException(400, "bool setting requires boolean value")
        value = "true" if value else "false"
    set_setting(db, key, str(value))
    return {"ok": True, "key": key, "value": payload.get("value")}


# ---- Logs ----

@router.get("/logs")
def list_logs(
    task_id: int | None = None,
    level: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    auth=Depends(get_current_auth),
):
    """发布日志查询（§51，metadata 已脱敏）。"""
    from sqlalchemy import select

    from ..models import PublishLog

    stmt = select(PublishLog)
    if task_id is not None:
        stmt = stmt.where(PublishLog.task_id == task_id)
    if level:
        stmt = stmt.where(PublishLog.level == level)
    stmt = stmt.order_by(PublishLog.id.desc()).limit(min(max(limit, 1), 1000))
    return db.scalars(stmt).all()


# ---- Events (SSE) ----

@router.get("/events")
async def events(auth=Depends(get_current_auth)):
    import json

    queue = event_bus.subscribe("*")

    async def gen():
        try:
            while True:
                payload = await queue.get()
                yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"
        finally:
            event_bus.unsubscribe("*", queue)

    return StreamingResponse(gen(), media_type="text/event-stream")