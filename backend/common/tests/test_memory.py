#!/usr/bin/env python3
"""Phase 6 Context-Memory 测试（D16）。

验证标准：下游只拿到直接依赖的摘要（非全文）；KB 后端可配置切换；kb:// 引用可往返。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.memory import KB_SCHEME, SqliteMemory, get_backend  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


# ── KB 后端 ──────────────────────────────────────────────────


def test_sqlite_memory_roundtrip(tmp_path):
    store = Store(tmp_path / "s.db")
    kb = SqliteMemory(store)
    ref = kb.write("pro_x", "GEO 结论", "结构化数据是关键", tags=["geo"])
    assert ref.startswith(f"{KB_SCHEME}sqlite/")
    got = kb.get(ref)
    assert got["title"] == "GEO 结论" and got["ref"] == ref
    found = kb.search(tags=["geo"], project_id="pro_x")
    assert found and found[0]["ref"] == ref
    store.close()


def test_backend_factory_default_and_unknown(tmp_path):
    store = Store(tmp_path / "s.db")
    assert isinstance(get_backend(store), SqliteMemory)
    assert isinstance(get_backend(store, backend="sqlite"), SqliteMemory)
    with pytest.raises(NotImplementedError):
        get_backend(store, backend="gbrain")
    store.close()


# ── Process 上下文注入 ───────────────────────────────────────


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "state.db")
    cfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, cfg
    store.close()


def _valid(task_type):
    spec = get_spec(task_type)
    out = ["# 标题\n"]
    for s in spec.required_sections:
        out.append(f"## {s}\n「{s}」的足够具体内容，覆盖要点与细节说明充分到位。\n")
    return "\n".join(out)


def test_downstream_gets_direct_upstream_summary(env):
    store, wcfg = env
    seen_contexts = {}

    def transport(ctx):
        ctx.emit("step_start")
        req = ctx.request
        seen_contexts[req.task_id] = req.context
        rel = f"{req.task_id}_deliverable.md"
        (paths.deliverables_dir(req.project_id) / rel).write_text(_valid("research"), "utf-8")
        # 上游 agent 在响应里写摘要（notes）
        notes = "上游关键结论：GEO 引用率提升 3 倍" if req.task_id == "t1" else "下游产出"
        submit({
            "interaction_id": req.interaction_id, "kind": "execute", "status": "ok",
            "notes": notes,
            "quality": {"score": 0.9, "known_gaps": [], "notes": ""},
            "result": {"outcome": {"kind": "artifact",
                                   "artifact": {"path": rel, "title": "x"}}},
        }, paths.response_dir(req.agent_id) / f"{req.interaction_id}.response")

    proc = Process(store, AgentPort(transport, store=store, config=wcfg), ProcessConfig())
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "research", "task_type": "research", "dependencies": ["t1"]},
    ]
    out = proc.run("pro_x", agents=["research"], tasks=tasks)
    assert out.status == "completed"
    # t1 无上游 → 无 upstream；t2 拿到 t1 的摘要 + 引用，而非全文
    assert seen_contexts["t1"] == {}
    up = seen_contexts["t2"]["upstream"]
    assert len(up) == 1
    assert up[0]["task_id"] == "t1"
    assert "GEO 引用率提升 3 倍" in up[0]["summary"]
    assert up[0]["ref"] == "t1_deliverable.md"
    # 注入的是摘要而非整篇交付物正文
    assert "## 调研背景" not in up[0]["summary"]
