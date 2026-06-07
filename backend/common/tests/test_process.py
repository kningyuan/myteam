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
import common.process as process_mod  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.process import (Process, ProcessConfig, PlanCheckResult,
                             _auto_create_agent, check_plan, topological_order)  # noqa: E402
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
    with pytest.raises(RuntimeError, match="校验失败"):
        proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2  # 用尽重试上限


def _transport_plan_bad(team, make_bad):
    """构造 transport：team_config 正常；task_plan 按 attempt 返回 make_bad(n) 产生的 tasks。"""
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
            submit({"interaction_id": ctx.request.interaction_id, "kind": "task_plan",
                    "status": "ok", "result": {"tasks": make_bad(calls["plan"])}}, rp)
        elif k == "execute":
            ctx.emit("step_start")
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    return transport, calls


def test_task_plan_rejects_unregistered_type_then_retry(env):
    """task_plan 返回未注册 task_type → check_plan 打回 → 重试后修正。"""
    store, wcfg = env

    def make_bad(n):
        tt = "fake_type" if n == 1 else "research"
        return [{"id": "t1", "name": "x", "agent": "researcher",
                 "task_type": tt, "description": "x", "dependencies": []}]

    transport, calls = _transport_plan_bad({"researcher"}, make_bad)
    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_plan_retries=2))
    out = proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2  # 第一次被 check_plan 打回
    assert out.status == "completed"


def test_task_plan_rejects_dangling_dep_then_retry(env):
    """task_plan 返回 dangling 依赖 → check_plan 打回 → 重试后修正。"""
    store, wcfg = env

    def make_bad(n):
        deps = ["nonexistent"] if n == 1 else []
        return [{"id": "t1", "name": "x", "agent": "researcher",
                 "task_type": "research", "description": "x", "dependencies": deps}]

    transport, calls = _transport_plan_bad({"researcher"}, make_bad)
    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_plan_retries=2))
    out = proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2
    assert out.status == "completed"


def test_task_plan_rejects_cycle_then_retry(env):
    """task_plan 返回有环 DAG → check_plan 打回 → 重试后修正。"""
    store, wcfg = env

    def make_bad(n):
        if n == 1:
            # t1 → t2 → t1 成环
            return [{"id": "t1", "name": "x", "agent": "researcher", "task_type": "research",
                     "description": "x", "dependencies": ["t2"]},
                    {"id": "t2", "name": "y", "agent": "researcher", "task_type": "research",
                     "description": "y", "dependencies": ["t1"]}]
        return [{"id": "t1", "name": "x", "agent": "researcher", "task_type": "research",
                 "description": "x", "dependencies": []}]

    transport, calls = _transport_plan_bad({"researcher"}, make_bad)
    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(max_plan_retries=2))
    out = proc.run("pro_x", goal="GEO")
    assert calls["plan"] == 2
    assert out.status == "completed"


# ── 同行评审（开关 review_enabled）────────────────────────────


def _review_transport(reviews, *, approved=True):
    """execute 正常产出；review 由 reviewer 返回 passed=approved。records 记录被调用的评审。"""
    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "review":
            reviews.append((req.task_id, req.agent_id))
            submit({"interaction_id": req.interaction_id, "kind": "review", "status": "ok",
                    "quality": GOOD_Q,
                    "result": {"passed": approved, "feedback": "" if approved else "缺数据"}}, rp)
            return
        _write_exec(ctx, valid_content("research"), GOOD_Q)
    return transport


def _reviewed_task():
    return [{"id": "t1", "agent": "researcher", "task_type": "research",
             "reviewer": "product", "dependencies": []}]


def test_review_switch_off_no_review(env):
    store, wcfg = env
    reviews = []
    proc = Process(store, _port(store, wcfg, _review_transport(reviews)),
                   ProcessConfig(review_enabled=False))
    out = proc.run("pro_x", agents=["researcher", "product"], tasks=_reviewed_task())
    assert out.tasks["t1"].status == "completed"
    assert reviews == []  # 开关关：即便指派了 reviewer 也不评审


