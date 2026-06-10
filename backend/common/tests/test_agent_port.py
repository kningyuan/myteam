#!/usr/bin/env python3
"""Phase 3 AgentPort 测试（D12 / D7 / D8）。

验证标准：注入卡死/超时/重复投递，状态机均正确恢复；无残留误用。
用临时 workspace + 注入式 Transport，不依赖真实 opencode。
"""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import (  # noqa: E402
    AgentPort, WatchdogConfig, _extract_tokens, reconcile_on_start,
)
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离的 MYTEAM_ROOT：workspaces 与 store 都落 tmp。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    store = Store(tmp_path / "state.db")
    store.upsert_project("pro_x")
    store.upsert_task("pro_x", "task_001")
    cfg = WatchdogConfig(soft_idle_sec=0.2, hard_idle_sec=0.6, poll_interval=0.05,
                         max_attempts=3)
    yield store, cfg
    store.close()


def _req(iid="i1", kind="execute"):
    return {
        "interaction_id": iid, "kind": kind, "project_id": "pro_x",
        "task_id": "task_001", "agent_id": "research", "intent": "do",
    }


def _valid_execute(iid="i1"):
    return {
        "interaction_id": iid, "kind": "execute", "status": "ok",
        "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
        "meta": {"tokens": 321},
        "result": {"outcome": {"kind": "artifact",
                               "artifact": {"path": "deliverables/x.md", "title": "X"}}},
    }


def test_happy_path(env):
    store, cfg = env

    def transport(ctx):
        ctx.emit("step_start")
        ctx.emit("text", {"chunk": "working"})
        # Agent 用 submit_result 校验后原子写 .response
        resp_path = paths.response_dir("research") / f"{ctx.request.interaction_id}.response"
        submit(_valid_execute(ctx.request.interaction_id), resp_path)

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "done"
    assert res.response["result"]["outcome"]["kind"] == "artifact"
    inter = store.get_interaction("i1")
    assert inter["status"] == "done"
    assert inter["tokens"] == 321
    # 见到合法响应即返回（D12）；返回前已入队的事件被记录
    kinds = [e["kind"] for e in store.list_run_events("i1")]
    assert "step_start" in kinds


def test_hard_idle_watchdog(env):
    store, cfg = env

    def transport(ctx):
        ctx.emit("step_start")
        # 之后卡死：不再产事件、不写响应，但要响应取消信号才退出
        while not ctx.cancelled:
            time.sleep(0.02)

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "timed_out"
    assert store.get_interaction("i1")["status"] == "timed_out"
    kinds = [e["kind"] for e in store.list_run_events("i1")]
    assert "watchdog_soft_idle" in kinds and "watchdog_hard_kill" in kinds


def test_no_response_when_transport_ends(env):
    store, cfg = env

    def transport(ctx):
        ctx.emit("step_start")  # 有事件但从不写响应，且很快返回

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "no_response"
    assert store.get_interaction("i1")["status"] == "failed"


def test_cli_error_not_no_response(env):
    store, cfg = env

    def transport(ctx):
        ctx.emit("error", {"message": "Open WebUI: Server Connection Error"})

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "error"
    assert "Server Connection Error" in (res.reason or "")
    assert store.get_interaction("i1")["status"] == "failed"


def test_retry_then_succeed_on_idle(env):
    store, cfg = env
    attempts = {"n": 0}

    def transport(ctx):
        attempts["n"] += 1
        if attempts["n"] == 1:
            ctx.emit("step_start")
            while not ctx.cancelled:  # 第一次卡死 → hard_idle 取消 → 重试
                time.sleep(0.02)
        else:
            ctx.emit("step_start")
            resp_path = paths.response_dir("research") / f"{ctx.request.interaction_id}.response"
            submit(_valid_execute(ctx.request.interaction_id), resp_path)

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "done"
    assert attempts["n"] == 2
    assert store.get_interaction("i1")["attempt"] == 2


def test_residue_response_rejected(env):
    """旧残留响应（interaction_id 不匹配）不得被误采纳。"""
    store, cfg = env
    resp_path = paths.response_dir("research") / "i1.response"
    resp_path.parent.mkdir(parents=True, exist_ok=True)
    # 预置一份「别的 interaction」的旧响应
    resp_path.write_text(json.dumps(_valid_execute("OTHER")), encoding="utf-8")

    def transport(ctx):
        ctx.emit("step_start")  # 不写新响应，很快返回

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req("i1"))
    # 派发前清旧文件 + interaction_id 不匹配 → 不采纳 → no_response
    assert res.status == "no_response"


