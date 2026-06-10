#!/usr/bin/env python3
"""Phase 8 capstone：新框架全栈集成测试。

Process（单内核）→ AgentPort（串行/看门狗/计量）→ AdapterTransport（fake opencode 适配器）
→ Gate（契约+格式）→ Store（SQLite 真相）→ Observability（只读视图）。

证明七层抽象可组合跑通一个 DAG 项目，不依赖真实 opencode。
"""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
import common.agent_registry as agent_registry_mod  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.observability import cost, project_overview  # noqa: E402
from common.agent_transport import AdapterTransport  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


class FakeEvent:
    def __init__(self, kind, data=None):
        self.kind = types.SimpleNamespace(value=kind)
        self.data = data or {}


class FakeOpencode:
    """模拟 opencode：按提示词产出合规交付物 + 经 submit_result 写回 + step_finish 计量。"""

    def run(self, request):
        yield FakeEvent("step_start")
        yield FakeEvent("text", {"chunk": "working..."})
        # 解析提示词里的 interaction_id / deliverable / response 路径并完成任务
        msg = request.message
        dv_abs = _line_after(msg, "写入文件：")
        resp_path = _line_after(msg, "--out ").split(" --file")[0]
        iid = Path(resp_path).stem  # 文件名即 interaction_id（D12 命名约定）
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
            "notes": f"完成 {iid} 的调研，关键结论已沉淀。",
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
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "version": "2.0",
        "agents": {
            "research": {"task_types": ["research"]},
            "seo": {"task_types": ["research", "seo-plan"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)
    store = Store(tmp_path / "state.db")
    wcfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, wcfg
    store.close()


def test_full_stack_dag(env):
    store, wcfg = env
    transport = AdapterTransport(
        adapter=FakeOpencode(),
        agents_config={"research": {"model": "m1"}, "seo": {"model": "m2"}},
        request_factory=lambda **kw: types.SimpleNamespace(**kw),
    )
    port = AgentPort(transport, store=store, config=wcfg)
    proc = Process(store, port, ProcessConfig(token_budget=10000))

    tasks = [
        {"id": "task_001", "agent": "research", "task_type": "research", "dependencies": []},
        {"id": "task_002", "agent": "seo", "task_type": "research", "dependencies": ["task_001"]},
    ]
    out = proc.run("pro_geo", title="GEO 全栈", agents=["research", "seo"], tasks=tasks)

    # 1) 项目与任务状态
    assert out.status == "completed"
    assert out.tasks["task_001"].status == "completed"
    assert out.tasks["task_002"].status == "completed"

    # 2) 交付物真实落盘
    dv = paths.deliverables_dir("pro_geo") / "task_001_deliverable.md"
    assert dv.exists() and "调研背景" in dv.read_text(encoding="utf-8")

    # 3) Store 真相 + token 计量（每任务 500）
    c = cost(store, "pro_geo")
    assert c["project"] == 1000
    assert c["by_agent"] == {"research": 500, "seo": 500}

    # 4) 上游摘要被注入下游 task.meta（Context-Memory）
    t1_meta = store.get_task("pro_geo", "task_001")["meta"]
    assert "调研" in (t1_meta.get("summary") or "")

    # 5) 可观测只读视图自洽
    ov = project_overview(store, "pro_geo")
    assert ov["status"] == "completed" and ov["progress"] == 1.0
