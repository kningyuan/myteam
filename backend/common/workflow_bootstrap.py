#!/usr/bin/env python3
"""PGD workflow 启动前准备 — 合并角色注册表、创建 workspace、校验能力边界。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from common import paths
from common.agent_bootstrap import auto_create_agent
from common.plan_gate import check_plan
from common.workflow_loader import WorkflowProfile, load_workflow

def _pgd_agents_template_path() -> Path:
    return paths.BUSINESS_DIR / "templates" / "pgd-agents.json"


def _load_pgd_role_boundaries() -> dict[str, str]:
    path = paths.BUSINESS_CONFIG_DIR / "pgd_role_boundaries.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {str(k): str(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _load_pgd_default_models() -> dict[str, tuple[str, str]]:
    path = paths.BUSINESS_CONFIG_DIR / "pgd_default_models.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            out: dict[str, tuple[str, str]] = {}
            for aid, spec in (raw or {}).items():
                if isinstance(spec, dict):
                    out[str(aid)] = (str(spec.get("backend") or ""), str(spec.get("model") or ""))
            return out
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def load_pgd_agent_template() -> dict[str, dict[str, Any]]:
    tpl = _pgd_agents_template_path()
    if not tpl.is_file():
        raise FileNotFoundError(f"缺少 PGD 角色模板：{tpl}")
    raw = json.loads(tpl.read_text(encoding="utf-8"))
    agents = raw.get("agents") or {}
    if not agents:
        raise ValueError("pgd-agents.json 未定义 agents")
    return agents


def _load_registry() -> dict:
    if paths.AGENTS_REGISTRY_FILE.exists():
        try:
            return json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": "1.0", "agents": {}}


def _save_registry(reg: dict) -> None:
    paths.AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_agent_meta(existing: dict, incoming: dict) -> dict:
    """Workflow 启动时合并「执行元数据」，不碰 skills/mcp（仅管理页配置）。

    incoming 来自 PGD 模板或 registry；只 union task_types/capabilities 供 check_plan，
    绝不从 incoming 写入 skills/mcp_servers/boundaries。
    """
    caps = sorted(set(existing.get("capabilities") or []) | set(incoming.get("capabilities") or []))
    tts = sorted(set(existing.get("task_types") or []) | set(incoming.get("task_types") or []))
    merged: dict = {
        "name": incoming.get("name") or existing.get("name") or "",
        "role": incoming.get("role") or existing.get("role") or "worker",
        "description": incoming.get("description") or existing.get("description") or "",
        "capabilities": caps,
        "task_types": tts,
    }
    # skills/mcp/boundaries：workflow 不参与；原样保留 registry 已有配置
    for key in ("skills", "mcp_servers", "boundaries"):
        if key in existing:
            merged[key] = existing[key]
    return merged


def _ensure_agents_config(agent_id: str, meta: dict, *, backend: str, model: str) -> None:
    from common.agent_model import system_default_backend

    cfg: dict = {}
    if paths.AGENTS_CONFIG_FILE.exists():
        try:
            cfg = json.loads(paths.AGENTS_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    entry = cfg.setdefault(agent_id, {})
    entry.setdefault("backend", backend or system_default_backend())
    if model:
        entry.setdefault("model", model)
    else:
        entry.setdefault("model", "")
    entry.setdefault("extra", {})
    entry.setdefault("name", meta.get("name") or agent_id)
    entry.setdefault("workspace", f"business/workspaces/workspace-{agent_id}")
    paths.AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _patch_role_boundary(agent_id: str) -> None:
    extra = _load_pgd_role_boundaries().get(agent_id)
    if not extra:
        return
    ag = paths.workspace_dir(agent_id) / "AGENTS.md"
    if not ag.is_file():
        return
    text = ag.read_text(encoding="utf-8")
    if "## 职责边界（PGD）" not in text:
        ag.write_text(text.rstrip() + "\n\n" + extra, encoding="utf-8")


def ensure_agent(agent_id: str, meta: dict, *, backend: str, model: str) -> None:
    """创建 workspace（若缺失）并合并注册表 task_types。"""
    be, mo = backend, model
    if not model:
        be, mo = _load_pgd_default_models().get(agent_id, (backend, "claude-sonnet-4-6"))

    if not paths.workspace_dir(agent_id).exists():
        auto_create_agent(
            agent_id,
            name=meta.get("name") or agent_id,
            role=meta.get("role") or "worker",
            description=meta.get("description") or f"PGD 角色：{agent_id}",
            backend=be,
            model=mo,
        )

    reg = _load_registry()
    reg.setdefault("agents", {})
    merged = _merge_agent_meta(reg["agents"].get(agent_id) or {}, meta)
    reg["agents"][agent_id] = merged
    _save_registry(reg)
    _ensure_agents_config(agent_id, merged, backend=be, model=mo)
    _patch_role_boundary(agent_id)


def _resolve_agent_meta(agent_id: str, template: dict[str, dict[str, Any]]) -> Optional[dict[str, Any]]:
    """与「管理」Tab 一致：已有 workspace 优先；否则 PGD/注册表元数据（可 bootstrap）。"""
    reg = _load_registry().get("agents") or {}
    has_ws = paths.workspace_dir(agent_id).is_dir()

    if has_ws:
        if agent_id in reg:
            return reg[agent_id]
        if agent_id in template:
            return template[agent_id]
        return {
            "name": agent_id,
            "role": "worker",
            "description": f"Agent：{agent_id}",
            "capabilities": [],
            "task_types": [],
        }
    if agent_id in template:
        return template[agent_id]
    if agent_id in reg:
        return reg[agent_id]
    return None


def ensure_workflow_ready(workflow_id: str, *, backend: str = "claude",
                          default_model: str = "") -> WorkflowProfile:
    """为 workflow 准备 roster：合并 PGD 注册表、创建缺失 workspace、校验 DAG+能力。"""
    profile = load_workflow(workflow_id)
    template = load_pgd_agent_template()

    agent_metas: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for aid in profile.roster:
        meta = _resolve_agent_meta(aid, template)
        if meta is None:
            missing.append(aid)
        else:
            agent_metas[aid] = meta
    if missing:
        raise ValueError(
            f"workflow「{workflow_id}」引用了未就绪的 Agent：{missing}；"
            f"请先在「管理」Tab 创建对应角色（workspace），或检查 agent id 拼写。")

    for aid in profile.roster:
        be, mo = _load_pgd_default_models().get(aid, (backend, default_model or "claude-sonnet-4-6"))
        ensure_agent(aid, agent_metas[aid], backend=be, model=mo)

    tasks = profile.instantiate_tasks()
    result = check_plan(tasks, set(profile.roster), check_capabilities=True)
    if not result.passed:
        raise RuntimeError(
            f"workflow「{workflow_id}」运行时校验失败：{result.feedback}")

    return profile


def list_workflow_summaries() -> list[dict]:
    """供 Hub API：列出可用 workflow 摘要。"""
    from common.hub_operation_meta import attach_operated_at, sort_by_operated_at
    from common.workflow_loader import list_workflows
    out = []
    for wid in list_workflows():
        try:
            p = load_workflow(wid)
            out.append({
                "id": p.id,
                "name": p.name,
                "display_name": p.name,
                "version": p.version,
                "description": p.description,
                "roster": p.roster,
                "phases": p.phases,
                "task_count": len(p.tasks),
                "loop_count": len(p.loops),
                "options": p.options,
            })
        except (OSError, ValueError) as e:
            out.append({"id": wid, "error": str(e)})
    out = attach_operated_at(out, "workflow")
    return sort_by_operated_at(out)
