#!/usr/bin/env python3
"""断点续跑与孤儿响应回收测试（D8）。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig, reconcile_on_start  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.run_kernel import resume_project  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    cfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, cfg
    store.close()


def _code_exec(iid: str, tid: str, project_id: str) -> dict:
    return {
        "interaction_id": iid, "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": "ok"},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": f"{tid}/", "format": "code_project",
                                            "title": "hw"}}},
        "notes": "done",
    }


def test_resume_adopts_stuck_t1_and_continues(env, monkeypatch):
    """模拟内核线程中断：t1 响应在磁盘、interaction=running，resume 应结算 t1 并继续。"""
    store, wcfg = env
    pid = "proj_recover"
    store.upsert_project(pid, status="in_progress", meta={"goal": "g"})
    store.upsert_task(pid, "t1", name="写脚本", agent="developer", task_type="code-writing",
                      status="in_progress", dependencies=[])
    store.upsert_task(pid, "t2", name="测试", agent="tester", task_type="test-plan",
                      status="pending", dependencies=["t1"])

    iid = f"{pid}:t1:execute:1"
    store.create_interaction(iid, "execute", pid, task_id="t1", agent_id="developer")
    store.update_interaction(iid, status="running")

    proj_dir = paths.deliverables_dir(pid) / "t1"
    proj_dir.mkdir(parents=True)
    (proj_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (proj_dir / "README.md").write_text("# 标题\n\n说明\n", encoding="utf-8")

    agent = "developer"
    trig = paths.trigger_dir(agent)
    resp_dir = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_code_exec(iid, "t1", pid), resp_dir / f"{iid}.response")

    t2_done = {"done": False}

    def transport(ctx):
        req = ctx.request
        if req.task_id == "t2":
            spec = get_spec("test-plan")
            rel = "t2_deliverable.md"
            dv = paths.deliverables_dir(req.project_id) / rel
            content = "# 标题\n" + "".join(f"## {s}\n内容\n" for s in spec.required_sections)
            dv.write_text(content, encoding="utf-8")
            submit({
                "interaction_id": req.interaction_id, "kind": "execute", "status": "ok",
                "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
                "result": {"outcome": {"kind": "artifact",
                                         "artifact": {"path": rel, "title": "plan"}}},
            }, paths.response_dir(req.agent_id) / f"{req.interaction_id}.response")
            t2_done["done"] = True

    port = AgentPort(transport, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig())
    out = proc.resume(pid)

    assert store.get_interaction(iid)["status"] == "done"
    assert store.get_task(pid, "t1")["status"] in ("completed", "needs_review")
    assert t2_done["done"]
    assert out.status in ("completed", "partially_failed")
