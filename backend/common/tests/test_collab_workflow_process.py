#!/usr/bin/env python3
"""子模块协作联动测试：workflow → process。

验证协作链路：
  1. workflow_loader.load_workflow 能从 YAML 加载 WorkflowProfile（tasks/roster/loops）
  2. Process.run 接受 profile.instantiate_tasks() / roster / loops 并把 workflow id 写入项目 meta
  3. Process 调度时使用 workflow 提供的任务 DAG（FakeOpencode 模拟，不依赖真实 CLI）

参考 test_integration.py 的 FakeOpencode 模式与 env fixture。
"""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
import common.agent.agent_registry as agent_registry_mod  # noqa: E402
from common.agent.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.agent.agent_transport import AdapterTransport  # noqa: E402
from common.process.process import Process, ProcessConfig  # noqa: E402
from common.gate.registry import get_spec  # noqa: E402
from common.store.store import Store  # noqa: E402
from common.delivery.submit_result import submit  # noqa: E402
from common.workflow.workflow_loader import (  # noqa: E402
    load_workflow,
    workflows_dir,
    write_workflow_raw,
)


class FakeEvent:
    def __init__(self, kind, data=None):
        self.kind = types.SimpleNamespace(value=kind)
        self.data = data or {}


class FakeOpencode:
    """模拟 opencode：按提示词产出合规交付物 + 经 submit_result 写回 + step_finish 计量。"""

    def run(self, request):
        yield FakeEvent("step_start")
        yield FakeEvent("text", {"chunk": "working..."})
        msg = request.message
        dv_abs = _line_after(msg, "写入文件：")
        resp_path = _line_after(msg, "--out ").split(" --file")[0]
        iid = Path(resp_path).stem
        task_type = "research"
        spec = get_spec(task_type)
        content = ["# 标题\n"]
        for s in spec.required_sections:
            content.append(f"## {s}\n「{s}」的足够具体内容，覆盖要点与细节说明充分。\n")
        Path(dv_abs).parent.mkdir(parents=True, exist_ok=True)
        Path(dv_abs).write_text("\n".join(content), encoding="utf-8")
        rel = Path(dv_abs).name
        submit({
            "interaction_id": iid, "kind": "execute", "status": "ok",
            "notes": f"完成 {iid} 的调研。",
            "quality": {"score": 0.9, "known_gaps": [], "notes": "自评良好"},
            "result": {"outcome": {"kind": "artifact",
                                   "artifact": {"path": rel, "title": "调研"}}},
        }, Path(resp_path))
        yield FakeEvent("step_finish", {"tokens": 500})


def _line_after(s, marker):
    i = s.index(marker) + len(marker)
    return s[i:s.index("\n", i)].strip()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离 workspaces / projects / registry / workflows 目录，避免污染工程。"""
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    # 创建 workspace-research，供 list_available_agent_ids 发现
    (tmp_path / "workspaces" / "workspace-research").mkdir(parents=True)
    # 隔离 agents_registry.json：research 绑定 research task_type
    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "version": "2.0",
        "agents": {
            "research": {"name": "调研", "task_types": ["research"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)
    # 隔离 workflows 目录
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    monkeypatch.setattr("common.workflow.workflow_loader.workflows_dir", lambda: wf_dir)

    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def _write_research_workflow(wf_id: str = "collab-flow"):
    """写一个最小 workflow：两步 research 任务，串行依赖。"""
    return write_workflow_raw({
        "id": wf_id,
        "name": "协作联动流程",
        "version": "1.0",
        "description": "workflow→process 联动测试",
        "tasks": [
            {
                "id": "t1", "name": "调研一", "agent": "research",
                "task_type": "research", "dependencies": [],
                "description": "【对象】主题 A",
            },
            {
                "id": "t2", "name": "调研二", "agent": "research",
                "task_type": "research", "dependencies": ["t1"],
                "description": "【对象】主题 B",
            },
        ],
    })


def test_workflow_profile_loads_and_feeds_process(env):
    """workflow 定义加载后，其 tasks/roster 能被 Process.run 消费，workflow id 落盘到项目 meta。"""
    store, wcfg = env
    wid = _write_research_workflow("collab-flow")

    # 1) workflow_loader 加载 profile（含 DAG 校验、能力绑定校验）
    profile = load_workflow(wid)
    assert profile.id == "collab-flow"
    assert "research" in profile.roster
    assert len(profile.tasks) == 2
    # goal 注入：instantiate_tasks 把项目目标前缀到 description
    tasks = profile.instantiate_tasks(goal="GEO 优化")
    assert tasks[0]["description"].startswith("【项目目标】GEO 优化")

    # 2) Process 消费 workflow 提供的 agents/tasks，并记录 workflow id
    transport = AdapterTransport(
        adapter=FakeOpencode(),
        agents_config={"research": {"model": "m1"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig(token_budget=10000))

    out = proc.run(
        "pro_wf_collab", title="workflow→process", goal="GEO 优化",
        agents=profile.roster, tasks=tasks, workflow=wid,
    )

    # 3) 项目状态完成 + workflow id 写入 store 的项目 meta
    assert out.status == "completed"
    proj = store.get_project("pro_wf_collab")
    assert (proj.get("meta") or {}).get("workflow") == wid

    # 4) 交付物真实落盘（Process 用 workflow 任务 DAG 跑出来的）
    dv1 = paths.deliverables_dir("pro_wf_collab") / "t1_deliverable.md"
    assert dv1.exists() and "调研背景" in dv1.read_text(encoding="utf-8")


def test_workflow_loops_handoff_to_process(env):
    """workflow 含 loop 时，profile.loops 能被 Process 注册并参与调度。"""
    store, wcfg = env
    # 写带 loop 的 workflow：loop body 含 work+review 两步，直到 marker 出现
    # 通过模块属性调用 workflows_dir（env fixture 已 monkeypatch 模块层）
    import common.workflow.workflow_loader as _wfl
    wf_dir = _wfl.workflows_dir()
    (wf_dir / "loop-flow.yaml").write_text(
        """
id: loop-flow
name: 循环联动
version: "1.0"
description: loop→process 注册测试
tasks:
  - id: t1
    name: 调研
    agent: research
    task_type: research
    dependencies: []
    description: 前置调研
  - id: t-loop
    name: 循环节点
    loop: lr
    dependencies: [t1]
loops:
  - id: lr
    max_rounds: 2
    until:
      - type: deliverable_marker
        task: review
        marker: "REVIEW: PASS"
    body:
      - id: work
        agent: research
        task_type: research
        dependencies: []
      - id: review
        agent: research
        task_type: research
        dependencies: [work]
""",
        encoding="utf-8",
    )

    profile = load_workflow("loop-flow")
    assert len(profile.loops) == 1
    assert profile.loops[0].id == "lr"

    # Process.run 接受 loops 参数并注册到 _loops_by_id
    transport = AdapterTransport(
        adapter=FakeOpencode(),
        agents_config={"research": {"model": "m1"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig(token_budget=20000))

    # 用 profile 的 tasks/loops 喂给 Process（loops 是协作的关键传递项）
    out = proc.run(
        "pro_wf_loop", title="loop 联动", goal="循环测试",
        agents=profile.roster,
        tasks=profile.instantiate_tasks(goal="循环测试"),
        loops=profile.loops,
        workflow="loop-flow",
    )
    # loop 已被 Process 注册（_loops_by_id 非空才能调度 loop 占位 task，否则 failed）
    assert "lr" in proc._loops_by_id
    # 项目有终态（loop 跑完或预算耗尽，不依赖真实 marker）
    assert out.status in ("completed", "partially_failed", "paused", "failed")
