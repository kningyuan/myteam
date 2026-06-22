"""execution_harness — Agent 任务执行质量层（Hermes 模式 · CLI 适配）。

与 Layer A（Process / Gate）隔离；通过 facade 与 AgentPort / agent_transport 交互。
"""

from execution_harness.facade import enabled, inject_for_execute, on_task_complete, prepare_execute_harness

__all__ = [
    "enabled",
    "prepare_execute_harness",
    "inject_for_execute",
    "on_task_complete",
]
