"""CLI 具体实例包 — 导入即注册到 adapter.registry。"""

import adapters.opencode.adapter  # noqa: F401
import adapters.claude.adapter  # noqa: F401
from adapter.registry import registry
from adapters.stub_cli import PlannedCLIAdapter

registry.register(PlannedCLIAdapter("codex", "OpenAI Codex CLI"))
registry.register(PlannedCLIAdapter("cursor", "Cursor Agent CLI"))
