"""SSE 事件总线。Worker 与 API 共享。"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, event: str, data: dict | None = None) -> None:
        payload = {"event": event, "data": data or {}, "ts": _now_iso()}
        for queue in list(self._subscribers["*"]) + [
            q for q in self._subscribers[event] if q not in self._subscribers["*"]
        ]:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def subscribe(self, event: str = "*") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers[event].add(q)
        return q

    def unsubscribe(self, event: str, queue: asyncio.Queue) -> None:
        self._subscribers[event].discard(queue)


event_bus = EventBus()


class EventEmitter:
    """业务层辅助，构造标准事件并发布。"""

    def __init__(self, bus: EventBus = event_bus):
        self.bus = bus

    def emit(self, event: str, data: dict | None = None) -> None:
        self.bus.publish(event, data)

    # 便捷方法
    def task_created(self, task_id: int, platform: str) -> None:
        self.emit("task.created", {"task_id": task_id, "platform": platform})

    def task_status(self, task_id: int, status: str, **extra) -> None:
        self.emit("task.status", {"task_id": task_id, "status": status, **extra})

    def review_stale(self, review_id: int, task_id: int) -> None:
        self.emit("task.review_stale", {"review_id": review_id, "task_id": task_id})

    def timeout(self, task_id: int) -> None:
        self.emit("task.timeout", {"task_id": task_id})


emitter = EventEmitter()