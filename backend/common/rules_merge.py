"""合并 business/rules 为临时 rules 文件 — Hub 聊天与内核 execute 同源。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Optional

RulesProfile = Literal["interactive", "discussion", "workflow_execute", "conversation"]

_INTERACTIVE_RULE = "interactive-guide.md"
_DISCUSSION_RULE = "brainstorming-guide.md"
_EXECUTE_RULE = "worker-template.md"


def normalize_rules_profile(profile: str) -> str:
    """conversation 为 interactive 的兼容别名。"""
    if profile == "conversation":
        return "interactive"
    return profile


def merge_rules_file(
    agent_id: str,
    workspace: str,
    rules_dir: Path,
    *,
    profile: RulesProfile = "interactive",
    chinese_name: str | None = None,
) -> Optional[str]:
    """按 profile 合并规则。

    interactive: universal + interactive-guide（私聊、群聊 @agent 交互任务；不含 AGENTS 执行段）
    discussion: universal + brainstorming-guide（圆桌 / 纯讨论；不含 AGENTS 执行段）
    workflow_execute: universal + worker-template + AGENTS.md（项目编排 execute）
    conversation: 同 interactive（兼容旧调用）
    """
    profile = normalize_rules_profile(profile)  # type: ignore[assignment]
    universal = rules_dir / "universal-rules.md"
    agents_md = Path(workspace) / "AGENTS.md"
    display = chinese_name or agent_id
    try:
        fd, temp_path = tempfile.mkstemp(
            suffix=".md", prefix=f"rules-{agent_id}-", dir="/tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"# {display} - 完整规则\n\n")
            if universal.exists():
                f.write(universal.read_text(encoding="utf-8"))
                f.write("\n\n---\n\n")
            if profile == "interactive":
                fp = rules_dir / _INTERACTIVE_RULE
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            elif profile == "discussion":
                fp = rules_dir / _DISCUSSION_RULE
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            elif profile == "workflow_execute" and agent_id != "main":
                fp = rules_dir / _EXECUTE_RULE
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
                if agents_md.exists():
                    f.write(agents_md.read_text(encoding="utf-8"))
        return temp_path
    except Exception:
        return None
