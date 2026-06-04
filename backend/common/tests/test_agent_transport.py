#!/usr/bin/env python3
"""Phase 8 step 1：AgentPort 真实 Transport 测试（注入 fake 适配器，不跑真实 opencode）。

验证：提示词含关键约束；适配器事件被转发为心跳；step_finish token 计量；取消信号联动；
端到端 done。真实 opencode 跑通需运行态验证（本测试只覆盖接线正确性）。
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.agent_transport import AdapterTransport, build_worker_prompt  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


class FakeEvent:
    def __init__(self, kind, data=None):
        self.kind = types.SimpleNamespace(value=kind)
        self.data = data or {}


class FakeAdapter:
    """记录收到的 RunRequest，按脚本 yield 事件，并模拟 agent 写 .response。"""

    def __init__(self, events, on_run=None):
        self.events = events
        self.on_run = on_run
        self.last_request = None

    def run(self, request):
        self.last_request = request
        for ev in self.events:
            if ev == "_submit" and self.on_run:
                self.on_run(request)
                continue
            yield ev


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def _req(iid="i1"):
    return {
        "interaction_id": iid, "kind": "execute", "project_id": "pro_x",
        "task_id": "task_001", "agent_id": "researcher", "intent": "做调研",
        "input": {"deliverable_path": "task_001_deliverable.md"},
        "constraints": {"task_type": "research"},
        "response_schema": "execute.result@1.0",
    }


def test_prompt_contains_key_constraints():
    from common.contracts import parse_request
    req = parse_request(_req())
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "submit_result.py" in prompt
    assert "i1" in prompt
    assert "调研背景" in prompt  # research 必需章节来自注册表
    assert "task_001_deliverable.md" in prompt
    assert "聊天" in prompt  # 明确禁止聊天返回


def test_task_plan_prompt_has_concrete_schema():
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "p:task_plan", "kind": "task_plan", "project_id": "p",
        "agent_id": "main", "intent": "规划",
        "input": {"goal": "g", "team": ["researcher", "seo"]},
    })
    prompt = build_worker_prompt(req, Path("/tmp/x.response"), Path("/tmp/deliv"))
    # 决策类必须给出具体 result 骨架，而非仅 schema 名（弱模型靠名字猜不出结构）
    assert '"tasks"' in prompt
    assert "task_type" in prompt
    assert "dependencies" in prompt
    assert "researcher" in prompt and "seo" in prompt  # 可用 agent 约束
    assert "research" in prompt  # 来自注册表的可用 task_type


def test_retry_feedback_shown_for_decision_kinds():
    """决策类（task_plan 等）也要把上一轮校验失败的 feedback 注入提示词。"""
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "p:task_plan:2", "kind": "task_plan", "project_id": "p",
        "agent_id": "main", "intent": "规划",
        "input": {"goal": "g", "team": ["researcher"]},
        "retry_feedback": ["以下 agent 不在团队名册中：ghost；只能从 [researcher] 中选。"],
    })
    prompt = build_worker_prompt(req, Path("/tmp/x.response"), Path("/tmp/deliv"))
    assert "逐条修正" in prompt
    assert "ghost" in prompt


def test_transport_forwards_events_and_meters_tokens(env):
    store, wcfg = env

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("researcher") / "i1.response")

    events = [FakeEvent("step_start"), FakeEvent("text", {"chunk": "hi"}),
              "_submit", FakeEvent("step_finish", {"tokens": 256})]
    adapter = FakeAdapter(events, on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"researcher": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))

    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    # 适配器拿到正确的 workspace/model/agent
    assert adapter.last_request.model == "m1"
    assert adapter.last_request.agent_id == "researcher"
    # 事件被转发入库
    kinds = [e["kind"] for e in store.list_run_events("i1")]
    assert "step_start" in kinds and "text" in kinds
    # step_finish token 计量（D17）
    assert store.get_interaction("i1")["tokens"] == 256


def test_meters_cumulative_opencode_tokens(env):
    """真实 opencode 形态：tokens 是 dict 且 total 为会话累计（单调递增）→ 取最大。"""
    store, wcfg = env

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("researcher") / "i1.response")

    events = [
        FakeEvent("step_finish", {"tokens": {"input": 10631, "output": 395, "total": 11026}}),
        FakeEvent("step_finish", {"tokens": {"input": 2854, "output": 313, "total": 11359}}),
        "_submit",
        FakeEvent("step_finish", {"tokens": {"input": 3187, "output": 174, "total": 11553}}),
    ]
    adapter = FakeAdapter(events, on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"researcher": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    # 取累计最大值，而非三次相加
    assert store.get_interaction("i1")["tokens"] == 11553


def test_transport_cancel_event_wired(env):
    store, wcfg = env
    seen = {}

    def write_resp(run_request):
        seen["cancel_event"] = run_request.cancel_event
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n内容足够。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("researcher") / "i1.response")

    adapter = FakeAdapter([FakeEvent("step_start"), "_submit"], on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"researcher": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    port.run(_req())
    # cancel_event 是 AgentPort 的取消 Event，done 后被 set
    assert seen["cancel_event"] is not None
