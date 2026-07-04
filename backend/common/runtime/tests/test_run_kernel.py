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
from common.agent.agent_port import WatchdogConfig  # noqa: E402
from common.gate.registry import get_spec  # noqa: E402
from common.runtime.run_kernel import run_project  # noqa: E402
from common.store.store import Store  # noqa: E402
from common.delivery.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    # 预建 research workspace，避免 auto_create_agent 写入空 task_types 到 registry
    # 导致 check_plan 能力边界校验失败
    paths.workspace_dir("research").mkdir(parents=True, exist_ok=True)
    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def _valid_content(task_type: str) -> str:
    from common.gate.registry import resolve_format_spec
    spec = resolve_format_spec(task_type) or get_spec(task_type)
    out = ["# 标题\n"]
    for s in spec.required_sections:
        out.append(f"## {s}\n这是「{s}」的足够具体的内容，覆盖要点与细节，便于评审与复用。\n")
    body = "\n".join(out)
    if task_type == "research":
        matrix = (
            "\n| 对象 | 核心功能 | 用户画像 | 变现模式 | 用户评价 |\n"
            "|---|---|---|---|---|\n"
            "| A | 功能X [S1] | 画像P [S2] | 订阅 [S1] | 好评 [S2] |\n"
            "| B | 功能Y [S2] | 画像Q [S1] | 广告 [S1] | 中评 [S2] |\n\n"
            "核心功能与用户画像均有数据支撑，变现模式涵盖订阅与广告。\n"
        )
        body = body.replace("## 关键发现\n", "## 关键发现\n" + matrix, 1)
    return body


def _fake_transport(ctx):
    """按 kind 模拟 Main / worker 的 submit 回写。"""
    req = ctx.request
    iid = req.interaction_id
    ctx.emit("step_start")
    if req.kind == "team_config":
        resp = {"interaction_id": iid, "kind": "team_config", "status": "ok",
                "result": {"agents": ["research"]}}
    elif req.kind == "task_plan":
        resp = {"interaction_id": iid, "kind": "task_plan", "status": "ok",
                "result": {"tasks": [
                    {"id": "t1", "name": "调研", "agent": "research",
                     "task_type": "research", "description": "做 GEO 调研", "dependencies": []},
                ]}}
    elif req.kind == "execute":
        rel = f"{req.task_id}_deliverable.md"
        # light_v1 过程产物（覆盖 scaffold 模板版）
        base = paths.deliverables_dir(req.project_id)
        base.mkdir(parents=True, exist_ok=True)
        (base / "align.md").write_text(
            "# Align\n\n## 对象\n\n目标\n\n## 输入\n\n输入\n\n## 成功标准\n\n标准\n\n## 非目标\n\n无\n",
            encoding="utf-8")
        (base / "verify.log").write_text("PASS: self-check ok\n", encoding="utf-8")
        (base / rel).write_text(
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


def test_main_cli_parses_and_dispatches(monkeypatch, capsys):
    """CLI 入口（SKILL.md 现指向它）：argv → run_project，参数透传正确。"""
    import common.runtime.run_kernel as rk
    from common.process.process import ProjectOutcome, TaskOutcome

    captured = {}

    def fake_run_project(project_id, **kw):
        captured["project_id"] = project_id
        captured.update(kw)
        return ProjectOutcome(project_id, "completed",
                              {"t1": TaskOutcome("t1", "completed", "", 1)})

    monkeypatch.setattr(rk, "run_project", fake_run_project)
    rc = rk.main(["proj_x", "--goal", "做点事", "--title", "T",
                  "--mode", "recurring", "--budget", "5000"])

    assert rc == 0
    assert captured["project_id"] == "proj_x"
    assert captured["goal"] == "做点事"
    assert captured["mode"] == "recurring"
    assert captured["token_budget"] == 5000
    assert '"status": "completed"' in capsys.readouterr().out


def test_hub_path_merges_workflow_parallel_flags(env, monkeypatch):
    """Hub 传入预建 config 时，workflow 的 parallel / skill_extract / review / split 标志须合并。"""
    import common.runtime.run_kernel as rk
    from common.process.process_types import ProcessConfig

    store, wcfg = env

    # workflow roster 需要 workspace
    paths.workspace_dir("research").mkdir(parents=True, exist_ok=True)

    # Hub 预建的 config（parallel_enabled 默认 False）
    pre_cfg = ProcessConfig()
    assert pre_cfg.parallel_enabled is False

    captured_cfg: dict = {}

    def fake_ensure_workflow_ready(wf_id, **_kw):
        from types import SimpleNamespace

        profile = SimpleNamespace(
            id=wf_id,
            roster=["research"],
            loops=[],
            options={
                "parallel_enabled": True,
                "max_parallel": 3,
                "skill_extract_enabled": True,
                "review_enabled": False,
                "split_enabled": False,
            },
        )
        profile.instantiate_tasks = lambda goal="": [
            {"id": "t1", "name": "调研", "agent": "research",
             "task_type": "research", "description": goal, "dependencies": []}
        ]
        return profile

    monkeypatch.setattr(rk, "_system_default_backend", lambda: "opencode")

    import common.workflow.workflow_bootstrap as wb
    monkeypatch.setattr(wb, "ensure_workflow_ready", fake_ensure_workflow_ready)

    from common.process.process import Process

    _orig_init = Process.__init__

    def _cap_init(self, store, port, cfg, hooks=None):
        captured_cfg["cfg"] = cfg
        _orig_init(self, store, port, cfg, hooks=hooks)

    monkeypatch.setattr(Process, "__init__", _cap_init)

    try:
        run_project("p_wf", goal="g", workflow="test-wf",
                    store=store, transport=_fake_transport, watchdog=wcfg,
                    config=pre_cfg)
    except Exception:
        pass

    cfg = captured_cfg.get("cfg")
    assert cfg is not None, "Process.__init__ was never called"
    assert cfg.parallel_enabled is True
    assert cfg.max_parallel == 3
    assert cfg.skill_extract_enabled is True


def test_reconcile_runs_on_start(env):
    """启动对账：上次残留的 running interaction 被标 timed_out（D8）。"""
    store, wcfg = env
    store.create_interaction("stale", "execute", "p_demo", task_id="t9",
                             agent_id="research")
    store.update_interaction("stale", status="running")

    run_project("p_demo", goal="g", store=store, transport=_fake_transport, watchdog=wcfg)

    assert store.get_interaction("stale")["status"] == "timed_out"
