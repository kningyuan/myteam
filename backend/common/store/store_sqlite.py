"""SQLite implementation of :class:`~common.store_backend.StoreBackend`."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from common.store.store_backend import AbstractStoreBackend


class SQLiteStoreBackend(AbstractStoreBackend):
    """Per-thread SQLite connections with WAL bootstrap."""

    def __init__(self, db_path: Path, schema: str):
        self.db_path = db_path
        self._schema = schema
        self._tls = threading.local()
        self._message_fts = False
        self._memory_fts = False
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
        self._ensure_memory_columns(conn)
        self._message_fts = self._init_message_fts(conn)
        self._memory_fts = self._init_memory_fts(conn)
        if self._memory_fts:
            self._backfill_memory_fts(conn)
        conn.commit()
        conn.close()

    def _ensure_memory_columns(self, conn: sqlite3.Connection) -> None:
        """memory 表加 source/created_by 列（旧库迁移，幂等）。"""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memory)").fetchall()}
        if "source" not in cols:
            conn.execute("ALTER TABLE memory ADD COLUMN source TEXT DEFAULT 'auto'")
        if "created_by" not in cols:
            conn.execute("ALTER TABLE memory ADD COLUMN created_by TEXT DEFAULT ''")

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = self._open_connection()
            self._tls.conn = conn
        return conn

    @property
    def fts_enabled(self) -> bool:
        return self._message_fts

    @property
    def memory_fts_enabled(self) -> bool:
        return self._memory_fts

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

    def _init_memory_fts(self, conn: sqlite3.Connection) -> bool:
        """memory 全文索引（trigram，KB/L1 关键词召回）。"""
        for tokenize in ("tokenize='trigram'", ""):
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
                    "title, content, project_id UNINDEXED, tags UNINDEXED"
                    + (", " + tokenize if tokenize else "")
                    + ")"
                )
                return True
            except sqlite3.OperationalError:
                conn.execute("DROP TABLE IF EXISTS memory_fts")
        return False

    def _backfill_memory_fts(self, conn: sqlite3.Connection) -> None:
        """已有 memory 行回填 FTS（幂等）。"""
        try:
            count = conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
            if count:
                return
            rows = conn.execute(
                "SELECT id, title, content, project_id, tags FROM memory"
            ).fetchall()
            for r in rows:
                conn.execute(
                    "INSERT INTO memory_fts(rowid, title, content, project_id, tags) "
                    "VALUES (?,?,?,?,?)",
                    (r[0], r[1] or "", r[2] or "", r[3] or "", r[4] or "[]"),
                )
        except sqlite3.OperationalError:
            pass

    def close(self) -> None:
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            conn.close()
            self._tls.conn = None
