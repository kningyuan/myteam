#!/usr/bin/env python3
"""协作审计日志开关测试。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent.agent_port import AgentPort, finalize_interaction  # noqa: E402
from common.observability.audit_log import clip_json, clip_text, verify_audit_snapshot  # noqa: E402
from common.store.store import Store  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    store.upsert_project("pro_audit")
    store.upsert_task("pro_audit", "t1")
    yield store
    store.close()


def test_clip_text_truncates():
    big = "中" * 1000
    out = clip_text(big, max_bytes=50)
    assert "截断" in out


def test_clip_json_large_object():
    obj = {"data": "x" * 10000}
    clipped = clip_json(obj, max_bytes=100)
    assert clipped.get("_truncated") is True


def test_audit_disabled_no_request_snapshot(env, monkeypatch):
    store = env
    monkeypatch.setattr("common.agent.agent_port.audit_enabled", lambda: False)

    def transport(ctx):
        pass

    port = AgentPort(transport, store=store)
    req = {
        "interaction_id": "pro_audit:t1:execute:1", "kind": "execute",
        "project_id": "pro_audit", "task_id": "t1", "agent_id": "dev",
        "intent": "do", "input": {}, "response_schema": "execute.result@1.0",
    }
    port.run(req)
    kinds = [e["kind"] for e in store.list_run_events("pro_audit:t1:execute:1")]
    assert "request_snapshot" not in kinds


def test_audit_enabled_writes_request_and_response_snapshot(env, monkeypatch):
    store = env
    monkeypatch.setattr("common.agent.agent_port.audit_enabled", lambda: True)

    def transport(ctx):
        pass

    port = AgentPort(transport, store=store)
    req = {
        "interaction_id": "pro_audit:t1:execute:1", "kind": "execute",
        "project_id": "pro_audit", "task_id": "t1", "agent_id": "dev",
        "intent": "do", "input": {"task": {"id": "t1"}}, "response_schema": "execute.result@1.0",
    }
    port.run(req)
    kinds = [e["kind"] for e in store.list_run_events("pro_audit:t1:execute:1")]
    assert "request_snapshot" in kinds
    snap = next(e for e in store.list_run_events("pro_audit:t1:execute:1")
                if e["kind"] == "request_snapshot")
    assert snap["payload"]["request"]["interaction_id"] == "pro_audit:t1:execute:1"
    assert snap["payload"]["agent_id"] == "dev"
    assert snap["payload"]["outcome"] == "dispatched"
    assert snap["payload"].get("request_hash")
    assert verify_audit_snapshot(snap["payload"], "request") is True
    tampered = dict(snap["payload"])
    tampered["request"] = {**tampered["request"], "agent_id": "other"}
    assert verify_audit_snapshot(tampered, "request") is False

    resp_path = paths.response_dir("dev") / "pro_audit:t1:execute:2.response"
    resp_path.parent.mkdir(parents=True, exist_ok=True)
    resp = {
        "interaction_id": "pro_audit:t1:execute:2", "kind": "execute", "status": "ok",
        "result": {"outcome": {"kind": "artifact", "artifact": {"path": "t1.md"}}},
    }
    store.create_interaction("pro_audit:t1:execute:2", "execute", "pro_audit",
                             task_id="t1", agent_id="dev")
    finalize_interaction(store, "pro_audit:t1:execute:2", resp_path, resp)
    kinds2 = [e["kind"] for e in store.list_run_events("pro_audit:t1:execute:2")]
    assert "response_snapshot" in kinds2
    resp_snap = next(e for e in store.list_run_events("pro_audit:t1:execute:2")
                     if e["kind"] == "response_snapshot")
    assert resp_snap["payload"]["agent_id"] == "dev"
    assert resp_snap["payload"]["outcome"] == "ok"
    assert resp_snap["payload"]["outcome_kind"] == "artifact"
    assert resp_snap["payload"].get("response_hash")
    assert verify_audit_snapshot(resp_snap["payload"], "response") is True
