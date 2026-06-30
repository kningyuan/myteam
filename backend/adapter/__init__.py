"""adapter 包 — CLI 适配层。

core/: 抽象层(events/protocol/registry/sse/subprocess_cli)
opencode/: opencode 实现
claude/: claude 实现
"""
# 触发 CLI 实例注册(side-effect import)
import adapter.opencode.adapter  # noqa: F401
import adapter.claude.adapter  # noqa: F401
from adapter.core.events import AgentEvent, EventKind
from adapter.core.protocol import AdapterCapabilities, CLIAdapter, ModelInfo, RunRequest
from adapter.core.subprocess_cli import SubprocessCLIAdapter
from adapter.core.registry import registry
from adapter.core.sse import encode_done, encode_error, encode_event
from adapter.stub_cli import PlannedCLIAdapter  # noqa: F401
