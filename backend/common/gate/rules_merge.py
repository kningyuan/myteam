"""合并 business/rules 为临时 rules 文件 — Hub 聊天与内核 execute 同源。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Optional

from config_store.system_config import system_config
from common.coordinator import get_coordinator_id

RulesProfile = Literal["interactive", "discussion", "workflow_execute", "conversation"]

# 默认值（仅当 system_config 中无配置时作为回退）
_DEFAULT_RULE_FILES: dict[str, str] = {
    "interactive": "interactive-guide.md",
    "discussion": "brainstorming-guide.md",
    "workflow_execute": "worker-template.md",
    "ethos": "ethos.md",
}


def _get_rule_filename(key: str) -> str:
    """从 system_config 读取规则文件名，找不到则使用硬编码默认值。"""
    return system_config.get(
        "system", "rules", "profile_filenames", key,
        default=_DEFAULT_RULE_FILES[key],
    )


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

    所有 profile：universal + ethos（团队哲学，全员默认）
    interactive: + interactive-guide（私聊、群聊 @agent；不含 AGENTS 执行段）
    discussion: + brainstorming-guide（圆桌 / 纯讨论；不含 AGENTS 执行段）
    workflow_execute: + worker-template（项目编排 execute；能力来自 agents_registry + IDENTITY）
    conversation: 同 interactive（兼容旧调用）
    """
    profile = normalize_rules_profile(profile)  # type: ignore[assignment]
    universal = rules_dir / "universal-rules.md"
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
            ethos = rules_dir / _get_rule_filename("ethos")
            if ethos.exists():
                f.write(ethos.read_text(encoding="utf-8"))
                f.write("\n\n---\n\n")
            if profile == "interactive":
                fp = rules_dir / _get_rule_filename("interactive")
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            elif profile == "discussion":
                fp = rules_dir / _get_rule_filename("discussion")
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            elif profile == "workflow_execute" and agent_id != get_coordinator_id():
                fp = rules_dir / _get_rule_filename("workflow_execute")
                if fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
        return temp_path
    except Exception:
        return None
