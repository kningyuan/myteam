#!/usr/bin/env python3
"""Hub 只读可观测路由测试（Phase 8 step 2）。

用 FastAPI TestClient 打 observability_api 路由，数据用临时 SQLite store 注入。
只挂载该 router（不拉起整个 Hub），避免引入重依赖。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "skill" / "team"))
sys.path.insert(0, str(ROOT / "backend"))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from common.store import Store  # noqa: E402
from hub.api import observability_api as obs_api  # noqa: E402

IID = "p1:task_001:execute:1"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    seed = Store(db)
    seed.upsert_project("p1", title="GEO", status="in_progress")
    seed.upsert_task("p1", "task_001", agent="researcher", task_type="research",
                     status="needs_review")
    seed.create_interaction(IID, "execute", "p1", task_id="task_001", agent_id="researcher")
    seed.append_run_event(IID, "step_start", {"i": 0})
    seed.append_run_event(IID, "step_finish", {"tokens": {"total": 123}})
    seed.update_interaction(IID, status="done", tokens=123, response_ref="x.response")
    seed.memory_write("p1", "GEO 要点", "结构化数据 + 引用策略是核心", task_id="task_001",
                      tags=["geo"])
    seed.close()

    # 每次请求开新连接指向同一临时库（handler 会 close）
    monkeypatch.setattr(obs_api, "_store", lambda: Store(db))

    app = FastAPI()
    app.include_router(obs_api.router)
    return TestClient(app)


def test_overview(client):
    r = client.get("/api/obs/projects/p1/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "in_progress"
    assert data["task_counts"] == {"needs_review": 1}
    assert data["progress"] == 1.0


def test_list_projects_route(client):
    r = client.get("/api/obs/projects")
    assert r.status_code == 200
    projects = r.json()["projects"]
    assert any(p["id"] == "p1" and p["title"] == "GEO" for p in projects)


def test_task_types_route(client):
    r = client.get("/api/obs/task-types")
    assert r.status_code == 200
    tts = r.json()["task_types"]
    assert tts and all("task_type" in t and "outcome_kind" in t for t in tts)


def test_memory_route(client):
    r = client.get("/api/obs/memory")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    hit = next(m for m in data["memory"] if m["title"] == "GEO 要点")
    assert "结构化数据" in hit["preview"] and hit["tags"] == ["geo"]


def test_cost(client):
    r = client.get("/api/obs/projects/p1/cost")
    assert r.status_code == 200
    data = r.json()
    assert data["project"] == 123
    assert data["by_agent"] == {"researcher": 123}
    assert data["by_task"] == {"task_001": 123}


def test_fleet(client):
    r = client.get("/api/obs/projects/p1/fleet")
    assert r.json()["fleet"] == {"researcher": "done"}


def test_summary_route(client):
    r = client.get("/api/obs/summary")
    assert r.status_code == 200
    d = r.json()
    assert "totals" in d and d["totals"]["projects"] >= 1
    assert any(p["id"] == "p1" for p in d["projects"])


def test_project_events_route(client):
    r = client.get("/api/obs/projects/p1/events")
    assert r.status_code == 200
    feed = r.json()["events"]
    assert any(e["category"] == "interaction" and e["kind"] == "execute" for e in feed)
    kinds = [e["kind"] for e in feed]
    assert "step_start" not in kinds and "step_finish" not in kinds  # 低层噪声不进项目流


def test_task_detail_and_404(client):
    r = client.get("/api/obs/projects/p1/tasks/task_001")
    assert r.status_code == 200
    assert len(r.json()["interactions"]) == 1
    assert client.get("/api/obs/projects/p1/tasks/nope").status_code == 404


def test_timeline(client):
    r = client.get(f"/api/obs/interactions/{IID}/timeline")
    kinds = [e["kind"] for e in r.json()["timeline"]]
    assert kinds == ["step_start", "step_finish"]


def test_project_stream_until_done(client):
    # 终态项目：stream 应推一帧 data 后立即收尾 [DONE]
    s = obs_api._store()
    s.upsert_project("pdone", title="done", status="completed")
    s.close()
    with client.stream("GET", "/api/obs/projects/pdone/stream") as resp:
        assert resp.status_code == 200
        body = ""
        for chunk in resp.iter_text():
            body += chunk
            if "[DONE]" in body:
                break
    assert '"status": "completed"' in body
    assert "[DONE]" in body


def test_events_sse_streams_until_done(client):
    with client.stream("GET", f"/api/obs/interactions/{IID}/events") as resp:
        assert resp.status_code == 200
        body = ""
        for chunk in resp.iter_text():
            body += chunk
            if "[DONE]" in body:
                break
    assert "step_start" in body
    assert "step_finish" in body
    assert "[DONE]" in body
