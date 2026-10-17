"""进程内事件总线：为情绪、记忆、宠物命令和 UI 事件解耦。

设计约束：
- 发布不抛异常：单个订阅者出错不能拖垮聊天或记忆流程。
- 每个事件带 trace_id，可从用户消息追踪到宠物反应。
- 订阅按优先级排序，同优先级按注册顺序执行。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from contracts import make_trace_id

# 已知事件类型注册表。新事件应先在这里登记，避免拼写漂移。
EVENT_TYPES = {
    "chat.user_message",
    "chat.assistant_completed",
    "chat.assistant_cancelled",
    "chat.assistant_failed",
    "emotion.fast_ready",
    "emotion.slow_ready",
    "emotion.result_expired",
    "memory.candidate_ready",
    "memory.confirmation_requested",
    "memory.confirmed",
    "memory.rejected",
    "memory.deleted",
    "pet.command_sent",
    "pet.event_received",
    "focus.completed",
    "quiet.toggled",
    "app.shutdown",
}


class EventBus:
    """线程安全的发布/订阅总线。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Tuple[int, int, Callable]]] = {}
        self._next_token = 0
        self.last_publish_errors: List[str] = []

    def subscribe(self, event_type: str, callback: Callable[[str, dict], None], priority: int = 100) -> int:
        """订阅事件。priority 越大越先执行。返回用于退订的 token。"""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"未登记的事件类型：{event_type}")
        if not callable(callback):
            raise TypeError("callback 必须可调用")
        with self._lock:
            self._next_token += 1
            token = self._next_token
            self._subscribers.setdefault(event_type, []).append((priority, token, callback))
            self._subscribers[event_type].sort(key=lambda item: item[0], reverse=True)
            return token

    def unsubscribe(self, token: int) -> bool:
        """按 token 退订。"""
        with self._lock:
            for event_type, items in list(self._subscribers.items()):
                for index, (_, item_token, _) in enumerate(items):
                    if item_token == token:
                        del items[index]
                        if not items:
                            del self._subscribers[event_type]
                        return True
        return False

    def subscriber_count(self, event_type: str) -> int:
        with self._lock:
            return len(self._subscribers.get(event_type, []))

    def publish(self, event_type: str, payload: Optional[dict] = None, trace_id: Optional[str] = None) -> List[Any]:
        """发布事件。返回各订阅者返回值；任何订阅者异常都会被记录而不是传播。"""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"未登记的事件类型：{event_type}")
        envelope = {"type": event_type, "payload": payload or {}, "trace_id": trace_id or make_trace_id()}
        with self._lock:
            items = list(self._subscribers.get(event_type, []))
        results: List[Any] = []
        for _, _, callback in items:
            try:
                results.append(callback(event_type, dict(envelope)))
            except Exception as error:  # noqa: BLE001 - 订阅者错误不能拖垮发布方
                self.last_publish_errors.append(f"{event_type}: {type(error).__name__}: {error}")
        return results

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self.last_publish_errors.clear()
