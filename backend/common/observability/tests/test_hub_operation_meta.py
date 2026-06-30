#!/usr/bin/env python3
"""hub_operation_meta — Hub 操作时间记录。"""
from __future__ import annotations

import pytest

from common.observability import hub_operation_meta as hom


@pytest.fixture
def meta_file(tmp_path, monkeypatch):
    fp = tmp_path / "hub_operation_meta.json"
    monkeypatch.setattr(hom, "_META_FILE", fp)
    return fp


def test_touch_and_get_ts(meta_file):
    ts = hom.touch("agent", "product")
    assert hom.get_ts("agent", "product") == ts
    assert "product" in hom.map_for_kind("agent")


def test_sort_by_operated_at(meta_file):
    hom.touch("task_type", "research")
    hom.touch("task_type", "requirements")
    items = [
        {"task_type": "strategy", "operated_at": ""},
        {"task_type": "research", "operated_at": hom.get_ts("task_type", "research")},
        {"task_type": "requirements", "operated_at": hom.get_ts("task_type", "requirements")},
    ]
    sorted_items = hom.sort_by_operated_at(items, id_key="task_type")
    assert sorted_items[0]["task_type"] == "requirements"
    assert sorted_items[-1]["task_type"] == "strategy"


def test_remove_on_delete(meta_file):
    hom.touch("workflow", "wf-a")
    hom.remove("workflow", "wf-a")
    assert hom.get_ts("workflow", "wf-a") is None


def test_attach_operated_at(meta_file):
    hom.touch("agent", "arch")
    rows = hom.attach_operated_at([{"id": "arch"}, {"id": "qa"}], "agent")
    assert rows[0]["operated_at"]
    assert rows[1]["operated_at"] == ""
