"""Agent CLI 抽象层 — 与具体 CLI（OpenCode / Claude 等）无关。"""

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, CLIAdapter, ModelInfo, RunRequest
from adapter.subprocess_cli import SubprocessCLIAdapter
from adapter.registry import registry
from adapter.sse import encode_done, encode_error, encode_event

__all__ = [
    "AgentEvent",
    "EventKind",
    "AdapterCapabilities",
    "CLIAdapter",
    "SubprocessCLIAdapter",
    "ModelInfo",
    "RunRequest",
    "registry",
    "encode_event",
    "encode_error",
    "encode_done",
]
