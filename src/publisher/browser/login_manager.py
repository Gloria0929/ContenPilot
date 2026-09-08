"""浏览器登录管理器：Web/Worker 触发的后台登录流程。

使用场景（§24/§25）：
- Web「账号登录」按钮 → POST /browser/login → 后台线程打开可见浏览器，
  容器内渲染在 Xvfb :99（用户经 noVNC :6080 操作），本机直接弹窗
- 发布任务 needs_auth（waiting_auth）时 Worker 自动触发，让 noVNC
  直接显示平台登录页，免去 SSH 手动执行 browser login

登录成功后自动把该账号所有 waiting_auth 任务重置为 queued。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from ..config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 内存态（进程级）：key = "platform:account_key"
_LOGIN_STATE: dict[str, dict] = {}
_LOCK = threading.Lock()


def _key(platform: str, account_key: str) -> str:
    return f"{platform}:{account_key}"


def get_status(platform: str, account_key: str) -> dict | None:
    with _LOCK:
        return _LOGIN_STATE.get(_key(platform, account_key))


def start_login(platform: str, account_key: str, timeout: int | None = None) -> dict:
    """启动后台浏览器登录线程。已 running 时直接返回当前状态（防重复开窗）。"""
    k = _key(platform, account_key)
    with _LOCK:
        cur = _LOGIN_STATE.get(k)
        if cur and cur["status"] == "running":
            return cur
        _LOGIN_STATE[k] = {
            "status": "running",
            "error": None,
            "started_at": _utcnow().isoformat(),
        }

    t = threading.Thread(
        target=_run_login,
        args=(platform, account_key, timeout),
        daemon=True,
        name=f"browser-login-{platform}",
    )
    t.start()
    return {"status": "running", "error": None, "started_at": _utcnow().isoformat()}


def _finish(platform: str, account_key: str, ok: bool, error: str | None = None) -> None:
    with _LOCK:
        _LOGIN_STATE[_key(platform, account_key)] = {
            "status": "success" if ok else "failed",
            "error": error,
            "started_at": _utcnow().isoformat(),
        }


def _run_login(platform: str, account_key: str, timeout: int | None) -> None:
    """后台线程主体：打开浏览器等登录 → 保存会话 → 恢复 waiting_auth 任务。"""
    import asyncio

    from . import LoginError, run_browser_login

    effective_timeout = timeout or settings.browser_login_timeout
    try:
        path = asyncio.run(
            run_browser_login(platform, account_key, timeout=effective_timeout)
        )
    except (LoginError, Exception) as exc:  # noqa: BLE001
        _finish(platform, account_key, ok=False, error=str(exc))
        _log(platform, account_key, "login_failed", str(exc))
        return

    ok = _save_session(platform, account_key, str(path))
    if ok:
        _requeue_waiting_auth(platform, account_key)
    _finish(platform, account_key, ok=ok)


def _save_session(platform: str, account_key: str, path: str) -> bool:
    """独立短事务：写 BrowserSession 登录态记录（同 CLI browser login 逻辑）。"""
    try:
        from ..database import SessionLocal
        from ..models import Account
        from ..services.account_service import AccountService

        s = SessionLocal()
        try:
            acct = s.query(Account).filter(
                Account.platform == platform, Account.key == account_key
            ).first()
            if not acct:
                return False
            svc = AccountService(s)
            bs = svc.ensure_session(acct.id, platform)
            bs.session_path = path
            bs.status = "idle"
            s.commit()
            return True
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        return False


def _requeue_waiting_auth(platform: str, account_key: str) -> None:
    """登录成功后，把该账号所有 waiting_auth 任务恢复为 queued。"""
    try:
        from ..database import SessionLocal
        from ..events import emitter
        from ..models import Account, PublishTask, TaskStatus
        from ..services.log_service import LogService

        s = SessionLocal()
        try:
            acct = s.query(Account).filter(
                Account.platform == platform, Account.key == account_key
            ).first()
            if not acct:
                return
            tasks = s.query(PublishTask).filter(
                PublishTask.account_id == acct.id,
                PublishTask.status == TaskStatus.waiting_auth.value,
            ).all()
            if not tasks:
                return
            logs = LogService(s)
            for t in tasks:
                t.status = TaskStatus.queued.value
                t.timeout_at = None
                emitter.task_status(t.id, TaskStatus.queued.value)
                logs.log(
                    "task_retry", t.id,
                    message=f"登录完成，任务已自动恢复（平台：{platform}）",
                )
            s.commit()
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        pass


def _log(platform: str, account_key: str, event: str, message: str) -> None:
    """登录过程日志（不关联任务），失败静默不影响主流程。"""
    try:
        from ..database import SessionLocal
        from ..services.log_service import LogService

        s = SessionLocal()
        try:
            LogService(s).log(event, task_id=None, level="info", message=message)
        finally:
            s.close()
    except Exception:
        pass


# 模块导入时间标记（调试用）
_STARTED_AT = time.time()
