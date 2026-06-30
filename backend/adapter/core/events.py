"""统一 Agent 流式事件模型 — UI 与 Service 层唯一事件契约。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    STEP_START = "step_start"
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    STEP_FINISH = "step_finish"
    ERROR = "error"
    SESSION = "session"


@dataclass
class AgentEvent:
    """一次 Adapter.run() 产出的统一事件。"""

    kind: EventKind
    data: dict[str, Any] = field(default_factory=dict)

    def to_thinking_payload(self) -> dict | None:
        """转为 SSE thinking.data（SESSION/ERROR 由 sse 模块单独处理）。"""
        if self.kind in (EventKind.SESSION, EventKind.ERROR):
            return None
        return {"type": self.kind.value, **self.data}
