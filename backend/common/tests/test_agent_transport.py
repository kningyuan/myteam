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
from common.agent_transport import (  # noqa: E402
    AdapterTransport,
    build_worker_prompt,
    lookup_interaction_session,
    make_gate_session_resolver,
    resolve_gate_retry_session,
)
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
        "task_id": "task_001", "agent_id": "research", "intent": "做调研",
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
    assert "## 调研背景" in prompt  # 与 Gate section_level 对齐的字面标题示例
    assert "不能只写在正文里提及" in prompt
    assert "task_001_deliverable.md" in prompt
    assert "聊天" in prompt  # 明确禁止聊天返回


def test_test_plan_prompt_has_literal_heading_examples():
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "i1", "kind": "execute", "project_id": "pro_x",
        "task_id": "task_001", "agent_id": "tester", "intent": "写测试计划",
        "input": {"deliverable_path": "task_001_deliverable.md"},
        "constraints": {"task_type": "test-plan"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "## 测试范围" in prompt
    assert "## 测试用例" in prompt
    assert "说明：" in prompt  # sections.description 已注入


def test_task_plan_prompt_has_concrete_schema():
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "p:task_plan", "kind": "task_plan", "project_id": "p",
        "agent_id": "main", "intent": "规划",
        "input": {"goal": "g", "team": ["research", "seo"]},
    })
    prompt = build_worker_prompt(req, Path("/tmp/x.response"), Path("/tmp/deliv"))
    # 决策类必须给出具体 result 骨架，而非仅 schema 名（弱模型靠名字猜不出结构）
    assert '"tasks"' in prompt
    assert "task_type" in prompt
    assert "dependencies" in prompt
    assert "research" in prompt and "seo" in prompt  # 可用 agent 约束
    assert "research" in prompt  # 来自注册表的可用 task_type


def test_retry_feedback_shown_for_decision_kinds():
    """决策类（task_plan 等）也要把上一轮校验失败的 feedback 注入提示词。"""
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "p:task_plan:2", "kind": "task_plan", "project_id": "p",
        "agent_id": "main", "intent": "规划",
        "input": {"goal": "g", "team": ["research"]},
        "retry_feedback": ["以下 agent 不在团队名册中：ghost；只能从 [research] 中选。"],
    })
    prompt = build_worker_prompt(req, Path("/tmp/x.response"), Path("/tmp/deliv"))
    assert "PATCH 修正" in prompt
    assert "ghost" in prompt


