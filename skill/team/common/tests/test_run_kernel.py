#!/usr/bin/env python3
"""新内核运行时入口测试（Phase 8 step 4 准备）。

注入 fake transport（不跑真实 opencode），验证 run_project 把 goal 经
team_config → task_plan → execute 串成一条 DAG 并跑完、真相库状态正确。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import WatchdogConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.run_kernel import run_project  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def _valid_content(task_type: str) -> str:
    out = ["# 标题\n"]
    for s in get_spec(task_type).required_sections:
        out.append(f"## {s}\n这是「{s}」的足够具体的内容，覆盖要点与细节，便于评审与复用。\n")
    return "\n".join(out)


def _fake_transport(ctx):
    """按 kind 模拟 Main / worker 的 submit 回写。"""
    req = ctx.request
    iid = req.interaction_id
    ctx.emit("step_start")
    if req.kind == "team_config":
        resp = {"interaction_id": iid, "kind": "team_config", "status": "ok",
                "result": {"agents": ["researcher"]}}
    elif req.kind == "task_plan":
        resp = {"interaction_id": iid, "kind": "task_plan", "status": "ok",
                "result": {"tasks": [
                    {"id": "t1", "name": "调研", "agent": "researcher",
                     "task_type": "research", "description": "做 GEO 调研", "dependencies": []},
                ]}}
    elif req.kind == "execute":
        rel = f"{req.task_id}_deliverable.md"
        (paths.deliverables_dir(req.project_id) / rel).write_text(
            _valid_content(req.constraints.get("task_type", "research")), "utf-8")
        resp = {"interaction_id": iid, "kind": "execute", "status": "ok",
                "quality": {"score": 0.9, "known_gaps": [], "notes": "ok"},
                "result": {"outcome": {"kind": "artifact",
                                       "artifact": {"path": rel, "title": "x"}}}}
    else:
        return
    submit(resp, paths.response_dir(req.agent_id) / f"{iid}.response")


def test_run_project_goal_driven_end_to_end(env):
    store, wcfg = env
    out = run_project("p_demo", goal="提升网站 GEO", title="GEO",
                      store=store, transport=_fake_transport, watchdog=wcfg)

    assert out.status == "completed"
    assert out.tasks["t1"].status == "completed"
    # 真相库落地：项目 + 任务 + 上游决策 interaction 都在
    assert store.get_project("p_demo")["status"] == "completed"
    assert store.get_task("p_demo", "t1")["status"] == "completed"
    inter_kinds = {i["kind"] for i in store.list_interactions("p_demo")}
    assert {"team_config", "task_plan", "execute"} <= inter_kinds


def test_reconcile_runs_on_start(env):
    """启动对账：上次残留的 running interaction 被标 timed_out（D8）。"""
    store, wcfg = env
    store.create_interaction("stale", "execute", "p_demo", task_id="t9",
                             agent_id="researcher")
    store.update_interaction("stale", status="running")

    run_project("p_demo", goal="g", store=store, transport=_fake_transport, watchdog=wcfg)

    assert store.get_interaction("stale")["status"] == "timed_out"
