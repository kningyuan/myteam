#!/usr/bin/env python3
"""Store 并发写入：WAL + 每线程独立连接，不应出现 database is locked。"""
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_store_concurrent_writes_no_database_locked(store):
    project_id = "pro_conc"
    store.upsert_project(project_id)
    for i in range(4):
        store.create_interaction(f"i{i}", "execute", project_id, task_id=f"task_{i}")

    errors: list[str] = []
    err_lock = threading.Lock()
    start = threading.Barrier(4)

    def worker(tid: int) -> None:
        start.wait()
        try:
            for n in range(10):
                store.upsert_task(
                    project_id, f"task_{tid}_{n}", name=f"t{tid}-{n}", agent="research"
                )
                store.append_run_event(f"i{tid}", "tick", {"n": n})
        except sqlite3.OperationalError as exc:
            with err_lock:
                errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=4)
        assert not t.is_alive(), "并发写入线程超时"

    locked = [e for e in errors if "database is locked" in e.lower()]
    assert not locked, f"不应出现 database is locked: {locked}"
    assert not errors, errors