def test_transport_injects_rules_file(env, tmp_path, monkeypatch):
    store, wcfg = env
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "universal-rules.md").write_text("UNIVERSAL_RULE_XYZ", encoding="utf-8")
    ws = tmp_path / "workspaces" / "workspace-research"
    ws.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("AGENTS_MD_XYZ", encoding="utf-8")
    import common.agent_transport as _at_mod
    monkeypatch.setattr(_at_mod, "RULES_DIR", rules_dir)

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("research") / "i1.response")

    adapter = FakeAdapter(["_submit"], on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"research": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    assert adapter.last_request.rules_file
    merged = Path(adapter.last_request.rules_file).read_text(encoding="utf-8")
    assert "UNIVERSAL_RULE_XYZ" in merged
    assert "AGENTS_MD_XYZ" in merged


def test_transport_forwards_events_and_meters_tokens(env):
    store, wcfg = env

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("research") / "i1.response")

    events = [FakeEvent("step_start"), FakeEvent("text", {"chunk": "hi"}),
              "_submit", FakeEvent("step_finish", {"tokens": 256})]
    adapter = FakeAdapter(events, on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"research": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))

    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    # 适配器拿到正确的 workspace/model/agent
    assert adapter.last_request.model == "m1"
    assert adapter.last_request.agent_id == "research"
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
        }, paths.response_dir("research") / "i1.response")

    events = [
        FakeEvent("step_finish", {"tokens": {"input": 10631, "output": 395, "total": 11026}}),
        FakeEvent("step_finish", {"tokens": {"input": 2854, "output": 313, "total": 11359}}),
        "_submit",
        FakeEvent("step_finish", {"tokens": {"input": 3187, "output": 174, "total": 11553}}),
    ]
    adapter = FakeAdapter(events, on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"research": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    # 取累计最大值，而非三次相加
    assert store.get_interaction("i1")["tokens"] == 11553


def test_meters_claude_result_tokens_without_total(env):
    """Claude result step_finish 仅 input/output 无 total → Store 持久化非零 tokens。"""
    store, wcfg = env

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("research") / "i1.response")

    events = [
        "_submit",
        FakeEvent("step_finish", {
            "cumulative": True,
            "tokens": {"input": 500, "output": 80},
        }),
    ]
    adapter = FakeAdapter(events, on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"research": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    assert store.get_interaction("i1")["tokens"] == 580


def test_transport_uses_per_agent_backend(env, monkeypatch):
    """各 agent 按 agents_config.backend 选择 CLI，而非全局写死 opencode。"""
    store, wcfg = env
    used_backends = []

    def write_resp(run_request):
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": "i1", "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("research") / "i1.response")

    class TaggedAdapter(FakeAdapter):
        def __init__(self, tag):
            super().__init__([FakeEvent("step_start"), "_submit"], on_run=write_resp)
            self.tag = tag

        def run(self, request):
            used_backends.append(self.tag)
            return super().run(request)

    def fake_default(backend):
        return TaggedAdapter(backend)

    monkeypatch.setattr("common.agent_transport._default_adapter", fake_default)

    transport = AdapterTransport(
        agents_config={"research": {"backend": "claude", "model": "claude-sonnet-4-6"}},
        backend="opencode",
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    res = port.run(_req())
    assert res.status == "done"
    assert used_backends == ["claude"]


def test_transport_two_agents_different_backends(env, monkeypatch):
    """R-K14：同一 Transport 内两 agent 可并存不同 CLI backend。"""
    store, wcfg = env
    used: dict[str, list[str]] = {}
    current = {"iid": "i-r", "agent": "research"}

    def write_resp(run_request):
        aid = getattr(run_request, "agent_id", current["agent"])
        iid = current["iid"]
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text("# x\n## 调研背景\n足够内容。\n", "utf-8")
        submit({
            "interaction_id": iid, "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir(aid) / f"{iid}.response")

    class TaggedAdapter(FakeAdapter):
        def __init__(self, tag):
            super().__init__([FakeEvent("step_start"), "_submit"], on_run=write_resp)
            self.tag = tag

        def run(self, request):
            aid = getattr(request, "agent_id", "research")
            used.setdefault(aid, []).append(self.tag)
            return super().run(request)

    monkeypatch.setattr("common.agent_transport._default_adapter", lambda b: TaggedAdapter(b))

    transport = AdapterTransport(
        agents_config={
            "research": {"backend": "claude", "model": "claude-sonnet-4-6"},
            "writer": {"backend": "opencode", "model": "gpt-4"},
        },
        backend="opencode",
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)

    req_r = {**_req("i-r"), "agent_id": "research", "task_id": "task_r"}
    req_w = {**_req("i-w"), "agent_id": "writer", "task_id": "task_w"}
    current.update(iid="i-r", agent="research")
    assert port.run(req_r).status == "done"
    current.update(iid="i-w", agent="writer")
    assert port.run(req_w).status == "done"
    assert used["research"] == ["claude"]
    assert used["writer"] == ["opencode"]


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
        }, paths.response_dir("research") / "i1.response")

    adapter = FakeAdapter([FakeEvent("step_start"), "_submit"], on_run=write_resp)
    transport = AdapterTransport(adapter=adapter, agents_config={"research": {"model": "m1"}},
                                 request_factory=lambda **kw: types.SimpleNamespace(**kw))
    port = AgentPort(transport, store=store, config=wcfg)
    port.run(_req())
    # cancel_event 是 AgentPort 的取消 Event，done 后被 set
    assert seen["cancel_event"] is not None


def test_config_reloads_from_disk_when_not_injected(monkeypatch):
    calls = {"n": 0}

    def load():
        calls["n"] += 1
        return {"research": {"model": f"m{calls['n']}"}}

    monkeypatch.setattr("common.agent_transport._load_agents_config", load)
    transport = AdapterTransport(adapter=FakeAdapter([]))
    assert transport._model("research") == "m1"
    assert transport._model("research") == "m2"


def test_empty_model_falls_back_to_settings_default(monkeypatch):
    monkeypatch.setattr(
        "common.agent_transport._load_agents_config",
        lambda: {"research": {"backend": "opencode", "model": ""}},
    )
    monkeypatch.setattr(
        "common.agent_transport.resolve_agent_model",
        lambda agent_id, config=None: "settings/default-model",
    )
    transport = AdapterTransport(adapter=FakeAdapter([]))
    assert transport._model("research") == "settings/default-model"


def test_lookup_interaction_session_reads_latest(env):
    store, _ = env
    iid = "pro_x:t1:execute:1"
    store.create_interaction(iid, "execute", "pro_x", task_id="t1", agent_id="research")
    store.append_run_event(iid, "session", {"session_id": "sess-old"})
    store.append_run_event(iid, "session", {"session_id": "sess-new"})
    assert lookup_interaction_session(store, iid) == "sess-new"


def test_resolve_gate_retry_session_from_store(env):
    store, _ = env
    store.create_interaction("pro_x:t1:execute:1", "execute", "pro_x",
                             task_id="t1", agent_id="research")
    store.append_run_event("pro_x:t1:execute:1", "session", {"session_id": "sess-abc"})
    from common.contracts import parse_request
    req = parse_request({
        "interaction_id": "pro_x:t1:execute:2", "kind": "execute",
        "project_id": "pro_x", "task_id": "t1", "agent_id": "research",
        "input": {}, "response_schema": "execute.result@1.0",
    })
    assert resolve_gate_retry_session(store, req) == "sess-abc"


def test_gate_retry_emits_gate_retry_session_event(env):
    """R-K17：attempt>1 且 resolver 返回 session 时写入 gate_retry_session。"""
    store, _ = env
    store.create_interaction("pro_x:t1:execute:1", "execute", "pro_x",
                             task_id="t1", agent_id="research")
    store.append_run_event("pro_x:t1:execute:1", "session", {"session_id": "sess-abc"})

    import threading

    emitted: list[tuple[str, dict]] = []

    class Ctx:
        request = None
        cancelled = False
        _cancel = threading.Event()
        cancel_event = _cancel

        def emit(self, kind, payload=None):
            emitted.append((kind, payload or {}))

    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "pro_x:t1:execute:2", "kind": "execute",
        "project_id": "pro_x", "task_id": "t1", "agent_id": "research",
        "input": {"deliverable_path": "t1.md", "deliverable_base": "/tmp"},
        "response_schema": "execute.result@1.0",
    })
    ctx = Ctx()
    ctx.request = req

    adapter = FakeAdapter([FakeEvent("step_start")])
    transport = AdapterTransport(
        adapter=adapter,
        agents_config={"research": {"model": "m1"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
        session_resolver=make_gate_session_resolver(store),
        prompt_builder=lambda *a, **k: "prompt",
    )
    transport(ctx)
    kinds = [k for k, _ in emitted]
    assert "gate_retry_session" in kinds
    ev = next(p for k, p in emitted if k == "gate_retry_session")
    assert ev["session_id"] == "sess-abc"
    assert ev["attempt"] == 2


def test_gate_session_resolver_passes_session_on_retry(env):
    store, wcfg = env
    call_n = {"n": 0}

    def write_resp(run_request):
        call_n["n"] += 1
        iid = f"pro_x:task_001:execute:{call_n['n']}"
        rel = "task_001_deliverable.md"
        (paths.deliverables_dir("pro_x") / rel).write_text(
            "# x\n## 调研背景\n足够内容。\n", encoding="utf-8",
        )
        submit({
            "interaction_id": iid, "kind": "execute", "status": "ok",
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact",
                                   "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir("research") / f"{iid}.response")

    adapter = FakeAdapter(
        [FakeEvent("session", {"session_id": "sess-retry"}), FakeEvent("step_start"), "_submit"],
        on_run=write_resp,
    )
    transport = AdapterTransport(
        adapter=adapter,
        agents_config={"research": {"model": "m1"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
        session_resolver=make_gate_session_resolver(store),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    port.run(_req("pro_x:task_001:execute:1"))
    port.run(_req("pro_x:task_001:execute:2"))
    assert adapter.last_request.session_id == "sess-retry"


def test_config_uses_injected_dict(monkeypatch):
    monkeypatch.setattr(
        "common.agent_transport._load_agents_config",
        lambda: {"research": {"model": "from_disk"}},
    )
    transport = AdapterTransport(
        adapter=FakeAdapter([]),
        agents_config={"research": {"model": "fixed"}},
    )
    assert transport._model("research") == "fixed"
    assert transport._model("research") == "fixed"


def test_parallel_execute_workspace_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    ws = tmp_path / "workspaces" / "workspace-research"
    ws.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("# research", encoding="utf-8")
    from common.agent_transport import parallel_execute_workspace
    from types import SimpleNamespace

    req = SimpleNamespace(
        interaction_id="p1:t1:execute:1",
        kind="execute",
        project_id="p1",
        task_id="t1",
        agent_id="research",
    )
    iso = parallel_execute_workspace("research", req)
    assert iso == ws / "_parallel" / "p1" / "t1"
    assert (iso / "AGENTS.md").exists()
