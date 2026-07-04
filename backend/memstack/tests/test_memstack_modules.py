#!/usr/bin/env python3
"""memstack 模块能力测试 — 不依赖 Hub/Process 端到端。

覆盖：config / kb / l1 / preferences / orchestration / injection / facade / anysearch
映射：MEMSTACK_VERIFY E-ISO / E-KB / E-L1 / E-PREF / E-ARCH
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store.store import Store


# ── config ───────────────────────────────────────────────────


class TestConfig:
    def test_memstack_enabled_reads_skill_config(self, monkeypatch):
        import memstack.config as cfg

        monkeypatch.setattr(
            cfg,
            "_skill_config",
            lambda: {"memstack": {"enabled": True, "inject_top_k": 5}},
        )
        assert cfg.memstack_enabled() is True
        assert cfg.inject_top_k() == 5

    def test_l1_backend_fallback_agent_memory(self, monkeypatch):
        import memstack.config as cfg

        monkeypatch.setattr(
            cfg,
            "_skill_config",
            lambda: {"agent_memory": {"backend": "noop"}},
        )
        assert cfg.l1_backend_name() == "noop"

    def test_kb_backend_default_sqlite(self, monkeypatch):
        import memstack.config as cfg

        monkeypatch.setattr(cfg, "_skill_config", lambda: {})
        assert cfg.kb_backend_name() == "sqlite"


# ── kb ───────────────────────────────────────────────────────


class TestKB:
    def test_sqlite_roundtrip(self, tmp_path):
        from memstack.kb import KB_SCHEME, get_kb_backend

        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store, backend="sqlite")
        ref = kb.write("pro1", "标题", "内容", tags=["research", "ledger"])
        assert ref.startswith(f"{KB_SCHEME}sqlite/")
        got = kb.get(ref)
        assert got["title"] == "标题" and got["content"] == "内容"
        hits = kb.search(tags=["research"], project_id="pro1")
        assert len(hits) == 1
        store.close()

    def test_unknown_backend_raises(self, tmp_path):
        from memstack.kb import get_kb_backend

        store = Store(tmp_path / "s.db")
        with pytest.raises(NotImplementedError, match="未注册"):
            get_kb_backend(store, backend="nonexistent")
        store.close()

    def test_gbrain_without_vendor_degrades_sqlite(self, tmp_path):
        from memstack.kb.gbrain import GbrainKnowledgeBackend

        store = Store(tmp_path / "s.db")
        kb = GbrainKnowledgeBackend(store)
        ref = kb.write("p1", "t", "body", tags=["test"])
        assert ref.startswith("kb://gbrain/")
        assert kb.get(ref.replace("gbrain", "sqlite")) or kb.get(ref)
        store.close()

    def test_register_kb_backend(self, tmp_path):
        from memstack.kb import KB_SCHEME, get_kb_backend, register_kb_backend

        class EchoKB:
            name = "echo"

            def __init__(self, store=None):
                self.store = store

            def write(self, project_id, title, content, *, task_id="", tags=None):
                return f"{KB_SCHEME}echo/1"

            def get(self, ref):
                return {"ref": ref}

            def search(self, *, tags=None, text="", project_id=None):
                return []

        register_kb_backend("echo", EchoKB)
        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store, backend="echo")
        assert kb.write("p", "t", "c").startswith(f"{KB_SCHEME}echo/")
        store.close()

    def test_list_kb_backends_includes_sqlite(self):
        from memstack.kb import list_kb_backends

        assert "sqlite" in list_kb_backends()


# ── l1 ───────────────────────────────────────────────────────


class TestL1:
    def test_inject_memory_hints(self):
        from memstack.l1.protocol import inject_memory_hints

        out = inject_memory_hints("用户问题", "上次讨论要点")
        assert "【记忆召回】" in out
        assert "上次讨论要点" in out

    def test_inject_memory_hints_empty(self):
        from memstack.l1.protocol import inject_memory_hints

        assert inject_memory_hints("msg", "") == "msg"

    def test_native_session_isolation(self):
        from memstack.l1.native import NativeAgentMemory
        from memstack.l1.protocol import memory_scope_dm, memory_scope_group

        p = NativeAgentMemory()
        assert p.session_key(memory_scope_dm("a1")) == "workspace-a1"
        assert p.session_key(memory_scope_group("g1", "a1")) == "group:g1:a1"

    def test_noop_before_turn_empty(self):
        from memstack.l1.noop import NoopAgentMemory
        from memstack.l1.protocol import memory_scope_dm

        assert NoopAgentMemory().before_turn(memory_scope_dm("x"), "hi") == ""

    def test_mem0_degrades_without_vendor(self, tmp_path):
        from common.store.store import Store
        from memstack.l1.mem0 import Mem0AgentMemory
        from memstack.l1.protocol import memory_scope_dm
        from memstack.l1.sqlite import SqliteAgentMemory

        m = Mem0AgentMemory()
        m._fallback = SqliteAgentMemory(Store(tmp_path / "l1.db"))
        assert m.before_turn(memory_scope_dm("a"), "hello") == ""

    def test_registry_native_and_unknown(self):
        from memstack.l1.registry import get_agent_memory_provider

        assert get_agent_memory_provider("native").name == "native"
        with pytest.raises(NotImplementedError):
            get_agent_memory_provider("unknown_l1")


# ── preferences ──────────────────────────────────────────────


class TestPreferences:
    def test_static_missing_user_md(self, monkeypatch, tmp_path):
        from memstack.preferences.static import StaticPreferenceBackend

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        assert StaticPreferenceBackend().format_block("user1") == ""

    def test_static_reads_user_md(self, monkeypatch, tmp_path):
        from memstack.preferences.static import StaticPreferenceBackend

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        user_md = tmp_path / "USER.md"
        user_md.write_text("回复用中文，简洁。", encoding="utf-8")
        block = StaticPreferenceBackend().format_block("any")
        assert "回复用中文" in block

    def test_static_per_user_path(self, monkeypatch, tmp_path):
        from memstack.preferences.static import StaticPreferenceBackend

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        per_user = tmp_path / "users" / "alice" / "USER.md"
        per_user.parent.mkdir(parents=True)
        per_user.write_text("Alice 偏好", encoding="utf-8")
        prefs = StaticPreferenceBackend().get_preferences("alice")
        assert len(prefs) == 1
        assert "Alice 偏好" in prefs[0].value

    def test_mem0_falls_back_static(self, monkeypatch, tmp_path):
        from memstack.preferences.mem0 import Mem0PreferenceBackend

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        (tmp_path / "USER.md").write_text("fallback pref", encoding="utf-8")
        block = Mem0PreferenceBackend().format_block("u")
        assert "fallback pref" in block

    def test_registry_static(self):
        from memstack.preferences.registry import get_preference_backend

        assert get_preference_backend("static").name == "static"


# ── orchestration / experience ───────────────────────────────


class TestOrchestrationExperience:
    def test_promote_ledger_to_kb(self, tmp_path):
        from memstack.orchestration.experience import promote_ledger_to_memory

        store = Store(tmp_path / "s.db")
        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text(
            "task_id: t1\ntask_type: research\nlesson:\n  worked: ok\n",
            encoding="utf-8",
        )
        ref = promote_ledger_to_memory(tmp_path, "proj1", "t1", "research", store)
        assert ref and ref.startswith("kb://")
        store.close()

    def test_promote_skips_stub_ledger(self, tmp_path):
        from memstack.orchestration.experience import promote_ledger_to_memory

        store = Store(tmp_path / "s.db")
        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text("<!-- stub -->", encoding="utf-8")
        assert promote_ledger_to_memory(tmp_path, "p", "t", "research", store) is None
        store.close()

    def test_promote_missing_ledger(self, tmp_path):
        from memstack.orchestration.experience import promote_ledger_to_memory

        store = Store(tmp_path / "s.db")
        assert promote_ledger_to_memory(tmp_path, "p", "t", "research", store) is None
        store.close()

    def test_fetch_experience_project_first(self, tmp_path):
        from memstack.kb import get_kb_backend
        from memstack.orchestration.experience import fetch_experience_entries

        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store)
        kb.write("projA", "a1", "content A", tags=["research", "ledger"])
        kb.write("projB", "b1", "content B", tags=["research", "ledger"])
        entries = fetch_experience_entries("projA", "research", limit=3, store=store)
        assert len(entries) >= 1
        assert entries[0].get("content") == "content A"
        store.close()

    def test_append_experience_hints_injects_block(self, tmp_path):
        from memstack.kb import get_kb_backend
        from memstack.orchestration.experience import append_experience_hints

        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store)
        kb.write("p1", "research:t1", "lesson learned", tags=["research", "ledger"])
        lines: list[str] = []
        append_experience_hints(lines, "p1", "research", store=store)
        text = "\n".join(lines)
        assert "同类任务经验" in text
        assert "lesson learned" in text
        store.close()

    def test_append_experience_empty_no_block(self, tmp_path):
        from memstack.orchestration.experience import append_experience_hints

        store = Store(tmp_path / "s.db")
        lines: list[str] = []
        append_experience_hints(lines, "p1", "unknown-type", store=store)
        assert lines == []
        store.close()


# ── injection ────────────────────────────────────────────────


class TestInjection:
    def test_append_kb_top_k_truncates_long_content(self):
        from memstack.injection.blocks import append_kb_top_k

        long_content = "x" * 300
        lines: list[str] = []
        append_kb_top_k(lines, [{"title": "t", "content": long_content}])
        joined = "\n".join(lines)
        assert "【相关知识】" in joined
        assert "…" in joined
        assert len(joined) < len(long_content)

    def test_append_preference_block(self):
        from memstack.injection.blocks import append_preference_block

        lines: list[str] = []
        append_preference_block(lines, "简洁中文")
        assert "【用户偏好】" in lines
        assert "简洁中文" in lines

    def test_append_block_skips_empty(self):
        from memstack.injection.blocks import append_block

        lines: list[str] = []
        append_block(lines, "title", "  ")
        assert lines == []


# ── anysearch ────────────────────────────────────────────────


class TestAnySearch:
    def test_cli_missing_graceful(self, monkeypatch):
        from memstack.orchestration import anysearch as mod

        monkeypatch.setattr(mod, "anysearch_cli", lambda: None)
        result = mod.search_and_extract("test query")
        assert result["ok"] is False
        assert result["query"] == "test query"


# ── facade（模块能力，不经过 Hub）────────────────────────────


class TestFacadeModule:
    @pytest.fixture()
    def enable_memstack(self, monkeypatch):
        monkeypatch.setattr("memstack.facade.memstack_enabled", lambda default=False: True)
        monkeypatch.setattr("memstack.config.memstack_enabled", lambda default=False: True)
        monkeypatch.setattr("memstack.facade.inject_top_k", lambda default=3: 3)

    @pytest.fixture()
    def disable_memstack(self, monkeypatch):
        monkeypatch.setattr("memstack.facade.memstack_enabled", lambda default=False: False)
        monkeypatch.setattr("memstack.config.memstack_enabled", lambda default=False: False)
        # execution_harness KB 注入也需禁用（memstack facade 委托到 execution_harness）
        monkeypatch.setattr("execution_harness.config.kb_inject_allowed", lambda default=True: False)

    def test_enabled_default_false(self, disable_memstack):
        from memstack.facade import enabled

        assert enabled() is False

    def test_on_chat_turn_injects_preference_when_enabled(
        self, enable_memstack, monkeypatch, tmp_path
    ):
        from memstack.facade import on_chat_turn
        from memstack.l1.protocol import memory_scope_dm
        from memstack.l1.registry import get_agent_memory_provider
        from memstack.orchestration.context import ChatTurnContext

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        (tmp_path / "USER.md").write_text("Always 中文", encoding="utf-8")
        msg = on_chat_turn(
            ChatTurnContext(scope=memory_scope_dm("product"), message="hi", owner_id="product"),
            provider=get_agent_memory_provider("native"),
        )
        assert "Always 中文" in msg

    def test_on_chat_turn_baseline_no_pref_when_disabled(
        self, disable_memstack, monkeypatch, tmp_path
    ):
        from memstack.facade import on_chat_turn
        from memstack.l1.protocol import memory_scope_dm
        from memstack.orchestration.context import ChatTurnContext

        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        (tmp_path / "USER.md").write_text("hidden pref", encoding="utf-8")
        msg = on_chat_turn(
            ChatTurnContext(scope=memory_scope_dm("product"), message="hi", owner_id="product"),
        )
        assert msg == "hi"
        assert "hidden pref" not in msg

    def test_inject_for_execute_baseline_experience(self, disable_memstack, tmp_path):
        from memstack.facade import inject_for_execute
        from memstack.kb import get_kb_backend
        from memstack.orchestration.context import ExecuteInjectContext

        store = Store(tmp_path / "s.db")
        get_kb_backend(store).write("p", "research:t0", "exp", tags=["research", "ledger"])
        lines: list[str] = []
        inject_for_execute(
            ExecuteInjectContext(
                lines=lines, project_id="p", task_type="research", store=store
            )
        )
        assert any("同类任务经验" in ln for ln in lines)
        assert not any("【相关知识】" in ln for ln in lines)
        store.close()

    def test_inject_for_execute_kb_when_enabled(self, enable_memstack, tmp_path):
        from memstack.facade import inject_for_execute
        from memstack.kb import get_kb_backend
        from memstack.orchestration.context import ExecuteInjectContext

        store = Store(tmp_path / "s.db")
        get_kb_backend(store).write(
            "p", "research:note", "KB entry body", tags=["research"]
        )
        lines: list[str] = []
        inject_for_execute(
            ExecuteInjectContext(
                lines=lines,
                project_id="p",
                task_type="research",
                agent_id="product",
                store=store,
            )
        )
        assert any("【相关知识】" in ln for ln in lines)
        assert any("KB entry body" in ln for ln in lines)
        store.close()

    def test_on_task_success_gate_not_passed(self, tmp_path):
        from memstack.facade import on_task_success
        from memstack.orchestration.context import TaskSuccessContext

        store = Store(tmp_path / "s.db")
        base = tmp_path / "d"
        base.mkdir()
        (base / "ledger.entry.yaml").write_text(
            "task_id: t1\nlesson:\n  worked: x\n", encoding="utf-8"
        )
        ref = on_task_success(
            TaskSuccessContext(
                base_dir=base,
                project_id="p",
                task_id="t1",
                task_type="research",
                store=store,
                gate_passed=False,
            )
        )
        assert ref is None
        store.close()

    def test_on_task_success_promotes_ledger(self, tmp_path):
        from memstack.facade import on_task_success
        from memstack.orchestration.context import TaskSuccessContext

        store = Store(tmp_path / "s.db")
        base = tmp_path / "d"
        base.mkdir()
        (base / "ledger.entry.yaml").write_text(
            "task_id: t1\nlesson:\n  worked: promoted\n", encoding="utf-8"
        )
        ref = on_task_success(
            TaskSuccessContext(
                base_dir=base,
                project_id="p",
                task_id="t1",
                task_type="research",
                store=store,
                gate_passed=True,
            )
        )
        assert ref and ref.startswith("kb://")
        store.close()

    def test_on_project_complete_writes_kb(self, enable_memstack, tmp_path):
        from memstack.facade import on_project_complete
        from memstack.kb import get_kb_backend
        from memstack.orchestration.context import ProjectCompleteContext

        store = Store(tmp_path / "s.db")
        store.upsert_task("pro_x", "t1", task_type="research", status="completed")
        ref = on_project_complete(
            ProjectCompleteContext(project_id="pro_x", store=store, status="completed")
        )
        assert ref and ref.startswith("kb://")
        got = get_kb_backend(store).search(tags=["project_review"], project_id="pro_x")
        assert got
        store.close()

    def test_on_project_complete_skipped_when_disabled(self, disable_memstack, tmp_path):
        from memstack.facade import on_project_complete
        from memstack.orchestration.context import ProjectCompleteContext

        store = Store(tmp_path / "s.db")
        ref = on_project_complete(
            ProjectCompleteContext(project_id="pro_x", store=store, status="completed")
        )
        assert ref is None
        store.close()

    def test_on_consensus_writes_kb(self, enable_memstack, monkeypatch, tmp_path):
        from memstack.facade import on_consensus
        from memstack.kb import get_kb_backend
        from memstack.orchestration.context import ConsensusContext

        store = Store(tmp_path / "s.db")
        monkeypatch.setattr(
            "memstack.facade.get_kb_backend",
            lambda s=None: get_kb_backend(store),
        )
        ref = on_consensus(
            ConsensusContext(
                group_id="g1",
                draft_text="最佳实践：先写测试",
                agenda="测试策略",
            )
        )
        assert ref and ref.startswith("kb://")
        hits = get_kb_backend(store).search(tags=["best_practice"])
        assert hits
        store.close()

    def test_facade_degrades_on_kb_error(self, enable_memstack, monkeypatch, tmp_path):
        from memstack.facade import inject_for_execute
        from memstack.orchestration.context import ExecuteInjectContext

        store = Store(tmp_path / "s.db")

        def _boom(*a, **k):
            raise RuntimeError("kb down")

        monkeypatch.setattr("memstack.facade.get_kb_backend", _boom)
        lines: list[str] = []
        inject_for_execute(
            ExecuteInjectContext(
                lines=lines, project_id="p", task_type="research", store=store
            )
        )
        # 不应 raise；baseline experience 仍可能为空
        store.close()

    def test_on_chat_turn_degrades_on_provider_error(self, monkeypatch):
        from memstack.facade import on_chat_turn
        from memstack.l1.protocol import memory_scope_dm
        from memstack.orchestration.context import ChatTurnContext

        class BadProvider:
            name = "bad"

            def session_key(self, scope):
                return "x"

            def before_turn(self, scope, user_text):
                raise RuntimeError("provider down")

            def after_turn(self, scope, user_text, assistant_text):
                pass

            def clear_scope(self, scope):
                pass

        msg = on_chat_turn(
            ChatTurnContext(scope=memory_scope_dm("a"), message="original"),
            provider=BadProvider(),
        )
        assert msg == "original"


# ── E-ARCH：Framework 不 import vendors ─────────────────────


class TestArchitecture:
    def test_framework_modules_no_vendor_import(self):
        root = Path(__file__).resolve().parents[2] / "memstack"
        targets = ["facade.py", "config.py"]
        for sub in ("orchestration", "injection", "kb", "l1", "preferences"):
            targets.extend(str(p.relative_to(root)) for p in (root / sub).glob("*.py"))
        for rel in targets:
            path = root / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            assert "memstack.vendors" not in text, f"{rel} must not import vendors"
            assert "from vendors" not in text, f"{rel} must not import vendors"
