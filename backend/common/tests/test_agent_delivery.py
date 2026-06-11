#!/usr/bin/env python3
"""过程产物 scaffold、Gate 过程校验、经验沉淀。"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.deliverable_guarantee import scaffold_process_artifacts
from common.experience import append_experience_hints, promote_ledger_to_memory
from common.gate import check_execute, check_process_artifacts
from common.registry import get_spec, invalidate_registry_cache
from common.delivery_profiles import invalidate_delivery_profiles_cache
from common.store import Store


@pytest.fixture(autouse=True)
def _clear_caches():
    invalidate_registry_cache()
    invalidate_delivery_profiles_cache()
    yield
    invalidate_registry_cache()
    invalidate_delivery_profiles_cache()


def test_scaffold_light_v1_creates_templates(tmp_path):
    scaffold_process_artifacts(tmp_path, "light_v1")
    assert (tmp_path / "align.md").is_file()
    assert (tmp_path / "verify.log").is_file()
    assert "<!--" in (tmp_path / "align.md").read_text()


def test_scaffold_does_not_overwrite_filled_align(tmp_path):
    scaffold_process_artifacts(tmp_path, "light_v1")
    filled = tmp_path / "align.md"
    filled.write_text("# Align\n\n## 对象\n\n已填写内容\n", encoding="utf-8")
    scaffold_process_artifacts(tmp_path, "light_v1")
    assert "已填写内容" in filled.read_text()


def test_process_gate_rejects_template_align(tmp_path):
    spec = get_spec("product-research")
    tpl = (
        Path(__file__).resolve().parents[3] / "business/playbooks/templates/align.md"
    )
    (tmp_path / "align.md").write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "verify.log").write_text("PASS: sections ok\n", encoding="utf-8")
    res = check_process_artifacts(spec, tmp_path)
    assert not res.passed
    assert any(f["rule"] == "process_artifact" for f in res.failures)


def test_process_gate_accepts_filled_align(tmp_path):
    spec = get_spec("product-research")
    (tmp_path / "align.md").write_text(
        "# Align\n\n## 对象\n\n面向 PM 的竞品调研摘要\n\n## 输入\n\nworkflow\n\n"
        "## 成功标准\n\n章节齐全\n\n## 非目标\n\n不写代码\n",
        encoding="utf-8",
    )
    (tmp_path / "verify.log").write_text("PASS: all sections present\n", encoding="utf-8")
    res = check_process_artifacts(spec, tmp_path)
    assert res.passed


def _execute_env(task_type: str, rel_path: str) -> dict:
    return {
        "kind": "execute",
        "status": "ok",
        "quality": {"score": 0.8, "known_gaps": []},
        "result": {
            "outcome": {
                "kind": "artifact",
                "artifact": {"path": rel_path, "format": "markdown", "title": "t"},
            }
        },
        "meta": {"task_type": task_type},
    }


def test_check_execute_light_v1_process_failure(tmp_path):
    dv = tmp_path / "t-brief_deliverable.md"
    dv.write_text(
        "# 产品调研\n\n## 调研背景\n\n背景\n\n## 核心发现\n\n发现\n\n"
        "## 机会与风险\n\n机会\n\n## 建议\n\n建议\n",
        encoding="utf-8",
    )
    scaffold_process_artifacts(tmp_path, "light_v1")
    env = _execute_env("product-research", dv.name)
    res = check_execute(env, base_dir=str(tmp_path))
    assert not res.passed


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
