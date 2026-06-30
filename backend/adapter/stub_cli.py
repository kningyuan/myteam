"""Placeholder CLI adapters for backends planned but not yet wired."""

from __future__ import annotations

from typing import Generator

from adapter.core.events import AgentEvent, EventKind
from adapter.core.protocol import AdapterCapabilities, CLIAdapter, ModelInfo, RunRequest


class PlannedCLIAdapter(CLIAdapter):
    """Registry-visible stub: lists in settings but run() yields a clear ERROR event."""

    def __init__(self, adapter_id: str, display_name: str, *, doc_hint: str = ""):
        self._adapter_id = adapter_id
        self._display_name = display_name
        self._doc_hint = doc_hint or "See docs/plans/store-token-adapter-plan.md"

    @property
    def id(self) -> str:
        return self._adapter_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(streaming=False, tool_use=False, multi_turn=False)

    def list_models(self) -> list[ModelInfo]:
        return []

    def get_default_model(self) -> str:
        return ""

    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]:
        message = (
            f"{self.display_name} is not implemented yet. "
            f"Use opencode or claude for live runs. ({self._doc_hint})"
        )
        yield AgentEvent(
            kind=EventKind.ERROR,
            data={"message": message, "code": "NOT_IMPLEMENTED", "backend": self.id},
        )
