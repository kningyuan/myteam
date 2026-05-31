"""
CLI Backend 抽象接口
所有具体 CLI 后端（OpenCode、Claude Code 等）必须实现此接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Optional


@dataclass
class BackendCapability:
    """后端能力声明"""
    streaming: bool = False        # 是否支持流式输出
    tool_use: bool = False         # 是否支持工具调用
    multi_turn: bool = False       # 是否支持多轮对话 (session)
    json_output: bool = False      # 是否原生支持 JSON 格式输出
    custom_rules: bool = False     # 是否支持注入自定义规则文件


@dataclass
class BackendModel:
    """后端可用模型"""
    id: str                        # 模型 ID（传给 CLI 用的名称）
    name: str                      # 显示名称
    provider: str = ""             # 提供商（如 SenseNova, Anthropic）
    default: bool = False          # 是否为此后端的默认模型


@dataclass
class BackendConfig:
    """后端配置 - 持久化到 agents.json"""
    backend_id: str                # 后端 ID（如 "opencode", "claude"）
    model: str                     # 使用的模型 ID
    extra: dict = field(default_factory=dict)  # 后端特定配置


class StreamEvent:
    """流式事件 - 统一所有后端的输出格式"""
    def __init__(self, event_type: str, **kwargs):
        self.event_type = event_type  # text, tool_use, tool_result, step_finish, error
        self.data = kwargs

    def to_dict(self) -> dict:
        return {"event": self.event_type, "data": self.data}


class CLIBackend(ABC):
    """CLI 后端抽象基类"""

    @property
    @abstractmethod
    def id(self) -> str:
        """后端唯一标识 (如 'opencode', 'claude')"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """后端显示名称"""
        ...

    @abstractmethod
    def list_models(self) -> list[BackendModel]:
        """列出此后端可用的模型"""
        ...

    @abstractmethod
    def get_default_model(self) -> str:
        """获取默认模型 ID"""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapability:
        """此后端的能力声明"""
        ...

    def validate_model(self, model: str) -> bool:
        """验证模型 ID 是否有效"""
        return any(m.id == model for m in self.list_models())

    @abstractmethod
    def chat(
        self,
        workspace: str,
        message: str,
        model: str,
        session_id: Optional[str] = None,
        rules_file: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Generator[StreamEvent, None, None]:
        """
        与 LLM 对话，返回流式事件

        Args:
            workspace: Agent 工作目录
            message: 用户消息（已拼接好系统提示）
            model: 模型 ID（由 list_models() 返回的 id）
            session_id: 会话 ID（用于继续对话，None=新建）
            rules_file: 规则文件路径（可选）
            agent_id: Agent ID（用于日志/环境变量）

        Yields:
            StreamEvent 流式事件
        """
        ...

    @abstractmethod
    def extract_session_id(self, output: str, events: list[StreamEvent]) -> Optional[str]:
        """从输出中提取新 session ID"""
        ...


class BackendRegistry:
    """后端注册中心 - 管理所有可用的 CLI 后端"""

    def __init__(self):
        self._backends: dict[str, CLIBackend] = {}

    def register(self, backend: CLIBackend):
        """注册后端"""
        self._backends[backend.id] = backend

    def get(self, backend_id: str) -> Optional[CLIBackend]:
        """获取后端实例"""
        return self._backends.get(backend_id)

    def list_all(self) -> list[CLIBackend]:
        """列出所有已注册后端"""
        return list(self._backends.values())

    def list_models_all(self) -> dict[str, list[BackendModel]]:
        """列出所有后端的所有模型，按后端分组"""
        return {bid: b.list_models() for bid, b in self._backends.items()}


# 全局注册中心
registry = BackendRegistry()