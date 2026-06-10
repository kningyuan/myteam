#!/usr/bin/env python3
"""R2/R3 基础设施单元测试 — workspace_event / projection / pipeline / job / agent_runtime。

覆盖 ProjectionRunner、EventPipeline、JobSupervisor 等 R2/R3 期基础设施层，
**非 L2 发版门禁**。上述模块在 L2 尚未产品化接通主链路；本套测试 **L2 发版不阻塞**。

运行：
    PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_r2_features.py -q
L2 门禁套件可排除：
    pytest -m "not r2_infra"
"""

import sys, json, asyncio, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.store import Store
from common.workspace_events import ProjectionRunner, _map_to_workspace_event, _resolve_project_id
from common.event_handler import EventPipeline
from common.job_supervisor import JobSupervisor

pytestmark = pytest.mark.r2_infra

# ── Fixtures ────────────────────────────────────────────

@pytest.fixture()
def store():
    db = Path(tempfile.mktemp(suffix=".db"))
    s = Store(db)
    yield s
    s.close()
    if db.exists():
        db.unlink()


@pytest.fixture()
def seeded_store(store):
    store.upsert_project("p001", title="Test", status="in_progress")
    store.upsert_task("p001", "t1", agent="research", task_type="research", status="needs_review")
    store.create_interaction("p001:t1:execute", "execute", "p001", task_id="t1", agent_id="research")
    store.append_run_event("p001:t1:execute", "step_start", {"i": 0})
    store.append_run_event("p001:t1:execute", "gate_passed", {"result": "ok"})
    return store


# ── R2-1 WorkspaceEvent ─────────────────────────────────

class TestWorkspaceEvent:
    def test_append_and_list(self, store):
        eid = store.append_workspace_event({
            "type": "project.created", "source": "test",
            "payload": json.dumps({"p": "1"}),
            "metadata": json.dumps({"project_id": "p001"}),
            "timestamp": "2026-06-07T00:00:00Z",
        })
        assert eid and eid.startswith("evt_")
        events = store.list_workspace_events(project_id="p001")
        assert len(events) == 1

    def test_list_filter_by_type(self, store):
        store.append_workspace_event({"type": "project.created", "source": "t", "payload": "{}", "metadata": '{"project_id":"p1"}', "timestamp": "1"})
        store.append_workspace_event({"type": "project.completed", "source": "t", "payload": "{}", "metadata": '{"project_id":"p1"}', "timestamp": "2"})
        assert len(store.list_workspace_events(type="project.created")) == 1

    def test_list_empty_project(self, store):
        assert store.list_workspace_events(project_id="nonexistent") == []


# ── R2-1a ProjectionRunner ──────────────────────────────

class TestProjectionRunner:
    def test_map_step_start(self):
        row = {"id": 1, "kind": "step_start", "payload": "{}", "interaction_id": "p001:t1:execute", "ts": "1"}
        ev = _map_to_workspace_event(row, "p001")
        assert ev["type"] == "project.task.updated"
        assert "running" in ev["payload"]

    def test_map_gate_passed(self):
        row = {"id": 2, "kind": "gate_passed", "payload": "{}", "interaction_id": "p001:t1:execute", "ts": "1"}
        ev = _map_to_workspace_event(row, "p001")
        assert ev["type"] == "project.gate.completed"

    def test_map_gate_failed(self):
        row = {"id": 3, "kind": "gate_failed", "payload": '{"failures":["格式错误"]}', "interaction_id": "p001:t1:execute", "ts": "1"}
        ev = _map_to_workspace_event(row, "p001")
        assert ev["type"] == "project.gate.rejected"

    def test_map_blocked(self):
        row = {"id": 4, "kind": "blocked", "payload": '{"reason":"超时"}', "interaction_id": "p001:t1:execute", "ts": "1"}
        ev = _map_to_workspace_event(row, "p001")
        assert ev["type"] == "project.task.blocked"

    def test_map_budget_alert(self):
        row = {"id": 5, "kind": "budget_alert", "payload": '{"used":85}', "interaction_id": "p001:budget", "ts": "1"}
        ev = _map_to_workspace_event(row, "p001")
        assert ev["type"] == "budget.threshold.reached"

    def test_map_skip_noise(self):
        row = {"id": 6, "kind": "text", "payload": '"hello"', "interaction_id": "p001:t1:execute", "ts": "1"}
        assert _map_to_workspace_event(row, "p001") is None
        row2 = {"id": 7, "kind": "tool_use", "payload": "{}", "interaction_id": "p001:t1:execute", "ts": "1"}
        assert _map_to_workspace_event(row2, "p001") is None

    def test_resolve_project_id(self, store):
        # prefix-based
        assert _resolve_project_id(store, "p001:t1:execute") == "p001"
        assert _resolve_project_id(store, "demo-123:team_config") == "demo-123"
        assert _resolve_project_id(store, "") is None

    def test_poll_once(self, seeded_store):
        runner = ProjectionRunner(seeded_store)
        count = asyncio.run(runner.poll_once())
        assert count >= 1, f"expected >=1 projected events, got {count}"
        events = seeded_store.list_workspace_events(project_id="p001")
        assert len(events) >= 1

    def test_checkpoint_persistence(self, seeded_store):
        runner = ProjectionRunner(seeded_store)
        asyncio.run(runner.poll_once())
        cp = seeded_store.get_projection_checkpoint()
        assert cp > 0
        # second poll should project 0 new events
        count2 = asyncio.run(runner.poll_once())
        assert count2 == 0


