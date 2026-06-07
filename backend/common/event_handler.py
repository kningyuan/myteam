"""事件处理器链 — persistence → SSE notification → projection → audit。

EventPipeline 是 Hub 侧的事件分发总线。ProjectionRunner 写入 WorkspaceEvent 后，
通过 EventPipeline.dispatch() 触发所有注册处理器。

处理器失败不污染 kernel task，仅 log 错误。
"""

import logging
from typing import Any, Callable

logger = logging.getLogger("event_handler")

EventHandler = Callable[[dict], None]


class EventPipeline:
    """事件处理管线。处理器按事件类型注册，dispatch 时并行/顺序执行。"""

    handlers: dict[str, list[EventHandler]] = {}

    @classmethod
    def register(cls, event_type: str, handler: EventHandler):
        """注册一个事件处理器到指定事件类型。"""
        cls.handlers.setdefault(event_type, []).append(handler)
        logger.debug("registered handler %s for %s", handler.__name__, event_type)

    @classmethod
    def dispatch(cls, event: dict):
        """调度事件给所有注册处理器。处理器异常只 log 不抛出。"""
        for handler in cls.handlers.get(event.get("type", ""), []):
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler %s failed for %s: %s",
                             handler.__name__, event.get("type"), e)

    @classmethod
    def registered_types(cls) -> list[str]:
        """返回所有已注册的事件类型。"""
        return list(cls.handlers.keys())


# ── 内置处理器 ─────────────────────────────────────────

def _persistence_handler(event: dict):
    """持久化：确保事件已写入 workspace_event 表（默认已由 append_workspace_event 写入）。"""
    # 默认无额外操作：append_workspace_event 已持久化
    pass


def _sse_notification_handler(event: dict):
    """SSE 通知：广播事件到前端订阅者。"""
    # 由 WorkspaceEvent SSE endpoint (/api/workspace/events/stream) 轮询处理
    # 此处预留钩子，未来可注入内存广播队列加速 SSE 推送
    pass


def _channel_projection_handler(event: dict):
    """频道投影：将任务/门禁事件写入项目频道消息。"""
    metadata = event.get("metadata", {})
    if not metadata:
        return
    # 由 R2-1a ProjectionRunner 处理频道相关内容
    # 此处预留钩子，未来可将 gate/deliverable 事件自动发帖到项目频道
    pass


def _audit_log_handler(event: dict):
    """审计日志：记录事件到 audit_log 表或日志文件。"""
    try:
        from common.audit_log import write_audit_entry
        write_audit_entry(event)
    except Exception:
        pass  # audit_log 失败不阻塞主流程


# ── 注册内置处理器 ─────────────────────────────────────
for _type in ["project.task.updated", "project.gate.completed", "project.gate.rejected",
              "project.task.blocked", "project.deliverable.ready", "project.created",
              "project.completed", "project.failed", "budget.threshold.reached",
              "chat.message.posted"]:
    EventPipeline.register(_type, _persistence_handler)
    EventPipeline.register(_type, _sse_notification_handler)
    EventPipeline.register(_type, _channel_projection_handler)
    EventPipeline.register(_type, _audit_log_handler)