def test_review_approve_keeps_status(env):
    store, wcfg = env
    reviews = []
    proc = Process(store, _port(store, wcfg, _review_transport(reviews, approved=True)),
                   ProcessConfig(review_enabled=True))
    out = proc.run("pro_x", agents=["researcher", "product"], tasks=_reviewed_task())
    assert out.tasks["t1"].status == "completed"
    assert reviews == [("t1", "product")]  # 评审发给了 main 指派的 reviewer


def test_review_reject_to_needs_review(env):
    store, wcfg = env
    reviews = []
    proc = Process(store, _port(store, wcfg, _review_transport(reviews, approved=False)),
                   ProcessConfig(review_enabled=True))
    out = proc.run("pro_x", agents=["researcher", "product"], tasks=_reviewed_task())
    assert out.tasks["t1"].status == "needs_review"  # 评审打回 → 不静默通过


def test_review_approve_promotes_low_selfassess_to_completed(env):
    """自评有 known_gaps → 自评判定 needs_review；但 reviewer 批准 → 升级为 completed。"""
    store, wcfg = env
    reviews = []
    low_q = {"score": 0.9, "known_gaps": ["未覆盖 X"], "notes": "有缺口"}

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "review":
            reviews.append((req.task_id, req.agent_id))
            submit({"interaction_id": req.interaction_id, "kind": "review", "status": "ok",
                    "quality": GOOD_Q, "result": {"passed": True, "feedback": ""}}, rp)
            return
        _write_exec(ctx, valid_content("research"), low_q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(review_enabled=True))
    out = proc.run("pro_x", agents=["researcher", "product"], tasks=_reviewed_task())
    assert out.tasks["t1"].status == "completed"
    assert reviews == [("t1", "product")]


def test_review_enabled_but_no_reviewer_skips(env):
    store, wcfg = env
    reviews = []
    proc = Process(store, _port(store, wcfg, _review_transport(reviews)),
                   ProcessConfig(review_enabled=True))
    out = proc.run("pro_x", agents=["researcher"],
                   tasks=[{"id": "t1", "agent": "researcher", "task_type": "research",
                           "dependencies": []}])
    assert out.tasks["t1"].status == "completed"
    assert reviews == []  # 开关开但 main 未指派 reviewer → 跳过


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


# ── check_plan 确定性门禁（plan gate）单元测试 ──────────────────


def _task(tid, agent="researcher", task_type="research", deps=None):
    return {"id": tid, "agent": agent, "task_type": task_type,
            "dependencies": deps or []}


def test_check_plan_valid():
    team = {"researcher"}
    tasks = [_task("a"), _task("b", deps=["a"])]
    r = check_plan(tasks, team)
    assert r.passed


def test_check_plan_empty_plan():
    r = check_plan([], {"researcher"})
    assert r.passed


def test_check_plan_duplicate_ids():
    r = check_plan([_task("a"), _task("a")], {"researcher"})
    assert not r.passed
    assert "重复" in r.feedback


def test_check_plan_agent_not_in_team():
    r = check_plan([_task("a", agent="ghost")], {"researcher"})
    assert not r.passed
    assert "ghost" in r.feedback
    assert "researcher" in r.feedback


def test_check_plan_unregistered_task_type():
    r = check_plan([_task("a", task_type="fake_type")], {"researcher"})
    assert not r.passed
    assert "fake_type" in r.feedback
    assert "注册表" in r.feedback


def test_check_plan_agent_task_type_mismatch():
    r = check_plan([_task("a", agent="researcher", task_type="code-writing")], {"researcher"})
    assert not r.passed
    assert "code-writing" in r.feedback
    assert "researcher" in r.feedback


def test_check_plan_dangling_dependency():
    r = check_plan([_task("a", deps=["nonexistent"])], {"researcher"})
    assert not r.passed
    assert "nonexistent" in r.feedback


def test_check_plan_cycle():
    r = check_plan([_task("a", deps=["b"]), _task("b", deps=["a"])], {"researcher"})
    assert not r.passed
    assert "环" in r.feedback


def test_check_plan_fanout_exceeded():
    tasks = [_task(f"t{i}") for i in range(10)]
    r = check_plan(tasks, {"researcher"}, max_fanout=5)
    assert not r.passed
    assert "上限" in r.feedback


