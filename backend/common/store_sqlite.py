"""SQLite implementation of :class:`~common.store_backend.StoreBackend`."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from common.store_backend import AbstractStoreBackend


class SQLiteStoreBackend(AbstractStoreBackend):
    """Per-thread SQLite connections with WAL bootstrap."""

    def __init__(self, db_path: Path, schema: str):
        self.db_path = db_path
        self._schema = schema
        self._tls = threading.local()
        self._fts = False
        self._bootstrap_schema()

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _bootstrap_schema(self) -> None:
        conn = self._open_connection()
        conn.executescript(self._schema)
        self._fts = self._init_message_fts(conn)
        conn.commit()
        conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = self._open_connection()
            self._tls.conn = conn
        return conn

    @property
    def fts_enabled(self) -> bool:
        return self._fts

    def _init_message_fts(self, conn: sqlite3.Connection) -> bool:
        """message 全文索引（trigram，CJK 子串召回友好）。FTS5/trigram 不可用时回退 LIKE。"""
        for tokenize in ("tokenize='trigram'", ""):
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5("
                    "text, conversation_id UNINDEXED"
                    + (", " + tokenize if tokenize else "")
                    + ")"
                )
                return True
            except sqlite3.OperationalError:
                conn.execute("DROP TABLE IF EXISTS message_fts")
        return False

    def close(self) -> None:
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            conn.close()
            self._tls.conn = None
