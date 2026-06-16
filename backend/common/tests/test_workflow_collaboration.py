#!/usr/bin/env python3
"""workflow_collaboration 单元测试。"""
from __future__ import annotations

from common.workflow_collaboration import (
    collaboration_for_project,
    collaboration_from_options,
    group_discussion_enabled,
    loop_discussion_profile_id,
    notifications_enabled,
    project_group_enabled,
)
from common.workflow_loader import load_workflow


def test_legacy_flat_options_compat():
    cfg = collaboration_from_options({
        "group_discussion_enabled": True,
        "loop_discussion_profile": "work-review-alignment",
    })
    assert cfg.group_discussion_enabled is True
    assert cfg.loop_discussion_profile == "work-review-alignment"


def test_collaboration_nested_overrides_legacy():
    cfg = collaboration_from_options({
        "group_discussion_enabled": True,
        "collaboration": {
            "group_discussion": {"enabled": False, "profile": "other"},
            "notifications": {"enabled": False},
            "project_group": {"enabled": False, "include_main": False},
        },
    })
    assert cfg.project_group_enabled is False
    assert cfg.include_main is False
    assert cfg.notifications_enabled is False
    assert cfg.group_discussion_enabled is False
    assert cfg.loop_discussion_profile == "other"


def test_plan_improve_workflow_collaboration():
    wf = load_workflow("方案完善")
    cfg = collaboration_from_options(wf.options)
    assert cfg.project_group_enabled is True
    assert cfg.group_discussion_enabled is True
    assert cfg.loop_discussion_profile == "work-review-alignment"


def test_project_fallback_without_store(monkeypatch):
    monkeypatch.setattr(
        "common.workflow_collaboration.collaboration_for_project",
        lambda pid: collaboration_from_options({}),
    )
    monkeypatch.setattr("common.skill_settings.is_auto_group_enabled", lambda: True)
    monkeypatch.setattr("common.skill_settings.is_project_group_enabled", lambda: True)
    assert project_group_enabled("pro_test") is True
    assert notifications_enabled("pro_test") is True


def test_collaboration_for_project_reads_meta(monkeypatch):
    class FakeStore:
        def get_project(self, project_id: str):
            return {"meta": {"workflow": "方案完善"}}

        def close(self):
            pass

    monkeypatch.setattr("common.store.Store", FakeStore)
    cfg = collaboration_for_project("pro_discuss")
    assert cfg.project_group_enabled is True
    assert loop_discussion_profile_id("pro_discuss") == "work-review-alignment"
    assert group_discussion_enabled("pro_discuss") is True