def test_check_plan_mixed_errors_first_wins():
    """check_plan 短路：先报 id 重复，不管 agent/task_type。"""
    tasks = [{"id": "x", "agent": "ghost", "task_type": "invalid"},
             {"id": "x", "agent": "researcher", "task_type": "research"}]
    r = check_plan(tasks, {"researcher"})
    assert not r.passed
    assert "重复" in r.feedback  # id 重复最先捕获


# ── 派发前静态递归展开（evaluate；开关 split_enabled）──────────


def _sub(sid, agent="researcher", task_type="research", deps=None):
    return {"id": sid, "name": sid, "agent": agent, "task_type": task_type,
            "description": sid, "dependencies": deps or []}


def _single_plan(req, rp, tid="t1"):
    submit({"interaction_id": req.interaction_id, "kind": "task_plan", "status": "ok",
            "result": {"tasks": [{"id": tid, "name": "大任务", "agent": "researcher",
                                  "task_type": "research", "description": "x",
                                  "dependencies": []}]}}, rp)


def test_normalize_and_splice_units():
    """归一（前缀/回填/兄弟依赖）与依赖重接的纯逻辑单测（不依赖 store/port）。"""
    from common.plan_splice import normalize_subtasks, splice_subtasks
    parent = {"id": "t1", "agent": "researcher", "task_type": "research", "dependencies": ["up"]}
    raw = [{"id": "a", "name": "A", "description": "x", "dependencies": []},
           {"id": "b", "name": "B", "description": "y", "dependencies": ["a"]}]
    subs = normalize_subtasks(raw, parent)
    assert [s["id"] for s in subs] == ["t1.a", "t1.b"]                 # 加父前缀
    assert all(s["agent"] == "researcher" and s["task_type"] == "research" for s in subs)  # 回填父值
    assert subs[1]["dependencies"] == ["t1.a"]                          # 兄弟依赖也加前缀

    result = {"t1": parent,
              "down": {"id": "down", "dependencies": ["t1"]},
              "up": {"id": "up", "dependencies": []}}
    splice_subtasks(result, parent, subs)
    assert "t1" not in result                                          # 父被替换
    assert result["t1.a"]["dependencies"] == ["up"]                    # 入口继承父上游
    assert result["t1.b"]["dependencies"] == ["t1.a"]                  # 非入口保持兄弟依赖
    assert result["down"]["dependencies"] == ["t1.a", "t1.b"]          # 外部重接到全部子任务


def test_split_disabled_no_evaluate(env):
    store, wcfg = env
    kinds = []

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        kinds.append(req.kind)
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(split_enabled=False))
    out = proc.run("pro_x", agents=["researcher"], goal="x")
    assert "evaluate" not in kinds              # 开关关：从不问 evaluate
    assert out.tasks["t1"].status == "completed"


def test_split_expands_one_task_into_two(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "evaluate":
            split = req.task_id == "t1"           # 只拆顶层；子任务（t1.a/t1.b）不再拆
            subs = [_sub("a"), _sub("b", deps=["a"])] if split else []
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": split, "reason": "复杂", "sub_tasks": subs}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport), ProcessConfig(split_enabled=True))
    out = proc.run("pro_x", agents=["researcher"], goal="big")
    assert "t1" not in out.tasks                  # 父任务被子任务替换
    assert out.tasks["t1.a"].status == "completed"
    assert out.tasks["t1.b"].status == "completed"
    assert out.status == "completed"


def test_split_rejects_out_of_team_subtask_then_retry(env):
    store, wcfg = env
    ev = {"n": 0}

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "evaluate":
            if req.task_id != "t1":               # 子任务不再拆
                submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                        "result": {"should_split": False, "reason": "", "sub_tasks": []}}, rp)
                return
            ev["n"] += 1
            agent = "ghost" if ev["n"] == 1 else "researcher"   # 先越界 → 打回；再修正
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": True, "reason": "复杂",
                               "sub_tasks": [_sub("a", agent=agent)]}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(split_enabled=True, max_plan_retries=2))
    out = proc.run("pro_x", agents=["researcher"], goal="x")
    assert ev["n"] == 2                           # 越界子任务被打回、重试一次后修正
    assert out.tasks["t1.a"].status == "completed"
    assert "t1" not in out.tasks


