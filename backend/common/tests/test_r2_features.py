#!/usr/bin/env python3
"""Store workspace_event + JobSupervisor 单元测试。

原 R2 ProjectionRunner / EventPipeline 模块已移除；本文件保留 Store 与
JobSupervisor 仍被生产使用的路径覆盖。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from common.job_supervisor import JobSupervisor
from common.store import Store


@pytest.fixture()
def store():
    db = Path(tempfile.mktemp(suffix=".db"))
    s = Store(db)
    yield s
    s.close()
    if db.exists():
        db.unlink()


class TestWorkspaceEventStore:
    def test_append_and_list(self, store):
        eid = store.append_workspace_event({
            "type": "project.created",
            "source": "test",
            "payload": json.dumps({"p": "1"}),
            "metadata": json.dumps({"project_id": "p001"}),
            "timestamp": "2026-06-07T00:00:00Z",
        })
        assert eid and eid.startswith("evt_")
        events = store.list_workspace_events(project_id="p001")
        assert len(events) == 1

    def test_list_filter_by_type(self, store):
        store.append_workspace_event({
            "type": "project.created",
            "source": "t",
            "payload": "{}",
            "metadata": '{"project_id":"p1"}',
            "timestamp": "1",
        })
        store.append_workspace_event({
            "type": "project.completed",
            "source": "t",
            "payload": "{}",
            "metadata": '{"project_id":"p1"}',
            "timestamp": "2",
        })
        assert len(store.list_workspace_events(type="project.created")) == 1

    def test_list_empty_project(self, store):
        assert store.list_workspace_events(project_id="nonexistent") == []


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
        store.create_job("po", pid=99999)
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
