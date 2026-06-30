"""CLI Adapter 抽象接口 — 各 CLI 实例必须实现。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event
from typing import Generator, Optional

from adapter.core.events import AgentEvent


@dataclass
class ModelInfo:
    id: str
    name: str
    provider: str = ""
    default: bool = False


@dataclass
class AdapterCapabilities:
    streaming: bool = True
    tool_use: bool = True
    multi_turn: bool = True
    custom_rules: bool = True
    native_skill_registry: bool = False
    native_mcp_registry: bool = False


@dataclass
class RunRequest:
    """一次 Agent 运行请求 — 与 CLI 无关。"""

    workspace: str
    message: str
    model: str
    session_id: Optional[str] = None
    rules_file: Optional[str] = None
    agent_id: Optional[str] = None
    cancel_event: Optional[Event] = None
    extra: dict = field(default_factory=dict)


class CLIAdapter(ABC):
    """CLI 后端抽象：subprocess 细节留在 adapters/ 子包。"""

    @property
    @abstractmethod
    def id(self) -> str:
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    def get_default_model(self) -> str:
        ...

    @abstractmethod
    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]:
        """执行一次对话，yield 统一 AgentEvent 流。"""
        ...

    def sync_agent_skills(
        self,
        agent_id: str,
        workspace: str,
        skill_ids: list[str],
    ) -> dict:
        """将 registry 中的 Skill 同步到 CLI 原生 skill 注册表（按 Agent 作用域）。

        默认无操作；支持 native_skill_registry 的适配器应覆盖此方法。
        """
        _ = (agent_id, workspace, skill_ids)
        return {"success": True, "skipped": True, "reason": "adapter does not support native skills"}

    def sync_agent_mcp(
        self,
        agent_id: str,
        workspace: str,
        server_ids: list[str],
    ) -> dict:
        """将 registry 中的 MCP 同步到 CLI 原生 MCP 配置（按 Agent 作用域）。"""
        _ = (agent_id, workspace, server_ids)
        return {"success": True, "skipped": True, "reason": "adapter does not support native mcp"}