def test_split_depth_cap_terminates(env):
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "evaluate":              # 永远想拆 → 必须靠 depth cap 收敛
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": True, "reason": "总想拆",
                               "sub_tasks": [_sub("x")]}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(split_enabled=True, max_split_depth=2))
    out = proc.run("pro_x", agents=["researcher"], goal="x")
    # t1(d0)→t1.x(d1)→t1.x.x(d2 到顶不再拆)；只有最深叶子被执行
    assert out.status == "completed"
    assert set(out.tasks) == {"t1.x.x"}
    assert out.tasks["t1.x.x"].status == "completed"


def test_split_rejects_dangling_dependency(env):
    """Bug 1 回归：子任务依赖非同组 id（会被 topological_order 静默丢）→ 必须打回重试。"""
    store, wcfg = env
    ev = {"n": 0}

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "evaluate":
            if req.task_id != "t1":
                submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                        "result": {"should_split": False, "reason": "", "sub_tasks": []}}, rp)
                return
            ev["n"] += 1
            subs = ([_sub("a", deps=["ghost_dep"])] if ev["n"] == 1      # 悬空依赖 → 打回
                    else [_sub("a"), _sub("b", deps=["a"])])            # 修正为合法兄弟
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": True, "reason": "拆", "sub_tasks": subs}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(split_enabled=True, max_plan_retries=2))
    out = proc.run("pro_x", agents=["researcher"], goal="x")
    assert ev["n"] == 2                            # 悬空依赖被打回、重试一次后修正
    assert out.tasks["t1.a"].status == "completed"
    assert out.tasks["t1.b"].status == "completed"


def test_split_subtask_failure_blocks_dependent(env):
    """Gap 3 回归：子任务是普通任务——失败走 triage、依赖它的兄弟经重接后的边被阻塞。"""
    store, wcfg = env

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "task_plan":
            _single_plan(req, rp)
        elif req.kind == "evaluate":
            split = req.task_id == "t1"
            subs = [_sub("a"), _sub("b", deps=["a"])] if split else []
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": split, "reason": "拆", "sub_tasks": subs}}, rp)
        elif req.kind == "triage":
            submit({"interaction_id": req.interaction_id, "kind": "triage", "status": "ok",
                    "result": {"decision": "drop"}}, rp)
        elif req.kind == "execute":
            content = bad_content("research") if req.task_id == "t1.a" \
                else valid_content("research")           # t1.a 永远缺章节 → 门禁失败
            _write_exec(ctx, content, GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(split_enabled=True, max_gate_retries=1))
    out = proc.run("pro_x", agents=["researcher"], goal="x")
    assert out.tasks["t1.a"].status == "failed"        # 子任务门禁耗尽 → failed
    assert out.tasks["t1.b"].status == "blocked"       # 依赖失败子任务 → 阻塞（重接边生效）
    assert out.status == "failed"


