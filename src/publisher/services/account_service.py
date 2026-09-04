"""账号服务：账号状态、账号级浏览器并发锁、发布频率限制与冷却。

文档第 50 节：同一 account_id + platform 组合的浏览器任务只能有一个执行。
文档第 54 节：最小发布间隔 + 连续失败自动冷却。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Account, AccountStatus, BrowserSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, account_id: int) -> Account | None:
        return self.session.get(Account, account_id)

    def get_by_key(self, key: str) -> Account | None:
        return self.session.scalar(select(Account).where(Account.key == key))

    def list(self) -> list[Account]:
        return list(self.session.scalars(select(Account).order_by(Account.id)))

    def create(
        self,
        key: str,
        platform: str,
        name: str = "",
        credentials: dict | None = None,
    ) -> Account:
        account = Account(key=key, platform=platform, name=name)
        if credentials:
            # 敏感凭据 Fernet 加密存储（§53），不落明文
            from ..security import encrypt_json

            account.encrypted_credentials = encrypt_json(credentials)
        self.session.add(account)
        self.session.commit()
        return account

    def update(
        self,
        account_id: int,
        platform: str | None = None,
        name: str | None = None,
    ) -> Account | None:
        account = self.get(account_id)
        if not account:
            return None
        if platform is not None:
            account.platform = platform
        if name is not None:
            account.name = name
        self.session.commit()
        return account

    def delete(self, account_id: int) -> bool:
        """删除账号。已关联发布任务的账号拒绝删除（保留历史归因）。"""
        from sqlalchemy import delete as sa_delete

        from ..models import BrowserSession, PublishTask

        account = self.get(account_id)
        if not account:
            return False
        has_tasks = self.session.scalar(
            select(PublishTask.id).where(PublishTask.account_id == account_id).limit(1)
        )
        if has_tasks:
            raise ValueError("该账号已关联发布任务，无法删除")
        # 显式按依赖顺序删除：ORM unit-of-work 的 flush 顺序对无
        # relationship 声明的表不保证先删子表，会导致外键约束失败
        self.session.execute(
            sa_delete(BrowserSession).where(BrowserSession.account_id == account_id)
        )
        self.session.execute(
            sa_delete(Account).where(Account.id == account_id)
        )
        self.session.commit()
        return True

    # ---- 浏览器会话锁 ----

    def get_session(self, account_id: int, platform: str) -> BrowserSession | None:
        return self.session.scalar(
            select(BrowserSession).where(
                BrowserSession.account_id == account_id,
                BrowserSession.platform == platform,
            )
        )

    def ensure_session(self, account_id: int, platform: str) -> BrowserSession:
        s = self.get_session(account_id, platform)
        if not s:
            s = BrowserSession(account_id=account_id, platform=platform)
            self.session.add(s)
            self.session.commit()
        return s

    def try_lock(self, account_id: int, platform: str, task_id: int) -> bool:
        """尝试对账号浏览器会话加锁。返回是否成功。"""
        s = self.ensure_session(account_id, platform)
        if s.current_task_id is not None and s.current_task_id != task_id:
            return False
        s.current_task_id = task_id
        s.status = "busy"
        s.locked_at = _utcnow()
        self.session.commit()
        return True

    def unlock(self, account_id: int, platform: str, task_id: int) -> None:
        s = self.get_session(account_id, platform)
        if s and s.current_task_id == task_id:
            s.current_task_id = None
            s.locked_at = None
            s.status = "idle"
            self.session.commit()

    def release_expired_locks(self) -> int:
        """释放超时的等待类任务锁（文档第 21 节）。由后台任务调用。"""
        cutoff = _utcnow() - timedelta(seconds=settings.waiting_auth_timeout)
        count = 0
        for s in self.session.scalars(
            select(BrowserSession).where(BrowserSession.current_task_id.is_not(None))
        ):
            if s.locked_at and self._as_aware(s.locked_at) < cutoff:
                s.current_task_id = None
                s.locked_at = None
                s.status = "idle"
                count += 1
        if count:
            self.session.commit()
        return count

    # ---- 频率限制与冷却 ----

    @staticmethod
    def _as_aware(dt: datetime) -> datetime:
        """SQLite 读出的 datetime 可能丢失 tz（naive），统一补 UTC。"""
        if dt is not None and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def check_publish_allowed(self, account: Account) -> tuple[bool, str]:
        """返回 (是否允许, 原因)。"""
        if account.status == AccountStatus.disabled.value:
            return False, "账户已停用"
        cooldown_until = self._as_aware(account.cooldown_until)
        if cooldown_until and cooldown_until > _utcnow():
            return False, "账户正在冷却中"
        last_published_at = self._as_aware(account.last_published_at)
        if last_published_at:
            elapsed = (_utcnow() - last_published_at).total_seconds()
            if elapsed < settings.min_publish_interval_seconds:
                return False, "低于最低发布间隔"
        return True, ""

    def mark_published(self, account: Account) -> None:
        account.last_published_at = _utcnow()
        account.consecutive_blocked = 0
        self.session.commit()

    def mark_blocked(self, account: Account) -> None:
        """记录一次风控/异常，达到阈值进入冷却。"""
        account.consecutive_blocked += 1
        if account.consecutive_blocked >= settings.max_consecutive_blocked:
            account.status = AccountStatus.cooling.value
            account.cooldown_until = _utcnow() + timedelta(
                seconds=settings.cooldown_seconds
            )
            account.consecutive_blocked = 0
        self.session.commit()