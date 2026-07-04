#!/usr/bin/env python3
"""KB 召回测试 — tag 子集匹配 + 截断上限提升。"""
from __future__ import annotations

import pytest

from common.store.store import Store


@pytest.fixture()
def store(tmp_path):
    """用临时 SQLite 创建 Store"""
    s = Store(str(tmp_path / "test.db"))
    return s


def test_subset_tag_matching(store):
    """tag 子集匹配：只返回包含所有查询 tag 的条目"""
    store.memory_write(
        title="A", tags=["product", "research", "methodology"],
        content="A" * 300, project_id="__kb__",
    )
    store.memory_write(
        title="B", tags=["product", "planning"],
        content="B" * 300, project_id="__kb__",
    )
    store.memory_write(
        title="C", tags=["coding", "testing"],
        content="C" * 300, project_id="__kb__",
    )
    results = store.memory_search(tags=["product", "research"], project_id="__kb__")
    assert len(results) == 1
    assert results[0]["content"].startswith("A")


def test_single_tag_still_works(store):
    """单 tag 查询仍正常"""
    store.memory_write(title="A", tags=["product"], content="A", project_id="__kb__")
    store.memory_write(title="B", tags=["coding"], content="B", project_id="__kb__")
    results = store.memory_search(tags=["product"], project_id="__kb__")
    assert len(results) == 1
    assert results[0]["content"] == "A"


def test_no_match_returns_empty(store):
    """无匹配返回空列表"""
    store.memory_write(title="A", tags=["product"], content="A", project_id="__kb__")
    results = store.memory_search(tags=["nonexistent"], project_id="__kb__")
    assert len(results) == 0


def test_no_tags_returns_all(store):
    """无 tags 参数返回全部"""
    store.memory_write(title="A", tags=["a"], content="A", project_id="__kb__")
    store.memory_write(title="B", tags=["b"], content="B", project_id="__kb__")
    results = store.memory_search(tags=None, project_id="__kb__")
    assert len(results) == 2
