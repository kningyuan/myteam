#!/usr/bin/env python3
"""Phase 7 可观测 + Token 治理测试（D17）。

验证标准：只读视图反映真相库；超预算触发暂停与告警。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.observability.observability import (  # noqa: E402
    BudgetConfig,
    check_budget,
    cost,
    fleet_status,
    liveness,
    project_events,
    project_overview,
    projects_summary,
    task_detail,
    timeline,
)
from common.process.process import Process, ProcessConfig  # noqa: E402
from common.gate.registry import get_spec  # noqa: E402
from common.store.store import Store  # noqa: E402
from common.delivery.submit_result import submit  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "s.db")
    yield s
    s.close()


def test_overview_budget_and_summary(store):
    """预算持久在 meta；overview/summary 暴露 tokens/budget/state。"""
    store.upsert_project("pro_b", title="预算项目", status="in_progress",
                         meta={"token_budget": 1000})
    store.upsert_task("pro_b", "t1", agent="research")
    store.create_interaction("pro_b:t1:execute:1", "execute", "pro_b",
                             task_id="t1", agent_id="research")
    store.update_interaction("pro_b:t1:execute:1", status="done", tokens=850)

    ov = project_overview(store, "pro_b")
    assert ov["tokens"] == 850 and ov["budget"] == 1000
    assert ov["budget_state"] == "alert"   # 85% ≥ 80%

    summ = projects_summary(store)
    assert summ["totals"]["projects"] >= 1
    assert summ["totals"]["tokens"] >= 850
    row = next(p for p in summ["projects"] if p["id"] == "pro_b")
    assert row["budget"] == 1000 and row["budget_state"] == "alert"
    assert summ["totals"]["running"] >= 1   # in_progress 计入运行中


def test_project_events_feed(store):
    """项目事件流：交互骨架 + 里程碑事件（含合成 id），过滤低层噪声，按时间排序。"""
    store.upsert_project("pro_e")
    store.create_interaction("pro_e_task_001_execute", "execute", "pro_e",
                             task_id="task_001", agent_id="research")
    store.append_run_event("pro_e_task_001_execute", "text", {"t": "正文片段"})  # 噪声，过滤
    store.append_run_event("pro_e_task_001_execute", "gate_passed", {})
    store.append_run_event("pro_e_task_001_execute", "tool_use", {"tool": "web-search"})
    # 合成 id 事件（不挂在真实 interaction 上）
    store.append_run_event("pro_e:budget", "budget_alert", {"used": 90})
    store.append_run_event("pro_e:notify", "message", {"sender": "system", "text": "进度通报"})

    feed = project_events(store, "pro_e")
    kinds = [e["kind"] for e in feed]
    assert "text" not in kinds                      # 低层噪声被过滤
    assert "gate_passed" in kinds                   # 真实交互里程碑
    assert "tool_use" in kinds                      # skill 调用
    assert "budget_alert" in kinds                  # 合成 id 事件被捞到
    assert "message" in kinds                       # 群通知进流
    assert any(e["category"] == "interaction" for e in feed)  # 交互骨架在


def test_parallel_wave_in_feed(store):
    """parallel_wave 项目级事件应出现在 project_events 流中。"""
    store.upsert_project("pro_pw")
    store.append_run_event("pro_pw:dispatch", "parallel_wave", {"tasks": ["t1", "t2"], "count": 2})
    feed = project_events(store, "pro_pw")
    assert any(e["kind"] == "parallel_wave" for e in feed)


def test_liveness_states():
    assert liveness({"status": "done"}) == "done"
    assert liveness({"status": "running", "last_event_at": "2026-06-01T12:00:00"}) == "stuck"
    import time
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    assert liveness({"status": "running", "last_event_at": now}) == "running"


def test_overview_and_cost(store):
    store.upsert_project("pro_x", title="GEO")
    store.upsert_task("pro_x", "t1", agent="research")
    store.upsert_task("pro_x", "t2", agent="seo", dependencies=["t1"])
    store.set_task_status("pro_x", "t1", "completed")
    store.create_interaction("i1", "execute", "pro_x", task_id="t1", agent_id="research")
    store.update_interaction("i1", tokens=100)
    store.create_interaction("i2", "execute", "pro_x", task_id="t2", agent_id="seo")
    store.update_interaction("i2", tokens=50)

    ov = project_overview(store, "pro_x")
    assert ov["task_counts"]["completed"] == 1
    assert ov["progress"] == 0.5

    c = cost(store, "pro_x")
    assert c["project"] == 150
    assert c["by_agent"] == {"research": 100, "seo": 50}
    assert c["by_task"] == {"t1": 100, "t2": 50}


def test_task_detail_and_timeline(store):
    store.upsert_project("pro_x")
    store.upsert_task("pro_x", "t1", agent="research")
    store.create_interaction("i1", "execute", "pro_x", task_id="t1", agent_id="research")
    store.append_run_event("i1", "step_start")
    store.append_run_event("i1", "text", {"chunk": "x"})
    store.update_interaction("i1", status="done", tokens=42)

    td = task_detail(store, "pro_x", "t1")
    assert td["interactions"][0]["tokens"] == 42
    assert td["interactions"][0]["status"] == "done"
    tl = timeline(store, "i1")
    assert [e["kind"] for e in tl] == ["step_start", "text"]


def test_fleet_status(store):
    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x", agent_id="research")
    store.update_interaction("i1", status="done")
    fs = fleet_status(store, "pro_x")
    assert fs["research"] == "done"


def test_check_budget(store):
    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x")
    store.update_interaction("i1", tokens=850)
    assert check_budget(store, "pro_x", BudgetConfig(project_limit=None)).state == "ok"
    assert check_budget(store, "pro_x", BudgetConfig(project_limit=1000)).state == "alert"
    store.update_interaction("i1", tokens=200)  # 累计 1050
    assert check_budget(store, "pro_x", BudgetConfig(project_limit=1000)).state == "over"


# ── 端到端：超预算暂停项目（方案丙）───────────────────────────


@pytest.fixture()
def penv(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    s = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    # 禁用 skill_review 后台复盘（本测试只验证预算/降级语义，不涉及复盘）
    import execution_harness.facade as _facade
    monkeypatch.setattr(_facade, "schedule_skill_review", lambda *a, **k: None)
    yield s, wcfg
    s.close()


def _valid(task_type):
    spec = get_spec(task_type)
    out = ["# 标题\n"]
    for sname in spec.required_sections:
        out.append(f"## {sname}\n「{sname}」足够具体的内容，覆盖要点与细节说明充分。\n")
    return "\n".join(out)


def test_execute_budget_exceeded_pauses_mid_interaction(penv):
    """交互进行中达 token 硬上限 → 项目 paused（非 task failed）。"""
    store, wcfg = penv
    store.upsert_project("pro_mid", status="in_progress", meta={"token_budget": 1000})

    def transport(ctx):
        ctx.emit("step_start")
        iid = ctx.request.interaction_id
        while not ctx.cancelled:
            store.update_interaction(iid, tokens=1100)
            time.sleep(0.03)

    checker = lambda pid: store.tokens_total(pid) >= 1000  # noqa: E731
    port = AgentPort(transport, store=store, config=wcfg, budget_checker=checker)
    proc = Process(store, port, ProcessConfig(token_budget=1000))
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
    ]
    out = proc.run("pro_mid", agents=["research"], tasks=tasks)
    assert out.status == "paused"
    kinds = [e["kind"] for e in store.list_run_events("pro_mid:t1:execute:1")]
    assert "budget_exceeded" in kinds
    pause = [e for e in store.list_project_events("pro_mid") if e["kind"] == "budget_exceeded_pause"]
    assert pause


def test_over_budget_pauses_project(penv):
    store, wcfg = penv

    def transport(ctx):
        ctx.emit("step_start")
        rel = f"{ctx.request.task_id}_deliverable.md"
        (paths.deliverables_dir(ctx.request.project_id) / rel).write_text(_valid("research"), "utf-8")
        submit({
            "interaction_id": ctx.request.interaction_id, "kind": "execute", "status": "ok",
            "meta": {"tokens": 800},  # 每个任务烧 800 token
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response")

    proc = Process(store, AgentPort(transport, store=store, config=wcfg),
                   ProcessConfig(token_budget=1000, plan_enabled=False))
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "research", "task_type": "research", "dependencies": ["t1"]},
        {"id": "t3", "agent": "research", "task_type": "research", "dependencies": ["t2"]},
    ]
    out = proc.run("pro_x", agents=["research"], tasks=tasks)
    # t1 跑完烧 800 → 下一轮检查超 1000 之前还没超；t2 跑完累计 1600 → t3 前超限暂停
    assert out.tasks["t1"].status == "completed"
    assert out.tasks["t2"].status == "completed"
    assert out.tasks["t3"].status == "blocked"
    assert out.status == "paused"


def test_budget_degrade_fires_before_pause(penv, tmp_path, monkeypatch):
    """L3：达降级阈值时先降级，下一任务仍可跑；硬上限后才暂停。"""
    store, wcfg = penv
    monkeypatch.setattr(paths, "AGENTS_CONFIG_FILE", tmp_path / "agents_config.json")

    def transport(ctx):
        ctx.emit("step_start")
        rel = f"{ctx.request.task_id}_deliverable.md"
        (paths.deliverables_dir(ctx.request.project_id) / rel).write_text(
            _valid("research"), "utf-8")
        submit({
            "interaction_id": ctx.request.interaction_id, "kind": "execute", "status": "ok",
            "meta": {"tokens": 800},
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir(ctx.request.agent_id) / f"{ctx.request.interaction_id}.response")

    proc = Process(
        store, AgentPort(transport, store=store, config=wcfg),
        ProcessConfig(
            token_budget=1000,
            budget_degrade_threshold=0.8,
            budget_degrade_backend="opencode",
            budget_degrade_model="cheap-model",
            plan_enabled=False,
        ),
    )
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "research", "task_type": "research", "dependencies": ["t1"]},
        {"id": "t3", "agent": "research", "task_type": "research", "dependencies": ["t2"]},
    ]
    out = proc.run("pro_x", agents=["research"], tasks=tasks)

    assert out.tasks["t1"].status == "completed"
    assert out.tasks["t2"].status == "completed"
    assert out.tasks["t3"].status == "blocked"
    assert out.status == "paused"

    proj = store.get_project("pro_x")
    assert (proj.get("meta") or {}).get("degraded") is True
    assert (proj.get("meta") or {}).get("degrade_model") == "cheap-model"

    ev_kinds = [e["kind"] for e in store.list_run_events("pro_x:budget")]
    assert "budget_degrade" in ev_kinds
    assert ev_kinds.index("budget_degrade") < ev_kinds.index("budget_over")

    cfg = json.loads((tmp_path / "agents_config.json").read_text(encoding="utf-8"))
    assert cfg["research"]["model"] == "cheap-model"
