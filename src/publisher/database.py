"""数据库引擎与会话。SQLite WAL 模式。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = settings.effective_database_url
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # 在创建引擎前确保数据目录存在，否则 SQLite 无法创建文件
        settings.ensure_dirs()
    engine = create_engine(url, future=True, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_wal(dbapi_conn, record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  确保所有模型已注册
    from .platforms.registry import sync_platforms

    settings.ensure_dirs()  # 确保 data/uploads/logs 目录存在
    Base.metadata.create_all(bind=engine)
    # 平台注册表 → platforms 表（幂等）：platform 级策略与浏览器锁判断依赖此表
    session = SessionLocal()
    try:
        sync_platforms(session)
    finally:
        session.close()