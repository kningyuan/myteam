"""Agent Skill 解析 — 严格模式：仅 registry 显式配置的 Skill 生效。

- ``task_types`` = 可接哪些交付物（workflow 派工 / Gate）
- ``skills`` = Agent 允许使用的 Skill id 或 Skill 组 id（私聊 / 群聊 / 圆桌 / execute 统一注入）
- 组 id（如 ``officecli``）展开为上游 vendor skills/ 下全部子 skill 同步到 CLI；也可只挂组内单个 skill
- 无默认兜底、无 task_type 隐式追加；未配置则 Agent 不挂载任何 Skill
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from common.agent.agent_registry import get_agent_info
from common.paths import MYTEAM_ROOT, workspace_dir
from common.skill.skill_catalog import get_skill_library_entry
from common.skill.skill_groups import expand_skill_mounts, get_skill_group, is_skill_group

SKILLS_DIR = MYTEAM_ROOT / "business" / "skills"

_SKILLS_MD_HEADER = "## 已挂载 Skill"
_SKILLS_MD_SECTION_RE = re.compile(
    rf"^{re.escape(_SKILLS_MD_HEADER)}\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def skill_file_path(skill_id: str) -> Optional[Path]:
    entry = get_skill_library_entry(skill_id)
    if not entry:
        return None
    p = MYTEAM_ROOT / entry["path"]
    return p if p.is_file() else None


def get_agent_skill_ids(agent_id: str) -> list[str]:
    """registry 中配置的 skill / 组 id（未展开）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return []
    info = get_agent_info(aid) or {}
    configured = info.get("skills")
    if not isinstance(configured, list):
        return []
    return _dedupe([str(s).strip() for s in configured if str(s).strip()])


def get_agent_mounted_skill_ids(agent_id: str) -> list[str]:
    """展开组后的叶子 skill id（CLI 同步、路径解析用）。"""
    return expand_skill_mounts(get_agent_skill_ids(agent_id))


def resolve_skill_ids(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> list[str]:
    """严格：registry 配置展开为叶子 skill；task_type 不参与解析。"""
    _ = task_type
    return list(get_agent_mounted_skill_ids(agent_id))


def resolve_skill_paths(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> list[Path]:
    paths: list[Path] = []
    for sid in resolve_skill_ids(agent_id, task_type=task_type):
        p = skill_file_path(sid)
        if p is not None:
            paths.append(p)
    return paths


def _append_leaf_skill_lines(
    lines: list[str],
    sid: str,
    ws: Path,
    *,
    prefix: str = "- ",
    indent: str = "",
) -> None:
    entry = get_skill_library_entry(sid) or {}
    name = (entry.get("name") or sid).strip()
    desc = (entry.get("description") or "").strip()
    p = skill_file_path(sid)
    head = f"{prefix}{indent}{sid}（{name}）"
    if desc:
        head += f"：{desc}"
    else:
        head += "（无简介；执行前须 Read SKILL.md）"
    lines.append(head)
    if p:
        oc = ws / ".opencode" / "skills" / sid / "SKILL.md"
        cc = ws / ".claude" / "skills" / sid / "SKILL.md"
        lines.append(f"{indent}    SKILL.md：{p}")
        lines.append(f"{indent}    OpenCode：{oc}")
        lines.append(f"{indent}    Claude Code：{cc}")
    else:
        lines.append(f"{indent}    （文件缺失）")


def build_skill_context(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> str:
    """拼入 system / worker prompt 的 Skill 块。"""
    _ = task_type
    configured = get_agent_skill_ids(agent_id)
    if not configured:
        return (
            "【Skill 边界】本 Agent 未挂载任何 Skill。"
            "禁止查阅或沿用 business/skills 下其他目录中的 SKILL.md。"
        )

    mounted = get_agent_mounted_skill_ids(agent_id)
    missing = [sid for sid in mounted if skill_file_path(sid) is None]

    lines: list[str] = [
        "【已挂载 Skill】仅允许使用下列 Skill（禁止查阅未列出的其他 skill 目录）：",
        "",
        "【简介来源】各行「：」后为选型用短简介，来自 SKILL.md frontmatter 的 description，"
        "或 myteam 为 vendor skill 配置的中文摘要；**不含**具体操作步骤。",
        "【用法】执行前必须用 Read 工具读取对应 SKILL.md **全文**（见下列路径），"
        "按文中命令、脚本与红线操作；禁止仅凭简介或训练数据臆造流程。",
        "",
    ]
    ws = workspace_dir(agent_id)
    for sid in configured:
        if is_skill_group(sid):
            g = get_skill_group(sid) or {}
            gname = g.get("name_zh") or g.get("name") or sid
            gdesc = (g.get("description") or "").strip()
            lines.append(f"- 【Skill 组】{sid}（{gname}）" + (f"：{gdesc}" if gdesc else ""))
            root = g.get("vendor_skills_root") or ""
            if root:
                lines.append(f"    上游目录：{root}")
            lines.append(f"    组内 {len(g.get('members') or [])} 个子 skill（已同步到工作区，按需自选）：")
            for mid in g.get("members") or []:
                _append_leaf_skill_lines(lines, mid, ws, prefix="", indent="    ")
            lines.append("")
        else:
            _append_leaf_skill_lines(lines, sid, ws)
    if missing:
        lines.append(f"（配置中存在但文件缺失：{', '.join(missing)}）")
    lines.extend(
        [
            "",
            "【Skill 自选纪律 — execute 必守】",
            "1. 根据本任务 intent、交付物类型（docx/pptx/drawio 等）与 Goal，从「已挂载 Skill」中选定 0..n 个适用项"
            "（挂 officecli 组时可在组内选子 skill，如 officecli-pptx）。",
            "2. 在 plan.md 的 chosen_skills 节写明：skill id + 选用理由（一句）。无 plan.md 时写在 deliverable「章节对象」首段。",
            "3. 对每个选中的 skill：须 Read 其 SKILL.md（上表路径），按其中步骤与红线执行；禁止跳过直接凭训练数据手写。",
            "4. 产出 Office 文件（.docx/.pptx）时优先 officecli 或 skill 内指定脚本；禁止自建未在 skill 中允许的 python-pptx/python-docx 流程替代。",
            "5. submit_result.metadata 建议含 chosen_skills 数组，便于审计。",
            "",
            "禁止把 ~/.claude/skills 或全局 skill 当作本 Agent 可用 skill。",
        ]
    )
    return "\n".join(lines)


def append_skill_instructions(
    lines: list[str],
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> None:
    block = build_skill_context(agent_id, task_type=task_type)
    if block:
        lines.append(block)


def _normalize_agents_md_after_strip(text: str) -> str:
    """去掉多余空行，保持文件末尾单个换行。"""
    import re as _re

    cleaned = _re.sub(r"\n{3,}", "\n\n", text.strip())
    return cleaned + "\n" if cleaned else ""


def strip_agents_md_skills_section(agent_id: str) -> bool:
    """从 workspace AGENTS.md 移除历史自动同步的「已挂载 Skill」节（幂等）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return False
    agents_md = workspace_dir(aid) / "AGENTS.md"
    if not agents_md.is_file():
        return False
    text = agents_md.read_text(encoding="utf-8")
    if not _SKILLS_MD_SECTION_RE.search(text):
        return False
    text = _SKILLS_MD_SECTION_RE.sub("", text)
    agents_md.write_text(_normalize_agents_md_after_strip(text), encoding="utf-8")
    return True


def _dedupe(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sid in ids:
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out
