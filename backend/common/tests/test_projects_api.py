#!/usr/bin/env python3
"""Hub 项目相关路由测试（发起 / 取消 / 读交付物 / 安全校验）。

用 FastAPI TestClient 打 server.app；用 monkeypatch 隔离后台内核线程、
临时 PROJECTS_DIR 与临时 SQLite，避免触达真实 opencode 与真实业务数据。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import hub.api.server as srv  # noqa: E402
import hub.paths as hub_paths  # noqa: E402
import common.store as cstore  # noqa: E402
import common.project_admin as padmin  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(srv.app)


def test_slug():
    assert srv._slug("Hello World!! 你好") == "Hello_World_你好"
    assert srv._slug("") == "project"
    assert len(srv._slug("x" * 100)) == 24


def test_run_requires_goal(client):
    r = client.post("/api/projects/run", json={})
    assert r.status_code == 400


def test_run_starts_background(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(srv, "_run_kernel_bg",
                        lambda *a, **k: calls.setdefault("hit", True))
    pid = "ui_test_proj_unit"
    srv._KERNEL_RUNS.pop(pid, None)
    r = client.post("/api/projects/run",
                    json={"goal": "做点事", "project_id": pid, "mode": "one_shot"})
    assert r.status_code == 200
    body = r.json()
    assert body["started"] is True and body["project_id"] == pid
    # 重复发起（标记 running）→ 409
    srv._KERNEL_RUNS[pid] = {"running": True, "error": None}
    r2 = client.post("/api/projects/run", json={"goal": "x", "project_id": pid})
    assert r2.status_code == 409
    srv._KERNEL_RUNS.pop(pid, None)


def test_deliverable_path_safety(client):
    assert client.get("/api/projects/p/deliverable/bad..id").status_code == 400
    assert client.get("/api/projects/ab../deliverable/t1").status_code == 400


def test_deliverable_read(client, tmp_path, monkeypatch):
    monkeypatch.setattr(hub_paths, "PROJECTS_DIR", tmp_path)
    d = tmp_path / "proj1" / "deliverables"
    d.mkdir(parents=True)
    (d / "t1_deliverable.md").write_text("# 标题\n正文内容", encoding="utf-8")

    r = client.get("/api/projects/proj1/deliverable/t1")
    assert r.status_code == 200 and r.json()["exists"] is True
    assert "正文内容" in r.json()["content"]

    miss = client.get("/api/projects/proj1/deliverable/t9")
    assert miss.status_code == 200 and miss.json()["exists"] is False


def test_cancel(client, tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    orig = cstore.Store
    seed = orig(db)
    seed.upsert_project("p_run", title="R", status="in_progress")
    seed.upsert_project("p_done", title="D", status="completed")
    seed.close()
    monkeypatch.setattr(cstore, "Store", lambda *a, **k: orig(db))

    assert client.post("/api/projects/nope/cancel").status_code == 404

    ok = client.post("/api/projects/p_run/cancel")
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    assert orig(db).get_project("p_run")["status"] == "cancelled"

    done = client.post("/api/projects/p_done/cancel")
    assert done.status_code == 200 and done.json()["success"] is False


def test_delete(client, tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    orig = cstore.Store
    seed = orig(db)
    seed.upsert_project("p_del", title="D", status="completed")
    seed.close()
    monkeypatch.setattr(cstore, "Store", lambda *a, **k: orig(db))
    calls = {}

    def _stub_delete(pid, **k):
        calls["pid"] = pid
        return {"interactions": 0, "files_removed": 0, "project_dir_removed": False}
    monkeypatch.setattr(padmin, "delete_project", _stub_delete)

    assert client.request("DELETE", "/api/projects/ab..").status_code == 400
    assert client.request("DELETE", "/api/projects/nope").status_code == 404

    srv._KERNEL_RUNS["p_del"] = {"running": True, "error": None}
    assert client.request("DELETE", "/api/projects/p_del").status_code == 409
    srv._KERNEL_RUNS.pop("p_del", None)

    ok = client.request("DELETE", "/api/projects/p_del")
    assert ok.status_code == 200 and ok.json()["success"] is True
    assert calls["pid"] == "p_del"
