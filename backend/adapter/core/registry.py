"""Adapter 注册中心 — 管理 opencode / claude 等实例。"""

from typing import Optional

from adapter.core.protocol import CLIAdapter, ModelInfo


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, CLIAdapter] = {}

    def register(self, adapter: CLIAdapter) -> None:
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> Optional[CLIAdapter]:
        return self._adapters.get(adapter_id)

    def list_all(self) -> list[CLIAdapter]:
        return list(self._adapters.values())

    def list_models_all(self) -> dict[str, list[ModelInfo]]:
        return {a.id: a.list_models() for a in self._adapters.values()}


registry = AdapterRegistry()
