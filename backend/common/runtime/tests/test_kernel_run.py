#!/usr/bin/env python3
"""hub.services.kernel_run 单元测试 — Store meta.hub_kernel_run 读写。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from common.store.store import Store  # noqa: E402
from hub.services import kernel_run  # noqa: E402


@pytest.fixture()
def store(tmp_path, monkeypatch):
    import common.store.store as cstore

    db = tmp_path / "state.db"
    orig = cstore.Store
    monkeypatch.setattr(cstore, "Store", lambda *a, **k: orig(db))
    s = orig(db)
    s.upsert_project("p1", title="T", status="in_progress")
    s.close()
    return db


def test_get_default_not_running(store):
    assert kernel_run._get_kernel_run("p1") == {"running": False, "error": None}
    assert kernel_run._is_kernel_running("p1") is False


def test_set_and_get_running(store):
    kernel_run._set_kernel_run("p1", running=True)
    assert kernel_run._get_kernel_run("p1") == {"running": True, "error": None}
    assert kernel_run._is_kernel_running("p1") is True


def test_set_with_error(store):
    kernel_run._set_kernel_run("p1", running=False, error="boom")
    assert kernel_run._get_kernel_run("p1") == {"running": False, "error": "boom"}


def test_clear_kernel_run(store):
    kernel_run._set_kernel_run("p1", running=True, error="x")
    kernel_run._clear_kernel_run("p1")
    assert kernel_run._get_kernel_run("p1") == {"running": False, "error": None}


def test_reconcile_stale_kernel_runs(store):
    kernel_run._set_kernel_run("p1", running=True)
    cleared = kernel_run._reconcile_stale_kernel_runs()
    assert cleared >= 1
    run = kernel_run._get_kernel_run("p1")
    assert run["running"] is False
    assert run["error"] == "hub_restarted"


def test_missing_project_no_op(store):
    kernel_run._set_kernel_run("ghost", running=True)
    assert kernel_run._get_kernel_run("ghost") == {"running": False, "error": None}
