#!/usr/bin/env python3
"""skill_extract scaffold 单测。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.paths import MYTEAM_ROOT, deliverables_dir  # noqa: E402
from common.skill_extract import (  # noqa: E402
    draft_dir,
    extract_skill_draft,
    list_skill_drafts,
    skill_draft_path,
)
from common.store import Store  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTEAM_ROOT", str(tmp_path))
    db = tmp_path / "business/tasks/state.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    return Store(db_path=db)


def test_extract_skill_draft_writes_minimal_skill(store, tmp_path, monkeypatch):
    monkeypatch.setattr("common.skill_extract.MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr("common.skill_extract.SKILLS_DIR", tmp_path / "business/skills")
    monkeypatch.setattr("common.paths.MYTEAM_ROOT", tmp_path)

    project_id = "proj-a"
    task_id = "skill-extract"
    store.upsert_project(project_id, title="t", mode="one_shot",
                         meta={"goal": "沉淀可复用调研模式"})
    store.upsert_task(project_id, task_id, agent="product", task_type="research")

    body = "A" * 600
    dv = deliverables_dir(project_id) / f"{task_id}_deliverable.md"
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text(body, encoding="utf-8")

    out = extract_skill_draft(store, project_id, task_id, dv)
    assert out == skill_draft_path(project_id, task_id)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "auto-proj-a-skill-extract" in text
    assert "task_type: research" in text
    assert "沉淀可复用调研模式" in text
    assert "A" * 500 in text
    assert "A" * 501 not in text


def test_list_skill_drafts(store, tmp_path, monkeypatch):
    monkeypatch.setattr("common.skill_extract.MYTEAM_ROOT", tmp_path)
    skills = tmp_path / "business/skills"
    monkeypatch.setattr("common.skill_extract.SKILLS_DIR", skills)

    d1 = draft_dir("p1", "t1")
    d2 = draft_dir("p2", "t2")
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    (d1 / "SKILL.md").write_text("# one", encoding="utf-8")
    (d2 / "SKILL.md").write_text("# two", encoding="utf-8")
    (skills / "publish-post").mkdir()
    (skills / "publish-post" / "SKILL.md").write_text("# real", encoding="utf-8")

    drafts = list_skill_drafts()
    assert len(drafts) == 2
    assert all(p.name == "SKILL.md" for p in drafts)
    assert all("auto-" in p.parent.name for p in drafts)
