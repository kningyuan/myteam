"""合并 business/rules 为临时 rules 文件 — Hub 聊天与内核 execute 同源。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Optional

RulesProfile = Literal["conversation", "workflow_execute"]

_CONVERSATION_RULE = "brainstorming-guide.md"
_EXECUTE_RULE = "worker-template.md"


def merge_rules_file(
    agent_id: str,
    workspace: str,
    rules_dir: Path,
    *,
    profile: RulesProfile = "conversation",
    chinese_name: str | None = None,
) -> Optional[str]:
    """按 profile 合并规则。

    conversation: universal + brainstorming-guide + AGENTS.md（私聊、群组讨论、圆桌）
    workflow_execute: universal + worker-template + AGENTS.md（项目任务 execute，非 main）
    """
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
            if profile == "conversation":
                fp = rules_dir / _CONVERSATION_RULE
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