def test_reconcile_on_start(env):
    store, cfg = env
    store.create_interaction("i_stuck", "execute", "pro_x")
    store.update_interaction("i_stuck", status="running", touch_event=True)
    n = reconcile_on_start(store)
    assert n["timed_out"] == 1
    assert store.get_interaction("i_stuck")["status"] == "timed_out"


def test_reconcile_adopts_orphan_response(env, monkeypatch):
    store, cfg = env
    monkeypatch.setattr(paths, "WORKSPACES_DIR", paths.WORKSPACES_DIR)
    agent = "research"
    iid = "i_orphan"
    store.create_interaction(iid, "execute", "pro_x", task_id="task_001", agent_id=agent)
    store.update_interaction(iid, status="running", touch_event=True)
    trig = paths.trigger_dir(agent)
    resp = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_valid_execute(iid), resp / f"{iid}.response")

    n = reconcile_on_start(store)
    assert n["adopted"] == 1
    assert store.get_interaction(iid)["status"] == "done"


def test_extract_tokens_input_output_fallback():
    """Claude result 行常见形态：tokens dict 无 total，回退 input+output。"""
    assert _extract_tokens({"tokens": {"input": 500, "output": 80}}) == 580
    assert _extract_tokens({"tokens": {"input_tokens": 100, "output_tokens": 20}}) == 120


def test_grace_window_drains_late_step_finish(env):
    """响应先落盘时 grace 窗口应排空迟到的 step_finish token。"""
    store, cfg = env

    def transport(ctx):
        resp_path = paths.response_dir("research") / f"{ctx.request.interaction_id}.response"
        submit(_valid_execute(ctx.request.interaction_id), resp_path)
        time.sleep(0.15)
        ctx.emit("step_finish", {"tokens": {"input": 100, "output": 50}})

    port = AgentPort(transport, store=store, config=cfg)
    res = port.run(_req())
    assert res.status == "done"
    assert store.get_interaction("i1")["tokens"] == 150


def test_reconcile_adopts_timed_out_orphan(env):
    """timed_out + 合法 .response → reconcile 采纳为 done。"""
    store, _cfg = env
    agent = "research"
    iid = "i_timed"
    store.create_interaction(iid, "execute", "pro_x", task_id="task_001", agent_id=agent)
    store.update_interaction(iid, status="timed_out")
    trig = paths.trigger_dir(agent)
    resp = paths.response_dir(agent)
    trig.mkdir(parents=True, exist_ok=True)
    resp.mkdir(parents=True, exist_ok=True)
    (trig / f"{iid}.request").write_text("{}", encoding="utf-8")
    submit(_valid_execute(iid), resp / f"{iid}.response")

    n = reconcile_on_start(store)
    assert n["adopted"] == 1
    assert n["timed_out"] == 0
    assert store.get_interaction(iid)["status"] == "done"


def test_agent_port_budget_hard_stop(env):
    """L3：交互进行中 budget_checker 返回 True 时硬停，不重试。"""
    store, cfg = env

    def transport(ctx):
        ctx.emit("step_start")
        while not ctx.cancelled:
            ctx.emit("heartbeat")
            time.sleep(0.05)

    checker = lambda pid: True  # noqa: E731 — 模拟已超预算
    port = AgentPort(transport, store=store, config=cfg, budget_checker=checker)
    res = port.run(_req())
    assert res.status == "budget_exceeded"
    assert store.get_interaction("i1")["status"] == "failed"
    kinds = [e["kind"] for e in store.list_run_events("i1")]
    assert "budget_exceeded" in kinds


def test_reconcile_keeps_timed_out_without_valid_response(env):
    """timed_out 且无合法响应 → 保持 timed_out，不误升。"""
    store, _cfg = env
    iid = "i_bad"
    store.create_interaction(iid, "execute", "pro_x", agent_id="research")
    store.update_interaction(iid, status="timed_out")

    n = reconcile_on_start(store)
    assert n["adopted"] == 0
    assert n["timed_out"] == 1
    assert store.get_interaction(iid)["status"] == "timed_out"
