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

_DEFAULT_BACKEND = {
    "main": ("claude", "claude-haiku-4-5"),
    "product": ("claude", "claude-sonnet-4-6"),
    "arch": ("claude", "claude-sonnet-4-6"),
    "frontend": ("claude", "claude-sonnet-4-6"),
    "qa": ("claude", "claude-sonnet-4-6"),
    "research": ("claude", "claude-sonnet-4-6"),
    "content": ("claude", "claude-sonnet-4-6"),
    "analyst": ("claude", "claude-sonnet-4-6"),
    "geo": ("claude", "claude-sonnet-4-6"),
    "seo": ("claude", "claude-sonnet-4-6"),
}

_ROLE_BOUNDARIES: dict[str, str] = {
    "main": """## 职责边界（PGD）
- 阶段仲裁：decision-record、发布决策；不编写业务代码与长篇需求正文。
- 部署记录：code-deployment 仅记录步骤与验证，不替代研发实现。
""",
    "product": """## 职责边界（PGD）
- 需求与策略：requirements、strategy、acceptance-report。
- 评审反馈由专责角色产出；产品负责定稿与验收，不替代架构/测试评审。
""",
    "arch": """## 职责边界（PGD）
- 后端/内核：system-design、code-writing、architecture-review、code-review。
- 遵守 adapter 隔离；不修改 hub 服务层 subprocess 逻辑于错误层级。
""",
    "frontend": """## 职责边界（PGD）
- 前端/UI：system-design、code-writing、architecture-review。
- 不引用 CLI 私有字段；只消费统一 SSE/API 契约。
""",
    "qa": """## 职责边界（PGD）
- 测试：test-plan、code-testing、architecture-review、code-review。
- 不编写业务功能代码；阻塞项须在评审中明确分级（🔴/🟡）。
""",
    "research": """## 职责边界（PGD）
- 调研：research；可评策略/调研类 architecture-review。
""",
    "content": """## 职责边界（PGD）
- 内容：content、publish-post；可评内容策略 architecture-review。
""",
    "analyst": """## 职责边界
- 数据分析：data-analysis；可产出 code-writing 分析脚本。
- 不替代产品定需求、不主责业务功能开发。
""",
    "geo": """## 职责边界
- GEO：geo-plan、geo-audit、geo-verification；可指导 content 改稿。
- 传统 SEO 用 seo-plan 归 seo 角色；不混淆。
""",
    "seo": """## 职责边界
- SEO：seo-plan、关键词与传统搜索策略；GEO 专项归 geo。
""",
}


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
    caps = sorted(set(existing.get("capabilities") or []) | set(incoming.get("capabilities") or []))
    tts = sorted(set(existing.get("task_types") or []) | set(incoming.get("task_types") or []))
    return {
        "name": incoming.get("name") or existing.get("name") or "",
        "role": incoming.get("role") or existing.get("role") or "worker",
        "description": incoming.get("description") or existing.get("description") or "",
        "capabilities": caps,
        "task_types": tts,
    }


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
    extra = _ROLE_BOUNDARIES.get(agent_id)
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
        be, mo = _DEFAULT_BACKEND.get(agent_id, (backend, "claude-sonnet-4-6"))

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
        be, mo = _DEFAULT_BACKEND.get(aid, (backend, default_model or "claude-sonnet-4-6"))
        ensure_agent(aid, agent_metas[aid], backend=be, model=mo)

    tasks = profile.instantiate_tasks()
    result = check_plan(tasks, set(profile.roster), check_capabilities=True)
    if not result.passed:
        raise RuntimeError(
            f"workflow「{workflow_id}」运行时校验失败：{result.feedback}")

    return profile


def list_workflow_summaries() -> list[dict]:
    """供 Hub API：列出可用 workflow 摘要。"""
    from common.workflow_loader import list_workflows
    out = []
    for wid in list_workflows():
        try:
            p = load_workflow(wid)
            out.append({
                "id": p.id,
                "version": p.version,
                "description": p.description,
                "roster": p.roster,
                "phases": p.phases,
                "task_count": len(p.tasks),
                "options": p.options,
            })
        except (OSError, ValueError) as e:
            out.append({"id": wid, "error": str(e)})
    return out
