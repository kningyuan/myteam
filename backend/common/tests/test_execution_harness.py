#!/usr/bin/env python3
"""execution_harness 单测。"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.store import Store
from execution_harness.config import harness_enabled
from execution_harness.context import ExecuteHarnessContext, TaskCompleteContext
from execution_harness.facade import inject_for_execute, on_task_complete, prepare_execute_harness
from execution_harness.post.pending import create_pending_bundle, list_pending
from execution_harness.post.review import (
    build_skill_review_request,
    record_review_from_response,
    should_trigger_review,
)
from execution_harness.skill.references import reference_file, write_reference_from_ledger
from execution_harness.skill.umbrella import resolve_umbrella_skill, reload_mapping


@pytest.fixture(autouse=True)
def _enable_harness(monkeypatch):
    monkeypatch.setenv(
        "MYTEAM_ROOT",
        str(Path(__file__).resolve().parents[2]),
    )
    reload_mapping()


def test_harness_enabled_default():
    assert harness_enabled() is True


def test_resolve_umbrella_research():
    assert resolve_umbrella_skill("research") == "product-methodology"


def test_inject_umbrella_block():
    lines: list[str] = []
    inject_for_execute(
        ExecuteHarnessContext(
            lines=lines,
            project_id="p1",
            task_type="research",
            agent_id="product",
        )
    )
    assert any("推荐方法论 Skill" in ln for ln in lines)


def test_write_reference_from_ledger(tmp_path):
    umbrella = "product-methodology"
    ledger = tmp_path / "ledger.entry.yaml"
    ledger.write_text(
        "task: research\nfindings: multiple sources cited\nnotes: " + ("x" * 40) + "\n",
        encoding="utf-8",
    )
    out = write_reference_from_ledger(umbrella, tmp_path, "research", "t1")
    assert out is not None and out.is_file()
    assert out == reference_file(umbrella, "research", "t1")


def test_promote_on_task_complete(tmp_path):
    store = Store(tmp_path / "s.db")
    base = tmp_path / "deliv"
    base.mkdir()
    (base / "ledger.entry.yaml").write_text(
        "task: research\nresult: ok\n" + ("detail: line\n" * 5),
        encoding="utf-8",
    )
    ref = on_task_complete(
        TaskCompleteContext(
            base_dir=base,
            project_id="proj",
            task_id="t1",
            task_type="research",
            store=store,
            agent_id="product",
            gate_passed=True,
        ),
        port_run=None,
    )
    assert ref is not None
    store.close()


def test_skill_review_pending():
    pid = create_pending_bundle(
        project_id="p",
        task_id="t",
        task_type="research",
        agent_id="product",
        action="patch",
        skill_id="product-methodology",
        notes="add pitfall",
        content="## Pitfalls\n- foo",
    )
    pending = list_pending()
    assert any(p["pending_id"] == pid for p in pending)


def test_should_trigger_review():
    ctx = TaskCompleteContext(
        base_dir=Path("/tmp"),
        project_id="p",
        task_id="t",
        task_type="research",
        store=Store(":memory:"),
        agent_id="product",
        gate_passed=True,
        attempt=1,
        status="completed",
    )
    assert should_trigger_review(ctx) is True


def test_record_review_from_response():
    ctx = TaskCompleteContext(
        base_dir=Path("/tmp"),
        project_id="p",
        task_id="t",
        task_type="research",
        store=Store(":memory:"),
        agent_id="product",
        gate_passed=True,
    )
    pid = record_review_from_response(
        ctx,
        {
            "result": {
                "action": "patch",
                "skill_id": "product-methodology",
                "notes": "n",
                "pending_content": "## Pitfalls",
            }
        },
    )
    assert pid


def test_build_skill_review_request(tmp_path):
    store = Store(tmp_path / "s.db")
    ctx = TaskCompleteContext(
        base_dir=Path("/tmp"),
        project_id="p",
        task_id="t1",
        task_type="research",
        store=store,
        agent_id="product",
        gate_passed=True,
        interaction_id="p:t1:execute:1",
        attempt=1,
    )
    req = build_skill_review_request(ctx, store)
    assert req["kind"] == "skill_review"
    assert req["constraints"]["umbrella_skill"] == "product-methodology"
    store.close()


def test_prepare_execute_harness(tmp_path, monkeypatch):
    from common.paths import WORKSPACES_DIR

    aid = "test-harness-agent"
    ws = WORKSPACES_DIR / f"workspace-{aid}"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "MEMORY.md").write_text("remember this", encoding="utf-8")
    lines: list[str] = []
    summary = prepare_execute_harness(
        ExecuteHarnessContext(
            lines=lines,
            project_id="p",
            task_type="research",
            agent_id=aid,
            workspace=ws,
        )
    )
    assert summary.get("umbrella") == "product-methodology"
    assert (ws / "MEMORY.md").is_file()