# ── R2-4 EventPipeline ──────────────────────────────────

class TestEventPipeline:
    def test_register_and_dispatch(self):
        calls = []
        def handler(ev): calls.append(ev["type"])
        EventPipeline.register("test.event", handler)
        EventPipeline.dispatch({"type": "test.event"})
        assert len(calls) == 1
        assert calls[0] == "test.event"

    def test_handler_exception_isolation(self):
        calls = []
        def broken(ev): raise ValueError("broken")
        def good(ev): calls.append("ok")
        EventPipeline.register("test.broken", broken)
        EventPipeline.register("test.broken", good)
        EventPipeline.dispatch({"type": "test.broken"})
        assert calls == ["ok"]

    def test_registered_types(self):
        types = EventPipeline.registered_types()
        assert "project.task.updated" in types
        assert len(types) >= 10

    def test_unknown_type(self):
        EventPipeline.dispatch({"type": "nonexistent"})
        # should not raise


# ── R2-3 Job Supervisor ─────────────────────────────────

class TestJobSupervisor:
    def test_create_and_query(self, store):
        store.upsert_project("pj", title="J", status="in_progress")
        jid = store.create_job("pj", pid=1234)
        job = store.get_latest_job("pj")
        assert job["status"] == "running"
        assert job["job_id"] == jid

    def test_cancel_job(self, store):
        store.upsert_project("pc", title="C", status="in_progress")
        store.create_job("pc", pid=0)
        jsv = JobSupervisor(store)
        cancelled = jsv.cancel_job("pc")
        assert cancelled is True
        job = store.get_latest_job("pc")
        assert job["status"] == "cancelled"

    def test_list_jobs(self, store):
        store.upsert_project("pa", title="A", status="in_progress")
        store.create_job("pa", pid=1)
        jobs = store.list_jobs()
        assert len(jobs) >= 1

    def test_orphan_scan(self, store):
        store.upsert_project("po", title="O", status="in_progress")
        store.create_job("po", pid=99999)  # pid 99999 doesn't exist
        jsv = JobSupervisor(store)
        orphans = jsv.resume_orphans()
        assert len(orphans) >= 1
        job = store.get_latest_job("po")
        assert job["status"] == "orphan"

    def test_upsert_agent_runtime(self, store):
        store.upsert_agent_runtime("agent1", status="busy", current_task="t1")
        rt = store.get_agent_runtime("agent1")
        assert rt["status"] == "busy"
        assert rt["current_task"] == "t1"

    def test_list_agent_runtimes(self, store):
        store.upsert_agent_runtime("agent_a", status="idle")
        store.upsert_agent_runtime("agent_b", status="busy")
        runtimes = store.list_agent_runtimes()
        assert len(runtimes) >= 2