def test_recurring_split_uses_distinct_ids_across_cycles(env):
    """Bug 2 回归：recurring + split 时 evaluate 交互 id 跨周期带 :c{cycle}，不撞。"""
    store, wcfg = env
    ev_ids: list[str] = []

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "team_config":
            submit({"interaction_id": req.interaction_id, "kind": "team_config", "status": "ok",
                    "result": {"agents": ["researcher"]}}, rp)
        elif req.kind == "task_plan":
            submit({"interaction_id": req.interaction_id, "kind": "task_plan", "status": "ok",
                    "result": {"tasks": [{"id": "t1", "name": "n", "agent": "researcher",
                                          "task_type": "research", "description": "x",
                                          "dependencies": []}]}}, rp)
        elif req.kind == "evaluate":
            ev_ids.append(req.interaction_id)
            split = req.task_id == "t1"
            subs = [_sub("a")] if split else []
            submit({"interaction_id": req.interaction_id, "kind": "evaluate", "status": "ok",
                    "result": {"should_split": split, "reason": "拆", "sub_tasks": subs}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(mode="recurring", max_cycles=2, split_enabled=True))
    out = proc.run("pro_r", goal="持续", agents=["researcher"])
    # 两周期各自展开，子任务带周期前缀互不覆盖
    assert set(out.tasks) == {"c1_t1.a", "c2_t1.a"}
    assert all(o.status == "completed" for o in out.tasks.values())
    # evaluate 交互 id 跨周期不撞
    assert "pro_r:t1:evaluate:c1" in ev_ids and "pro_r:t1:evaluate:c2" in ev_ids
    assert len(set(ev_ids)) == len(ev_ids)


# ── 动态 Agent 创建测试 ──────────────────────────────────────────


def test_auto_create_agent_direct(tmp_path, monkeypatch):
    """_auto_create_agent 直接测试：创建 workspace + 身份文件 + 配置 + 注册表。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "AGENTS_CONFIG_FILE", tmp_path / "agents_config.json")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", tmp_path / "agents_registry.json")

    ok = _auto_create_agent("test_dev", name="测试开发者", role="developer",
                            description="auto-created dev agent",
                            backend="opencode", model="claude-sonnet-4")
    assert ok

    ws_dir = tmp_path / "workspaces" / "workspace-test_dev"
    assert ws_dir.is_dir()
    assert (ws_dir / ".trigger").is_dir()
    assert (ws_dir / ".response").is_dir()
    for fname in ["IDENTITY.md", "AGENTS.md", "SOUL.md"]:
        assert (ws_dir / fname).is_file(), f"缺少 {fname}"
        content = (ws_dir / fname).read_text(encoding="utf-8")
        assert "测试开发者" in content or "test_dev" in content
    for fname in ["USER.md", "TOOLS.md", "HEARTBEAT.md"]:
        assert (ws_dir / fname).is_file(), f"缺少 {fname}"

    # 验证 agents_config.json
    import json
    cfg = json.loads((tmp_path / "agents_config.json").read_text(encoding="utf-8"))
    assert cfg["test_dev"]["backend"] == "opencode"
    assert cfg["test_dev"]["model"] == "claude-sonnet-4"

    # 验证 agents_registry.json
    reg = json.loads((tmp_path / "agents_registry.json").read_text(encoding="utf-8"))
    assert reg["agents"]["test_dev"]["name"] == "测试开发者"
    assert reg["agents"]["test_dev"]["role"] == "developer"


def test_auto_create_agent_already_exists(tmp_path, monkeypatch):
    """已存在的 agent 不应重复创建。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    ws_dir = tmp_path / "workspaces" / "workspace-existing"
    ws_dir.mkdir(parents=True)
    marker = ws_dir / "MARKER"
    marker.write_text("original")

    _auto_create_agent("existing")
    # 不应覆盖已有文件
    assert marker.read_text() == "original"


def test_auto_create_agent_works_in_full_team_config(tmp_path, monkeypatch):
    """完整流程：team_config → Main 返回新 agent → auto-create → DAG 执行。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    monkeypatch.setattr(paths, "AGENTS_CONFIG_FILE", tmp_path / "agents_config.json")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", tmp_path / "agents_registry.json")
    monkeypatch.setattr(paths, "WORKSPACE_PREFIX", "workspace-")

    # 预创建 main agent workspace（auto-create 不会为 main 做，但 team_config 交互需要）
    main_ws = tmp_path / "workspaces" / "workspace-main"
    main_ws.mkdir(parents=True)

    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        rp = paths.response_dir(req.agent_id) / f"{req.interaction_id}.response"
        if req.kind == "team_config":
            # Main 返回既有 + 新 agent
            submit({"interaction_id": req.interaction_id, "kind": "team_config",
                    "status": "ok", "result": {"agents": ["main", "auto_created_dev"]}}, rp)
        elif req.kind == "task_plan":
            # 新 agent 承担一个任务
            submit({"interaction_id": req.interaction_id, "kind": "task_plan",
                    "status": "ok",
                    "result": {"tasks": [{"id": "t1", "name": "开发任务",
                                          "agent": "auto_created_dev",
                                          "task_type": "research",
                                          "description": "测试任务",
                                          "dependencies": []}]}}, rp)
        elif req.kind == "execute":
            _write_exec(ctx, valid_content("research"), GOOD_Q)

    proc = Process(store, _port(store, wcfg, transport),
                   ProcessConfig(auto_create_agents=True))
    out = proc.run("pro_auto", goal="test")

    # auto_created_dev 应被自动创建
    dev_ws = tmp_path / "workspaces" / "workspace-auto_created_dev"
    assert dev_ws.is_dir()
    assert (dev_ws / "IDENTITY.md").is_file()

    # DAG 应正常完成
    assert out.tasks["t1"].status == "completed"
    assert out.status == "completed"

    store.close()
