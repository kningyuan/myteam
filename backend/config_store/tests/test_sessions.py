"""SessionStore 测试。

覆盖：
- 键格式 adapter_id:agent_id:workspace
- get / set（含 last_used 刷新、entry 字段）
- remove / remove_for_agent_workspace（后缀匹配语义、跨 adapter 批量删）
- 落盘持久化
"""
from __future__ import annotations

import json



# ── 键格式 ──


class TestKeyFormat:
    def test_key_is_adapter_agent_workspace(self, session_store):
        assert session_store._key("opencode", "agent1", "ws1") == "opencode:agent1:ws1"

    def test_set_uses_key_format_in_internal_map(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        assert "opencode:agent1:ws1" in session_store._map


# ── get / set ──


class TestSetGet:
    def test_get_missing_returns_none(self, session_store):
        assert session_store.get("opencode", "agent1", "ws1") is None

    def test_set_then_get_returns_session_id(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        assert session_store.get("opencode", "agent1", "ws1") == "sess-1"

    def test_set_entry_fields(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        entry = session_store._map["opencode:agent1:ws1"]
        assert entry["session_id"] == "sess-1"
        assert "created_at" in entry
        assert "last_used" in entry

    def test_get_updates_last_used(self, session_store):
        """get 会刷新 last_used 并落盘。"""
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        key = "opencode:agent1:ws1"
        # 伪造旧的 last_used / created_at，验证 get 之后 last_used 被刷新
        session_store._map[key]["last_used"] = 100.0
        session_store._map[key]["created_at"] = 100.0

        sid = session_store.get("opencode", "agent1", "ws1")
        assert sid == "sess-1"
        assert session_store._map[key]["last_used"] > 100.0

    def test_different_keys_isolated(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-a")
        session_store.set("opencode", "agent2", "ws1", "sess-b")
        session_store.set("claude", "agent1", "ws1", "sess-c")
        assert session_store.get("opencode", "agent1", "ws1") == "sess-a"
        assert session_store.get("opencode", "agent2", "ws1") == "sess-b"
        assert session_store.get("claude", "agent1", "ws1") == "sess-c"


# ── remove ──


class TestRemove:
    def test_remove_deletes_entry(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        session_store.remove("opencode", "agent1", "ws1")
        assert session_store.get("opencode", "agent1", "ws1") is None

    def test_remove_missing_is_noop(self, session_store):
        """删除不存在的键不应抛异常。"""
        session_store.remove("opencode", "agent1", "ws1")
        assert session_store.get("opencode", "agent1", "ws1") is None

    def test_remove_only_targets_specific_key(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-a")
        session_store.set("claude", "agent1", "ws1", "sess-c")
        session_store.remove("opencode", "agent1", "ws1")
        assert session_store.get("opencode", "agent1", "ws1") is None
        assert session_store.get("claude", "agent1", "ws1") == "sess-c"


# ── remove_for_agent_workspace ──


class TestRemoveForAgentWorkspace:
    def test_removes_all_adapters_for_agent_workspace(self, session_store):
        """移除某 agent+workspace 下所有 adapter 的 session，返回删除数。"""
        session_store.set("opencode", "agent1", "ws1", "sess-a")
        session_store.set("claude", "agent1", "ws1", "sess-c")
        session_store.set("opencode", "agent2", "ws1", "sess-b")

        n = session_store.remove_for_agent_workspace("agent1", "ws1")
        assert n == 2
        assert session_store.get("opencode", "agent1", "ws1") is None
        assert session_store.get("claude", "agent1", "ws1") is None
        # 其他 agent 不受影响
        assert session_store.get("opencode", "agent2", "ws1") == "sess-b"

    def test_returns_zero_when_nothing_matched(self, session_store):
        assert session_store.remove_for_agent_workspace("nobody", "nowhere") == 0

    def test_does_not_match_different_workspace(self, session_store):
        """后缀精确匹配 workspace_key，不同 workspace 不被误删。"""
        session_store.set("opencode", "agent1", "ws1", "sess-a")
        session_store.set("opencode", "agent1", "ws2", "sess-a2")
        n = session_store.remove_for_agent_workspace("agent1", "ws1")
        assert n == 1
        assert session_store.get("opencode", "agent1", "ws2") == "sess-a2"

    def test_suffix_match_not_confused_by_agent_in_adapter_slot(self, session_store):
        """键尾缀匹配 :agent_id:workspace_key；agent_id 出现在 adapter 位置不应误删。"""
        # key = "agent1:other:ws1"，后缀应是 ":agent1:ws1" → 不命中
        session_store.set("agent1", "other", "ws1", "trap")
        n = session_store.remove_for_agent_workspace("agent1", "ws1")
        assert n == 0
        assert session_store.get("agent1", "other", "ws1") == "trap"


# ── 落盘持久化 ──


class TestPersistence:
    def test_set_persists_to_disk(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        on_disk = json.loads(session_store.path.read_text(encoding="utf-8"))
        assert "opencode:agent1:ws1" in on_disk
        assert on_disk["opencode:agent1:ws1"]["session_id"] == "sess-1"

    def test_remove_persists_to_disk(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-1")
        session_store.remove("opencode", "agent1", "ws1")
        on_disk = json.loads(session_store.path.read_text(encoding="utf-8"))
        assert "opencode:agent1:ws1" not in on_disk

    def test_remove_for_agent_workspace_persists_to_disk(self, session_store):
        session_store.set("opencode", "agent1", "ws1", "sess-a")
        session_store.set("claude", "agent1", "ws1", "sess-c")
        session_store.remove_for_agent_workspace("agent1", "ws1")
        on_disk = json.loads(session_store.path.read_text(encoding="utf-8"))
        assert "opencode:agent1:ws1" not in on_disk
        assert "claude:agent1:ws1" not in on_disk
