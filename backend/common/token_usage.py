#!/usr/bin/env python3
"""Token 计量抽象（Workflow v3 修正项 2/3：先契约后实施）。

adapter 层采集 usage → ``TokenUsageSink.record_usage`` → Store 真相库。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from common.store import Store


@dataclass(frozen=True)
class TokenUsageRecord:
    """一次 interaction 的 token 计量快照。"""

    project_id: str
    interaction_id: str
    tokens: int
    agent_id: str = ""
    backend: str = ""
    model: str = ""


@runtime_checkable
class TokenUsageSink(Protocol):
    """Token 计量落盘协议。"""

    def record_usage(
        self,
        project_id: str,
        interaction_id: str,
        tokens: int,
        *,
        agent_id: str = "",
        backend: str = "",
        model: str = "",
    ) -> None:
        """记录 token 用量；``tokens`` 为会话累计值（非增量）。"""
        ...


class StoreTokenUsageSink:
    """默认 sink：经 ``Store.bump_interaction_tokens`` 写入 interaction.tokens。"""

    def __init__(self, store: Store):
        self.store = store

    def record_usage(
        self,
        project_id: str,
        interaction_id: str,
        tokens: int,
        *,
        agent_id: str = "",
        backend: str = "",
        model: str = "",
    ) -> None:
        _ = TokenUsageRecord(
            project_id, interaction_id, tokens,
            agent_id=agent_id, backend=backend, model=model,
        )
        self.store.bump_interaction_tokens(interaction_id, tokens)
