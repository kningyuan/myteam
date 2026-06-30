#!/usr/bin/env python3
"""Layer B Web/API 补齐 — distill、user_store、pending、memory。"""
from __future__ import annotations

from execution_harness.post.distill import distill_ledger_body
from execution_harness.post.pending import (
    approve_pending,
    create_pending_bundle,
    list_pending,
    reject_pending,
)
from memstack.preferences.user_store import read_canonical_user_md, write_canonical_user_md


def test_distill_multiline_summary_block():
    raw = (
        "task_id: t-eval-01\n"
        "task_type: research\n"
        "summary: |\n"
        "  用户要求竞品表格必须含价格列\n"
        "  第二次交付已补齐\n"
        "pitfalls:\n"
        "  - 勿省略价格列\n"
        "keywords:\n"
        "  - 竞品表格\n"
        "  - 价格列\n"
    )
    out = distill_ledger_body(raw, task_type="research", task_id="t-eval-01")
    assert "用户要求竞品表格" in out
    assert "勿省略价格列" in out
    assert "竞品表格" in out


def test_user_store_global(tmp_path, monkeypatch):
    from memstack.preferences import user_store as us

    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr(us, "CONFIG_DIR", cfg)
    monkeypatch.setattr(us, "GLOBAL_USER_PATH", cfg / "USER.md")
    monkeypatch.setattr(us, "LEGACY_USERS_DIR", cfg / "users")

    path = us.write_global_user_md("# Team rules\n- verify\n")
    assert path.is_file()
    assert "verify" in us.read_global_user_md()
    assert us.read_canonical_user_md("product", agent_id="product") == us.read_global_user_md()


def test_user_store_write_read_legacy(tmp_path, monkeypatch):
    from memstack.preferences import user_store as us

    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr(us, "CONFIG_DIR", cfg)
    ws_root = tmp_path / "workspace"
    monkeypatch.setattr(us, "workspace_dir", lambda aid: ws_root / aid)

    path = write_canonical_user_md("product", "# Rules\n- foo\n", agent_id="product")
    assert path.is_file()
    assert "foo" in read_canonical_user_md("product", agent_id="product")
    ws_copy = ws_root / "product" / "USER.md"
    assert ws_copy.is_file()
    assert "foo" in ws_copy.read_text(encoding="utf-8")


def test_pending_approve_patch(tmp_path, monkeypatch):
    from execution_harness.post import pending as pm

    pending_root = tmp_path / "_pending"
    skills = tmp_path / "skills"
    monkeypatch.setattr(pm, "PENDING_SKILLS_DIR", pending_root)
    monkeypatch.setattr(pm, "SKILLS_DIR", skills)

    pid = create_pending_bundle(
        project_id="p",
        task_id="t1",
        task_type="research",
        agent_id="product",
        action="patch",
        skill_id="demo-skill",
        content="## Pitfalls\n- always verify\n",
    )
    assert any(x["pending_id"] == pid for x in list_pending())
    skill_dir = skills / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    res = approve_pending(pid)
    assert res["success"]
    assert "always verify" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert not list_pending()


def test_pending_reject(tmp_path, monkeypatch):
    from execution_harness.post import pending as pm

    monkeypatch.setattr(pm, "PENDING_SKILLS_DIR", tmp_path / "_pending")
    pid = create_pending_bundle(
        project_id="p",
        task_id="t2",
        task_type="research",
        agent_id="product",
        action="patch",
        skill_id="x",
        content="noop",
    )
    assert reject_pending(pid)["success"]
    assert not list_pending()


def test_memory_update(tmp_path):
    from common.store.store import Store

    store = Store(tmp_path / "mem.db")
    store.upsert_project("sa-test", title="test", status="active")
    mid = store.memory_write("sa-test", "title1", "body1", tags=["research"])
    ok = store.memory_update(mid, title="title2", content="body2", tags=["distilled"])
    assert ok
    row = store.memory_get(mid)
    assert row["title"] == "title2"
    assert row["content"] == "body2"
    assert "distilled" in row["tags"]
    store.close()
