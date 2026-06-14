"""Pluggable persistence port for Store (adapter pattern).

Store owns domain query methods; backends own connection lifecycle and
bootstrap. Swap SQLite for Postgres by implementing StoreBackend and
passing it to ``Store(backend=...)``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import sqlite3


@runtime_checkable
class StoreBackend(Protocol):
    """Minimal surface Store delegates to for persistence I/O."""

    @property
    def connection(self) -> sqlite3.Connection:
        """Thread-local (or pooled) connection for the current operation."""
        ...

    @property
    def fts_enabled(self) -> bool:
        """Whether full-text search index is available on this backend."""
        ...

    def close(self) -> None:
        """Release resources held by the current thread / session."""
        ...


class AbstractStoreBackend(ABC):
    """ABC mirror of :class:`StoreBackend` for concrete implementations."""

    @property
    @abstractmethod
    def connection(self) -> sqlite3.Connection:
        raise NotImplementedError

    @property
    @abstractmethod
    def fts_enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
