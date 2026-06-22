#!/usr/bin/env python3
"""memstack 本地 smoke — 不依赖 Hub，验证开箱可用。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.store import Store
from memstack.facade import after_chat_turn, inject_for_execute, on_chat_turn, on_task_success
from memstack.kb import get_kb_backend
from memstack.l1.protocol import memory_scope_dm
from memstack.l1.sqlite import SqliteAgentMemory
from memstack.orchestration.context import (
    ChatTurnContext,
    ExecuteInjectContext,
    TaskSuccessContext,
)


def main() -> int:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="memstack_smoke_"))
    store = Store(tmp / "state.db")
    scope = memory_scope_dm("product")
    l1 = SqliteAgentMemory(store)

    print("[1] L1 多轮记忆")
    l1.after_turn(scope, "我们主攻 B2B SaaS", "明白，B2B SaaS 方向。")
    hint = l1.before_turn(scope, "下一步策略?")
    assert hint, "L1 before_turn 应非空"
    print("  hint:", hint[:120].replace("\n", " "))

    print("[2] facade 私聊（需 memstack.enabled=true 才有偏好，此处测 L1）")
    after_chat_turn(scope, "竞品有哪些?", "主要竞品 A、B、C。", provider=l1)
    msg = on_chat_turn(
        ChatTurnContext(scope=scope, message="总结一下", owner_id="product"),
        provider=l1,
    )
    assert "总结" in msg
    print("  message ok, len=", len(msg))

    print("[3] KB + execute 注入")
    get_kb_backend(store).write(
        "demo_proj", "research:t0", "ledger: 先用户访谈", tags=["research", "ledger"]
    )
    lines: list[str] = []
    inject_for_execute(
        ExecuteInjectContext(
            lines=lines, project_id="demo_proj", task_type="research", store=store
        )
    )
    blob = "\n".join(lines)
    assert "同类任务经验" in blob
    print("  inject lines:", len(lines))

    print("[4] ledger promote")
    base = tmp / "deliv"
    base.mkdir()
    (base / "ledger.entry.yaml").write_text(
        "lesson:\n  worked: smoke test ok\n", encoding="utf-8"
    )
    ref = on_task_success(
        TaskSuccessContext(
            base_dir=base,
            project_id="demo_proj",
            task_id="t_smoke",
            task_type="research",
            store=store,
            gate_passed=True,
        )
    )
    assert ref
    print("  kb ref:", ref)

    store.close()
    print("\n✅ memstack smoke 全部通过")
    print("   临时目录:", tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
