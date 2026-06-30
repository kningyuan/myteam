#!/usr/bin/env python3
"""Phase 3/4 Store 扩展测试。"""
from __future__ import annotations

import pytest

from common.roundtable.group_message_store import persist_group_message
from common.observability.ops_log import maybe_log_task_completion
from common.store.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_publish_and_audit_logs(store, tmp_path, monkeypatch):
    monkeypatch.setattr("common.paths.deliverables_dir", lambda pid: tmp_path / pid)
    monkeypatch.setattr("common.store.store.Store", lambda db_path=None: store)
    dv = tmp_path / "p1" / "t-pub_deliverable.md"
    dv.parent.mkdir(parents=True)
    dv.write_text("# publish\n", encoding="utf-8")

    store.insert_publish_log("p1", task_id="t-pub", platform="zhihu", deliverable=str(dv))
    store.insert_audit_log("p1", task_id="t-geo", audit_type="geo", deliverable=str(dv))

    assert len(store.list_publish_logs("p1")) == 1
    assert len(store.list_audit_logs("p1")) == 1

    maybe_log_task_completion("p1", "t-pub", "publish-post", status="completed")
    maybe_log_task_completion("p1", "t-geo", "geo-audit", status="completed")
    assert len(store.list_publish_logs("p1")) >= 2
    assert len(store.list_audit_logs("p1")) >= 2


def test_agent_config_and_workflow_version(store):
    ver = store.upsert_agent_config("product", {"backend": "claude", "model": "x"})
    assert ver >= 1
    row = store.get_agent_config_row("product")
    assert row and row["version"] == ver

    wver = store.save_workflow_version("wf-test", {"id": "wf-test", "tasks": []})
    assert wver == 1
    wver2 = store.save_workflow_version("wf-test", {"id": "wf-test", "tasks": [{"id": "t1"}]})
    assert wver2 == 2


def test_group_message_persisted_to_conversation(store, monkeypatch):
    monkeypatch.setattr("common.store.store.Store", lambda db_path=None: store)
    persist_group_message("g_test", "main", "hello group", project_id="proj-x")
    conv = store.get_conversation("group:g_test")
    assert conv is not None
    assert conv.get("project_id") == "proj-x"
    msgs = store.list_messages("group:g_test")
    assert msgs and msgs[-1]["text"] == "hello group"
