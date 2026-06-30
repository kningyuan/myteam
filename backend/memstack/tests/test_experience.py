#!/usr/bin/env python3
"""experience ledger → KB 单元测试。"""
from __future__ import annotations

from memstack.orchestration.experience import append_experience_hints, promote_ledger_to_memory
from common.store.store import Store


def test_experience_promote_and_inject(tmp_path):
    store = Store(db_path=str(tmp_path / "test.db"))
    ledger = tmp_path / "ledger.entry.yaml"
    ledger.write_text(
        "task_id: t1\ntask_type: diagram-build\nlesson:\n  worked: ok\n  next_time: x\n",
        encoding="utf-8",
    )
    ref = promote_ledger_to_memory(tmp_path, "proj1", "t1", "diagram-build", store)
    assert ref and ref.startswith("kb://")

    lines: list[str] = []
    append_experience_hints(lines, "proj1", "diagram-build", store=store)
    assert any("同类任务经验" in ln for ln in lines)
