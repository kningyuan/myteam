#!/usr/bin/env python3
"""Phase 5 Process 单内核测试（D10 / D18）。

验证标准：DAG 串行跑通；门禁失败按阶梯升级（重试→failed→triage）；needs_review 不阻塞；
失败传播 blocked；项目级状态显式暴露。注入式 Transport，不依赖真实 opencode。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.process import Process, ProcessConfig, topological_order  # noqa: E402
from common.registry import get_spec  # noqa: E402
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


# ── 内容/信封工具 ────────────────────────────────────────────


def valid_content(task_type: str) -> str:
    spec = get_spec(task_type)
    out = ["# 标题\n"]
    for s in spec.required_sections:
        out.append(f"## {s}\n这是「{s}」的足够具体的内容，覆盖要点与细节，便于评审与复用。\n")
    return "\n".join(out)


def bad_content(task_type: str) -> str:
    spec = get_spec(task_type)
    secs = spec.required_sections[1:]  # 故意缺第一个必需章节
    out = ["# 标题\n"]
    for s in secs:
        out.append(f"## {s}\n这是「{s}」的足够具体的内容，覆盖要点与细节说明充分。\n")
    return "\n".join(out)


def exec_env(iid, rel_path, quality):
    return {
        "interaction_id": iid, "kind": "execute", "status": "ok", "quality": quality,
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": rel_path, "title": "x"}}},
    }


GOOD_Q = {"score": 0.9, "known_gaps": [], "notes": "ok"}


def _write_exec(ctx, content, quality):
    req = ctx.request
    rel = f"{req.task_id}_deliverable.md"
    dv = paths.deliverables_dir(req.project_id) / rel
    dv.write_text(content, encoding="utf-8")
    submit(exec_env(req.interaction_id, rel, quality),
           paths.response_dir(req.agent_id) / f"{req.interaction_id}.response")


def _port(store, wcfg, transport):
    return AgentPort(transport, store=store, config=wcfg)


# ── 测试 ─────────────────────────────────────────────────────


def test_topological_order_and_cycle():
    tasks = [{"id": "a", "dependencies": []}, {"id": "b", "dependencies": ["a"]}]
    assert topological_order(tasks) == ["a", "b"]
    with pytest.raises(ValueError):
        topological_order([{"id": "a", "dependencies": ["b"]},
                           {"id": "b", "dependencies": ["a"]}])


def test_happy_dag(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig())
    tasks = [
        {"id": "task_001", "agent": "researcher", "task_type": "research", "dependencies": []},
        {"id": "task_002", "agent": "researcher", "task_type": "research",
         "dependencies": ["task_001"]},
    ]
    out = proc.run("pro_x", agents=["researcher"], tasks=tasks)
    assert out.status == "completed"
    assert out.tasks["task_001"].status == "completed"
    assert out.tasks["task_002"].status == "completed"
    assert store.get_project("pro_x")["status"] == "completed"


def test_cancel_stops_dispatch(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        if ctx.request.task_id == "t1":
            store.set_project_status("pro_x", "cancelled")  # 外部取消（模拟 API）
        _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig())
    tasks = [
        {"id": "t1", "agent": "researcher", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "researcher", "task_type": "research", "dependencies": ["t1"]},
    ]
    out = proc.run("pro_x", agents=["researcher"], tasks=tasks)
    assert out.status == "cancelled"
    assert out.tasks["t2"].status == "blocked"
    assert store.get_project("pro_x")["status"] == "cancelled"


def test_gate_retry_then_pass(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        attempt = int(ctx.request.interaction_id.rsplit(":", 1)[-1])
        content = bad_content("research") if attempt == 1 else valid_content("research")
        _write_exec(ctx, content, GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_gate_retries=3))
    out = proc.run("pro_x", agents=["researcher"],
                   tasks=[{"id": "t1", "agent": "researcher", "task_type": "research",
                           "dependencies": []}])
    assert out.tasks["t1"].status == "completed"
    assert out.tasks["t1"].attempts == 2


def test_gate_exhausted_failed_blocks_dependents(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        if ctx.request.kind == "triage":
            submit({"interaction_id": ctx.request.interaction_id, "kind": "triage",
                    "status": "ok", "result": {"decision": "drop"}},
                   paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response")
            return
        _write_exec(ctx, bad_content("research"), GOOD_Q)  # 永远缺章节

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_gate_retries=2))
    tasks = [
        {"id": "t1", "agent": "researcher", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "researcher", "task_type": "research", "dependencies": ["t1"]},
    ]
    out = proc.run("pro_x", agents=["researcher"], tasks=tasks)
    assert out.tasks["t1"].status == "failed"
    assert out.tasks["t2"].status == "blocked"
    assert out.status == "failed"


def test_needs_review_not_blocking(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        # t1 自评有 known_gaps → needs_review；t2 正常
        q = {"score": 0.9, "known_gaps": ["数据样本偏少"], "notes": ""} \
            if ctx.request.task_id == "t1" else GOOD_Q
        _write_exec(ctx, valid_content("research"), q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(needs_review_blocks=False))
    tasks = [
        {"id": "t1", "agent": "researcher", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "researcher", "task_type": "research", "dependencies": ["t1"]},
    ]
    out = proc.run("pro_x", agents=["researcher"], tasks=tasks)
    assert out.tasks["t1"].status == "needs_review"
    assert out.tasks["t2"].status == "completed"  # 未被阻塞
    assert out.status == "completed"


def test_needs_review_blocking_when_configured(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        q = {"score": 0.3, "known_gaps": [], "notes": ""} \
            if ctx.request.task_id == "t1" else GOOD_Q
        _write_exec(ctx, valid_content("research"), q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(needs_review_blocks=True, quality_floor=0.6))
    tasks = [
        {"id": "t1", "agent": "researcher", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "researcher", "task_type": "research", "dependencies": ["t1"]},
    ]
    out = proc.run("pro_x", agents=["researcher"], tasks=tasks)
    assert out.tasks["t1"].status == "needs_review"
    assert out.tasks["t2"].status == "blocked"


def test_triage_reassign_then_succeed(env):
    store, wcfg = env
    calls = {"exec": 0}

    def transport(ctx):
        ctx.emit("step_start")
        if ctx.request.kind == "triage":
            submit({"interaction_id": ctx.request.interaction_id, "kind": "triage",
                    "status": "ok",
                    "result": {"decision": "reassign", "target_agent": "seo"}},
                   paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response")
            return
        calls["exec"] += 1
        # 第一个 agent(researcher) 永远失败；reassign 到 seo 后成功
        content = valid_content("research") if ctx.request.agent_id == "seo" \
            else bad_content("research")
        _write_exec(ctx, content, GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_gate_retries=1))
    out = proc.run("pro_x", agents=["researcher", "seo"],
                   tasks=[{"id": "t1", "agent": "researcher", "task_type": "research",
                           "dependencies": []}])
    assert out.tasks["t1"].status == "completed"
    assert store.get_task("pro_x", "t1")["agent"] == "seo"


def test_full_flow_team_config_and_task_plan(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        k = ctx.request.kind
        rp = paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response"
        if k == "team_config":
            submit({"interaction_id": ctx.request.interaction_id, "kind": "team_config",
                    "status": "ok", "result": {"agents": ["researcher"]}}, rp)
        elif k == "task_plan":
            submit({"interaction_id": ctx.request.interaction_id, "kind": "task_plan",
                    "status": "ok", "result": {"tasks": [{
                        "id": "task_001", "name": "调研", "agent": "researcher",
                        "task_type": "research", "description": "做调研", "dependencies": []}]}}, rp)
        elif k == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig())
    out = proc.run("pro_x", goal="GEO 优化")
    assert out.status == "completed"
    assert out.tasks["task_001"].status == "completed"


def _plan_transport(team, agent_by_attempt):
    """构造一个 transport：team_config 返回 team；task_plan 按 attempt 指派 agent。"""
    calls = {"plan": 0}

    def transport(ctx):
        ctx.emit("step_start")
        k = ctx.request.kind
        rp = paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response"
        if k == "team_config":
            submit({"interaction_id": ctx.request.interaction_id, "kind": "team_config",
                    "status": "ok", "result": {"agents": list(team)}}, rp)
        elif k == "task_plan":
            calls["plan"] += 1
            agent = agent_by_attempt(calls["plan"])
            submit({"interaction_id": ctx.request.interaction_id, "kind": "task_plan",
                    "status": "ok", "result": {"tasks": [{
                        "id": "t1", "name": "调研", "agent": agent, "task_type": "research",
                        "description": "做调研", "dependencies": []}]}}, rp)
        elif k == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    return transport, calls


def test_task_plan_rejects_out_of_team_then_retry(env):
    store, wcfg = env
    # attempt 1 指派团队外 "ghost"，attempt 2 修正为 "researcher"
    transport, calls = _plan_transport(
        ["researcher"], lambda n: "ghost" if n == 1 else "researcher")
    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_plan_retries=2))
    out = proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2  # 越界后重试了一次
    assert out.status == "completed"
    assert store.get_task("pro_x", "t1")["agent"] == "researcher"


def test_task_plan_out_of_team_exhausted_raises(env):
    store, wcfg = env
    transport, calls = _plan_transport(["researcher"], lambda n: "ghost")  # 永远越界
    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_plan_retries=2))
    with pytest.raises(RuntimeError, match="团队外"):
        proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2  # 用尽重试上限


# ── recurring：周期循环 + 轮次继承（D10）──────────────────────


def _recurring_transport(seen, *, fail_all=False):
    """team_config 一次定 team；每周期 task_plan 返回单任务；记录注入的 prior_summary。"""
    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "team_config":
            submit({"interaction_id": req.interaction_id, "kind": "team_config",
                    "status": "ok", "result": {"agents": ["researcher"]}}, rp)
        elif req.kind == "task_plan":
            seen.append((req.input or {}).get("prior_summary", ""))
            submit({"interaction_id": req.interaction_id, "kind": "task_plan", "status": "ok",
                    "result": {"tasks": [{"id": "task_001", "name": "调研", "agent": "researcher",
                                          "task_type": "research", "description": "做调研",
                                          "dependencies": []}]}}, rp)
        elif req.kind == "execute":
            content = bad_content("research") if fail_all else valid_content("research")
            _write_exec(ctx, content, GOOD_Q)
        elif req.kind == "triage":
            submit({"interaction_id": req.interaction_id, "kind": "triage", "status": "ok",
                    "result": {"decision": "drop"}}, rp)
    return transport


def test_recurring_runs_cycles_with_inheritance(env):
    store, wcfg = env
    seen: list[str] = []
    proc = Process(store, _port(store, wcfg, _recurring_transport(seen)),
                   ProcessConfig(mode="recurring", max_cycles=2))
    out = proc.run("pro_r", goal="持续优化", agents=["researcher"])

    assert out.status == "completed"
    # 两个周期，task id 带周期前缀，互不覆盖
    assert set(out.tasks) == {"c1_task_001", "c2_task_001"}
    assert all(o.status == "completed" for o in out.tasks.values())
    # 轮次继承：周期1 无 prior，周期2 注入了非空滚动摘要
    assert seen[0] == "" and seen[1] and seen[1] != ""
    # 每周期滚动摘要落 KB
    mem = store.memory_search(project_id="pro_r", tags=["cycle_summary"])
    assert len(mem) == 2


def test_recurring_stops_on_zero_progress(env):
    store, wcfg = env
    seen: list[str] = []
    proc = Process(store, _port(store, wcfg, _recurring_transport(seen, fail_all=True)),
                   ProcessConfig(mode="recurring", max_cycles=3, max_gate_retries=1))
    out = proc.run("pro_r", goal="持续优化", agents=["researcher"])

    assert out.status == "failed"
    # 第一周期零完成即停，不会跑满 max_cycles
    assert set(out.tasks) == {"c1_task_001"}
    assert len(seen) == 1
