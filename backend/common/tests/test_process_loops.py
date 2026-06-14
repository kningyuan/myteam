#!/usr/bin/env python3
"""Process workflow loop 集成测试（fake transport）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent_port import AgentPort, WatchdogConfig  # noqa: E402
from common.loop_runtime import LoopSpec  # noqa: E402
from common.process import Process, ProcessConfig  # noqa: E402
from common.registry import get_spec  # noqa: E402
from common.store import Store  # noqa: E402
from common.submit_result import submit  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    bc = tmp_path / "business" / "config"
    bc.mkdir(parents=True)
    reg = {
        "agents": {
            "main": {"task_types": ["strategy"]},
            "product": {"task_types": ["research", "strategy", "product-planning"]},
            "arch": {"task_types": ["research", "architecture-review"]},
        }
    }
    reg_file = bc / "agents_registry.json"
    reg_file.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(paths, "BUSINESS_CONFIG_DIR", bc)
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", reg_file)
    monkeypatch.setattr("common.agent_id_policy.BUSINESS_CONFIG_DIR", bc)
    for aid in ("product", "arch"):
        ws = tmp_path / "workspaces" / f"workspace-{aid}"
        ws.mkdir(parents=True)
        (ws / ".trigger").mkdir(exist_ok=True)
        (ws / ".response").mkdir(exist_ok=True)
    store = Store(tmp_path / "state.db")
    cfg = WatchdogConfig(soft_idle_sec=5, hard_idle_sec=10, poll_interval=0.02, max_attempts=1)
    yield store, cfg
    store.close()


def _valid(tt: str) -> str:
    spec = get_spec(tt)
    lines = ["# T\n"]
    for s in spec.required_sections:
        lines.append(f"## {s}\n内容足够长，用于通过 Gate 校验，包含具体细节与说明。\n")
    return "\n".join(lines)


def _acceptance_with_marker(marker: str) -> str:
    body = _valid("architecture-review")
    return body + f"\n\n{marker}\n"


def _ensure_process_artifacts(project_id: str) -> None:
    base = paths.deliverables_dir(project_id)
    base.mkdir(parents=True, exist_ok=True)
    align = base / "align.md"
    align.write_text(
        "# Align\n\n## 对象\n\n目标\n\n## 输入\n\n输入\n\n## 成功标准\n\n标准\n\n## 非目标\n\n无\n",
        encoding="utf-8",
    )
    (base / "verify.log").write_text("PASS: self-check ok\n", encoding="utf-8")


GOOD_Q = {"score": 0.9, "known_gaps": [], "notes": "ok"}


def _write(ctx, content, quality):
    req = ctx.request
    _ensure_process_artifacts(req.project_id)
    rel = f"{req.task_id}_deliverable.md"
    dv = paths.deliverables_dir(req.project_id) / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text(content, encoding="utf-8")
    env = {
        "interaction_id": req.interaction_id, "kind": "execute", "status": "ok",
        "quality": quality,
        "result": {"outcome": {"kind": "artifact", "artifact": {"path": rel, "title": "x"}}},
    }
    submit(env, paths.response_dir(req.agent_id) / f"{req.interaction_id}.response")


def test_loop_passes_on_first_round(env):
    store, wcfg = env
    review_round = {"n": 0}

    def transport(ctx):
        tid = ctx.request.task_id
        if tid.endswith("-work"):
            _write(ctx, _valid("strategy"), GOOD_Q)
        elif tid.endswith("-review"):
            review_round["n"] += 1
            _write(ctx, _acceptance_with_marker("REVIEW: PASS"), GOOD_Q)

    loop = LoopSpec(
        id="unit",
        max_rounds=5,
        body=[
            {"id": "work", "agent": "product", "task_type": "strategy", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "architecture-review",
             "dependencies": ["work"]},
        ],
        until=[{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
    )
    proc = Process(store, AgentPort(transport, store=store, config=wcfg), ProcessConfig())
    tasks = [
        {"id": "t-loop", "name": "loop", "loop": "unit", "dependencies": []},
    ]
    out = proc.run("p_loop", tasks=tasks, agents=["main", "product", "arch"], loops=[loop])
    assert out.tasks["t-loop"].status == "completed"
    assert review_round["n"] == 1


def test_loop_exhausts_after_max_rounds(env):
    store, wcfg = env
    review_round = {"n": 0}

    def transport(ctx):
        tid = ctx.request.task_id
        if tid.endswith("-work"):
            _write(ctx, _valid("strategy"), GOOD_Q)
        elif tid.endswith("-review"):
            review_round["n"] += 1
            _write(ctx, _acceptance_with_marker("REVIEW: FAIL"), GOOD_Q)

    loop = LoopSpec(
        id="unit",
        max_rounds=3,
        on_exhaust="needs_review",
        body=[
            {"id": "work", "agent": "product", "task_type": "strategy", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "architecture-review",
             "dependencies": ["work"]},
        ],
        until=[{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
    )
    proc = Process(store, AgentPort(transport, store=store, config=wcfg), ProcessConfig())
    tasks = [{"id": "t-loop", "name": "loop", "loop": "unit", "dependencies": []}]
    out = proc.run("p_ex", tasks=tasks, agents=["main", "product", "arch"], loops=[loop])
    assert out.tasks["t-loop"].status == "needs_review"
    assert review_round["n"] == 3


def test_loop_passes_on_third_round(env):
    store, wcfg = env
    state = {"round": 0}

    def transport(ctx):
        tid = ctx.request.task_id
        if tid.endswith("-work"):
            _write(ctx, _valid("strategy"), GOOD_Q)
        elif tid.endswith("-review"):
            state["round"] += 1
            marker = "REVIEW: PASS" if state["round"] >= 3 else "REVIEW: FAIL"
            _write(ctx, _acceptance_with_marker(marker), GOOD_Q)

    loop = LoopSpec(
        id="unit",
        max_rounds=5,
        body=[
            {"id": "work", "agent": "product", "task_type": "strategy", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "architecture-review",
             "dependencies": ["work"]},
        ],
        until=[{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
    )
    proc = Process(store, AgentPort(transport, store=store, config=wcfg), ProcessConfig())
    out = proc.run("p_r3", tasks=[{"id": "t-loop", "loop": "unit", "dependencies": []}],
                   agents=["main", "product", "arch"], loops=[loop])
    assert out.tasks["t-loop"].status == "completed"
    assert state["round"] == 3
