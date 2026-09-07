"""平台注册表：通过 name 查找 Adapter。新增平台不改 Core。"""
from __future__ import annotations

from .base import PlatformAdapter

_registry: dict[str, type[PlatformAdapter]] = {}


def register(name: str) -> Any:
    def deco(cls):
        cls.platform = name
        _registry[name] = cls
        return cls

    return deco


def get_adapter(name: str) -> PlatformAdapter | None:
    cls = _registry.get(name)
    return cls() if cls else None


def available_platforms() -> list[str]:
    return sorted(_registry.keys())


def import_platforms() -> None:
    """导入所有平台模块以触发注册。"""
    from . import cnblogs  # noqa: F401  (官方 API)
    from . import juejin  # noqa: F401
    from . import csdn  # noqa: F401
    from . import segmentfault  # noqa: F401
    from . import freebuf  # noqa: F401
    from . import baijiahao  # noqa: F401
    from . import qiehao  # noqa: F401
    from . import cto51  # noqa: F401  (51cto，模块名避开数字开头)
    from . import tencent_cloud  # noqa: F401


def adapter_mode(name: str) -> str:
    """平台的发布模式（api / browser / manual），未注册平台保守按 browser。"""
    cls = _registry.get(name)
    return getattr(cls, "mode", "browser") if cls else "browser"


def sync_platforms(session) -> int:
    """把 Adapter 注册表同步到 platforms 表（幂等，启动时调用）。

    没有这一步，platforms 表永远为空：
    - platform 级策略覆盖因 platform_id=None 无法 resolve（§6）
    - pre_publish_check 的锁模式判断退化为「全部按浏览器」（§50）
    """
    from sqlalchemy import select

    from ..models import Platform

    import_platforms()
    changed = 0
    for name in sorted(_registry):
        mode = adapter_mode(name)
        row = session.scalar(select(Platform).where(Platform.name == name))
        if row is None:
            session.add(Platform(name=name, mode=mode, capabilities="{}"))
            changed += 1
        elif row.mode != mode:
            row.mode = mode
            changed += 1
    if changed:
        session.commit()
    return changed