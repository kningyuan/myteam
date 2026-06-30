#!/usr/bin/env python3
"""StoreBackend pluggable persistence tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store.store import Store, _SCHEMA  # noqa: E402
from common.store.store_backend import StoreBackend  # noqa: E402
from common.store.store_sqlite import SQLiteStoreBackend  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_default_backend_is_sqlite(tmp_path):
    s = Store(tmp_path / "state.db")
    try:
        assert isinstance(s.backend, SQLiteStoreBackend)
        assert isinstance(s.backend, StoreBackend)
    finally:
        s.close()


def test_explicit_sqlite_backend(tmp_path):
    db = tmp_path / "explicit.db"
    backend = SQLiteStoreBackend(db, _SCHEMA)
    s = Store(db, backend=backend)
    try:
        assert s.backend is backend
        s.upsert_project("p1", title="via-backend")
        assert s.get_project("p1")["title"] == "via-backend"
    finally:
        s.close()


def test_backend_close_releases_connection(tmp_path):
    db = tmp_path / "close.db"
    backend = SQLiteStoreBackend(db, _SCHEMA)
    s = Store(db, backend=backend)
    _ = s.backend.connection
    s.close()
    assert getattr(backend._tls, "conn", None) is None


def test_schema_idempotent_via_backend(tmp_path):
    db = tmp_path / "idem.db"
    SQLiteStoreBackend(db, _SCHEMA).close()
    s = Store(db)
    s.upsert_project("p1")
    s.close()


def test_fts_flag_exposed(tmp_path):
    s = Store(tmp_path / "fts.db")
    try:
        assert isinstance(s._fts, bool)
    finally:
        s.close()
