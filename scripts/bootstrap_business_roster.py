#!/usr/bin/env python3
"""将 business/templates/business-roster.json 合并进 agents_registry，并创建缺失 workspace。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MYTEAM_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from common import paths  # noqa: E402
from common.agent_bootstrap import auto_create_agent  # noqa: E402
from common.agent_id_policy import invalidate_agent_id_policy_cache  # noqa: E402
from common.registry import invalidate_registry_cache  # noqa: E402


def _load_roster() -> dict:
    fp = paths.BUSINESS_DIR / "templates" / "business-roster.json"
    raw = json.loads(fp.read_text(encoding="utf-8"))
    return raw.get("agents") or {}


def _load_registry() -> dict:
    if paths.AGENTS_REGISTRY_FILE.is_file():
        try:
            return json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": "2.0", "agents": {}}


def _merge_agent_meta(existing: dict, incoming: dict) -> dict:
    merged = {
        "name": incoming.get("name") or existing.get("name", ""),
        "role": incoming.get("role") or existing.get("role", "worker"),
        "description": incoming.get("description") or existing.get("description", ""),
        "capabilities": incoming.get("capabilities") or existing.get("capabilities") or [],
        "task_types": sorted(
            set(existing.get("task_types") or []) | set(incoming.get("task_types") or [])
        ),
    }
    if incoming.get("boundaries"):
        merged["boundaries"] = incoming["boundaries"]
    return merged


def _sync_persona_files(agent_id: str, meta: dict) -> None:
    """将名册中的职责与边界写入 workspace 身份文件（幂等覆盖 AGENTS.md）。"""
    ws = paths.workspace_dir(agent_id)
    if not ws.is_dir():
        return

    name = meta.get("name") or agent_id
    desc = meta.get("description") or ""
    caps = meta.get("capabilities") or []
    tts = meta.get("task_types") or []
    bounds = meta.get("boundaries") or {}
    does = bounds.get("does") or []
    does_not = bounds.get("does_not") or []

    identity = ws / "IDENTITY.md"
    if identity.is_file():
        identity.write_text(
            f"# Agent Identity\n\n"
            f"emoji: 🤖\n"
            f"name: {name}\n"
            f"role: {meta.get('role', 'worker')}\n"
            f"description: {desc}\n",
            encoding="utf-8",
        )

    cap_lines = "\n".join(f"- {c}" for c in caps) or "- （见 description）"
    tt_lines = "\n".join(f"- `{t}`" for t in tts) or "- research"
    does_lines = "\n".join(f"- {x}" for x in does) or "- 见 task_types 契约"
    not_lines = "\n".join(f"- {x}" for x in does_not) or "- 越界任务应拒绝并上报"

    agents_md = f"""# {name} - Agent 配置

## 核心定位
{desc}

## 能力标签
{cap_lines}

## 可执行任务类型（硬边界）
{tt_lines}

## 职责边界
### 做什么
{does_lines}

### 不做什么
{not_lines}

## 工作流程
1. 接收内核下发的 execute 任务
2. 按 task_type 对应的 deliverable_template 完成交付物
3. 写入指定路径后 submit_result

## 协作方式
- 编排任务由 Process 调度 DAG，不与其他 Agent 直接互读 .trigger
- 交卷用 submit_result 写 .response/{{interaction_id}}.response
"""
    (ws / "AGENTS.md").write_text(agents_md.strip() + "\n", encoding="utf-8")

    soul = f"""# {name} - 行为准则

## 核心原则
1. **守边界**：只接 task_types 允许的任务，越界一律拒绝
2. **可验收**：交付物须满足 Gate 章节与长度要求
3. **可协作**：引用上游交付物时注明 task_id，不臆造结论
4. **可追踪**：代码/发布/分析须留痕（路径、URL、截图）

## 角色专责
{desc}
"""
    (ws / "SOUL.md").write_text(soul.strip() + "\n", encoding="utf-8")


def main() -> int:
    roster = _load_roster()
    reg = _load_registry()
    reg.setdefault("agents", {})

    created_ws: list[str] = []
    updated: list[str] = []

    for aid, meta in roster.items():
        ws = paths.workspace_dir(aid)
        if not ws.is_dir():
            auto_create_agent(
                aid,
                name=meta.get("name") or aid,
                role=meta.get("role") or "worker",
                description=meta.get("description") or "",
            )
            created_ws.append(aid)
        merged = _merge_agent_meta(reg["agents"].get(aid) or {}, meta)
        reg["agents"][aid] = merged
        _sync_persona_files(aid, merged)
        updated.append(aid)

    paths.AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cfg_path = paths.AGENTS_CONFIG_FILE
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = {}
    for aid, meta in roster.items():
        if paths.workspace_dir(aid).is_dir():
            entry = dict(cfg.get(aid) or {})
            entry.setdefault("backend", "opencode")
            entry.setdefault("model", "")
            entry.setdefault("extra", {})
            entry["name"] = meta.get("name") or entry.get("name") or aid
            cfg[aid] = entry
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    invalidate_registry_cache()
    invalidate_agent_id_policy_cache()

    print(f"✓ 已合并 {len(updated)} 个 Agent 到 {paths.AGENTS_REGISTRY_FILE}")
    if created_ws:
        print(f"✓ 新建 workspace: {', '.join(created_ws)}")
    else:
        print("  （workspace 均已存在，已同步 AGENTS.md / SOUL.md）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
