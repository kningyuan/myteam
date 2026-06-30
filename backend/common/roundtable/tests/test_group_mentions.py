#!/usr/bin/env python3
"""群组 @mention 路由单元测试。"""
from __future__ import annotations

from base.group_manager import resolve_mentions


def test_resolve_single_mention():
    members = ["main", "product", "research"]
    assert resolve_mentions("请 @product 看一下", members) == ["product"]


def test_resolve_all_mentions():
    members = ["main", "product", "research"]
    assert set(resolve_mentions("@all 开会", members)) == set(members)
    assert set(resolve_mentions("@everyone 同步", members)) == set(members)


def test_resolve_no_mention():
    members = ["main", "product"]
    assert resolve_mentions("普通消息", members) == []
