"""CLI Backend 注册与导出"""
from .base import CLIBackend, BackendModel, BackendCapability, BackendConfig, StreamEvent, registry, BackendRegistry

# 导入所有后端触发注册
from . import opencode
