"""群组管理测试 — CRUD / 成员管理 / @mention 路由。

用 tmp_path 隔离 GROUPS_FILE（经 conftest 的 isolated_paths patch 到 tmp）。
不测圆桌讨论执行（依赖 stream_chat），只测 CRUD 与路由逻辑。

注意：get_group 内部调用 _agent_display_names_for_members（依赖 scan_agents +
hub.services.agent_registry.get_agents_registry，后者会读真实 agents_registry），
故本模块用 autouse fixture 把它 stub 成纯函数，聚焦 CRUD 本身。
"""
from __future__ import annotations

import pytest

import base.group_manager as gm
from base.group_manager import (
    add_member,
    create_group,
    delete_group,
    detect_group_mode,
    dissolve_group,
    get_group,
    list_groups,
    remove_member,
    resolve_mentions,
    restore_group,
    search_groups,
)


@pytest.fixture(autouse=True)
def _stub_display_names(monkeypatch):
    """stub _agent_display_names_for_members（get_group 的辅助函数，依赖外部 registry）。"""
    monkeypatch.setattr(
        gm, "_agent_display_names_for_members",
        lambda members: {m: m for m in members},
    )


def _patch_scan_agents(monkeypatch, ids):
    """把 group_manager 绑定的 scan_agents 替换为受控列表（add_member 校验存在性用）。"""
    monkeypatch.setattr(gm, "scan_agents", lambda: [{"id": i} for i in ids])


# ============ 群组 CRUD ============

def test_create_group_returns_group_with_id():
    g = create_group("测试群", description="desc")
    assert g["name"] == "测试群"
    assert g["description"] == "desc"
    assert g["id"].startswith("g_")
    assert g["members"] == []
    assert g["messages"] == []


def test_create_group_persists_to_groups_file():
    g = create_group("持久化群")
    # GROUPS_FILE 已被 conftest patch 到 tmp；写入后能再次读出
    import json
    data = json.loads(gm.GROUPS_FILE.read_text(encoding="utf-8"))
    assert g["id"] in data
    assert data[g["id"]]["name"] == "持久化群"


def test_list_groups_excludes_dissolved_by_default():
    g1 = create_group("群A")
    g2 = create_group("群B")
    assert {g1["id"], g2["id"]} <= {g["id"] for g in list_groups()}

    dissolve_group(g2["id"])
    active_ids = {g["id"] for g in list_groups()}
    assert g1["id"] in active_ids
    assert g2["id"] not in active_ids
    # include_dissolved=True 时可见
    all_ids = {g["id"] for g in list_groups(include_dissolved=True)}
    assert g2["id"] in all_ids


def test_get_group_returns_none_for_missing():
    assert get_group("nope") is None


def test_get_group_returns_details():
    g = create_group("详情群", description="d")
    got = get_group(g["id"])
    assert got is not None
    assert got["name"] == "详情群"
    assert got["description"] == "d"
    assert got["members"] == []
    assert got["messages"] == []


def test_delete_group_permanent():
    g = create_group("待删")
    assert delete_group(g["id"]) is True
    assert get_group(g["id"]) is None
    assert delete_group("missing") is False


def test_dissolve_then_restore_lifecycle():
    g = create_group("圆桌群")
    ok, _ = dissolve_group(g["id"])
    assert ok is True
    # 重复解散
    ok2, _ = dissolve_group(g["id"])
    assert ok2 is False
    # 恢复
    ok3, _ = restore_group(g["id"])
    assert ok3 is True
    assert get_group(g["id"]) is not None
    # 重复恢复
    ok4, _ = restore_group(g["id"])
    assert ok4 is False


def test_dissolve_group_missing():
    assert dissolve_group("ghost") == (False, "群组不存在")


def test_restore_group_missing():
    assert restore_group("ghost") == (False, "群组不存在")


def test_search_groups_by_name():
    create_group("前端讨论组")
    create_group("后端讨论组")
    res = search_groups("前端")
    assert any(r["name"] == "前端讨论组" for r in res)
    assert not any(r["name"] == "后端讨论组" for r in res)


def test_search_groups_empty_query_matches_all():
    create_group("群X")
    res = search_groups("")
    assert any(r["name"] == "群X" for r in res)


# ============ 成员管理 ============

def test_add_member_succeeds_for_existing_agent(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice", "bob"])
    g = create_group("成员群")
    ok, _ = add_member(g["id"], "alice")
    assert ok is True
    got = get_group(g["id"])
    assert got["members"] == ["alice"]


def test_add_member_rejects_duplicate(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice"])
    g = create_group("去重群")
    add_member(g["id"], "alice")
    ok, msg = add_member(g["id"], "alice")
    assert ok is False
    assert "已在群组中" in msg


def test_add_member_rejects_unknown_agent(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice"])
    g = create_group("校验群")
    ok, msg = add_member(g["id"], "ghost")
    assert ok is False
    assert "不存在" in msg


def test_add_member_missing_group(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice"])
    assert add_member("nope", "alice") == (False, "群组不存在")


def test_remove_member(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice", "bob"])
    g = create_group("移除群")
    add_member(g["id"], "alice")
    add_member(g["id"], "bob")
    ok, _ = remove_member(g["id"], "alice")
    assert ok is True
    assert get_group(g["id"])["members"] == ["bob"]


def test_remove_member_not_in_group(monkeypatch):
    _patch_scan_agents(monkeypatch, ["alice"])
    g = create_group("空群")
    assert remove_member(g["id"], "alice") == (False, "Agent 'alice' 不在群组中")


def test_remove_member_missing_group(monkeypatch):
    _patch_scan_agents(monkeypatch, ["bob"])
    assert remove_member("nope", "bob") == (False, "群组不存在")


# ============ @mention 路由 ============

def test_resolve_mentions_single():
    members = ["main", "product", "arch"]
    assert resolve_mentions("请 @product 看一下", members) == ["product"]


def test_resolve_mentions_multiple():
    members = ["main", "product", "arch"]
    assert set(resolve_mentions("@arch @product 帮忙", members)) == {"arch", "product"}


def test_resolve_mentions_all_keyword_returns_all_members():
    members = ["main", "product", "arch"]
    assert set(resolve_mentions("@all 开会", members)) == set(members)
    assert set(resolve_mentions("@everyone 同步", members)) == set(members)


def test_resolve_mentions_none():
    assert resolve_mentions("普通消息", ["main", "product"]) == []


def test_detect_group_mode_roundtable_on_at_all():
    members = ["main", "product", "arch"]
    assert detect_group_mode("@all 讨论", members) == "roundtable"
    assert detect_group_mode("@everyone 讨论", members) == "roundtable"


def test_detect_group_mode_notify_for_specific():
    assert detect_group_mode("@product 看看", ["product"]) == "notify"
    assert detect_group_mode("@arch @product", ["arch", "product"]) == "notify"


def test_detect_group_mode_notify_when_no_mention():
    # 无 @mention → notify（不进圆桌）
    assert detect_group_mode("无提及的普通消息", []) == "notify"
