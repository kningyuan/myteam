"""Agent MCP 解析 — 严格模式：仅 registry 显式配置 + 全局 enabled 的 MCP 生效。"""

from __future__ import annotations

import re
from pathlib import Path

from common.agent_registry import get_agent_info
from common.mcp_catalog import get_mcp_server, validate_mcp_ids
from common.paths import workspace_dir

_MCP_MD_HEADER = "## 已挂载 MCP"
_MCP_MD_SECTION_RE = re.compile(
    rf"^{re.escape(_MCP_MD_HEADER)}\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def get_agent_mcp_ids(agent_id: str) -> list[str]:
    aid = (agent_id or "").strip()
    if not aid:
        return []
    info = get_agent_info(aid) or {}
    configured = info.get("mcp_servers")
    if not isinstance(configured, list):
        return []
    valid, _ = validate_mcp_ids([str(s).strip() for s in configured if str(s).strip()])
    return valid


def build_mcp_context(agent_id: str) -> str:
    ids = get_agent_mcp_ids(agent_id)
    if not ids:
        return ""

    lines = [
        "【MCP 工具边界】",
        "以下 MCP Server 已挂载到当前 Agent（经 Hub 同步至其 CLI 后端），可使用其提供的 tools：",
        "",
    ]
    for sid in ids:
        entry = get_mcp_server(sid) or {}
        name = entry.get("name") or sid
        desc = (entry.get("description") or "").strip()
        stype = entry.get("type") or "local"
        lines.append(f"- {sid}（{name}，{stype}）" + (f"：{desc}" if desc else ""))
    lines.extend(
        [
            "",
            "未在上表中的 MCP 不可用。若需新能力，请在 Hub「MCP」页启用并在 Agent 配置中勾选。",
        ]
    )
    return "\n".join(lines)


def append_mcp_instructions(lines: list[str], agent_id: str) -> None:
    block = build_mcp_context(agent_id)
    if block:
        lines.append(block)


def _normalize_agents_md_after_strip(text: str) -> str:
    import re as _re

    cleaned = _re.sub(r"\n{3,}", "\n\n", text.strip())
    return cleaned + "\n" if cleaned else ""


def strip_agents_md_mcp_section(agent_id: str) -> bool:
    """从 workspace AGENTS.md 移除历史自动同步的「已挂载 MCP」节（幂等）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return False
    fp = Path(workspace_dir(aid)) / "AGENTS.md"
    if not fp.is_file():
        return False
    text = fp.read_text(encoding="utf-8")
    if not _MCP_MD_SECTION_RE.search(text):
        return False
    text = _MCP_MD_SECTION_RE.sub("", text)
    fp.write_text(_normalize_agents_md_after_strip(text), encoding="utf-8")
    return True
