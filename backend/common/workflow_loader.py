#!/usr/bin/env python3
"""Workflow profile 加载与实例化 — PGD 阶段闸门 DAG 种子。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from common.agent_id_policy import normalize_agent_ids, normalize_plan_tasks
from common.loop_runtime import LoopSpec, parse_loop_specs, validate_loop_specs
from common.paths import BUSINESS_DIR
from common.plan_gate import check_plan


@dataclass
class WorkflowProfile:
    id: str
    version: str
    description: str
    roster: list[str]
    tasks: list[dict]
    options: dict[str, Any] = field(default_factory=dict)
    phases: list[dict] = field(default_factory=list)
    loops: list[LoopSpec] = field(default_factory=list)

    def instantiate_tasks(self, *, goal: str = "") -> list[dict]:
        """复制 task 列表，将 goal 注入 description。"""
        prefix = f"【项目目标】{goal.strip()}\n\n" if goal.strip() else ""
        out: list[dict] = []
        for t in self.tasks:
            item = {k: v for k, v in t.items() if k != "phase"}
            desc = item.get("description", "")
            if prefix and desc:
                item["description"] = prefix + desc
            elif prefix:
                item["description"] = prefix.rstrip()
            out.append(item)
        return out


def workflows_dir() -> Path:
    return BUSINESS_DIR / "workflows"


def roster_from_tasks(tasks: list[dict], loops: Optional[list[LoopSpec]] = None) -> list[str]:
    """从任务 DAG 推导团队名册：各步 agent 去重；无 main 时前置 main（协调者）。"""
    roster: list[str] = []
    for t in tasks:
        aid = str(t.get("agent") or "").strip()
        if aid and aid not in roster:
            roster.append(aid)
    for spec in loops or []:
        for t in spec.body:
            aid = str(t.get("agent") or "").strip()
            if aid and aid not in roster:
                roster.append(aid)
    if "main" not in roster:
        roster.insert(0, "main")
    return roster


def list_workflows() -> list[str]:
    d = workflows_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_workflow(workflow_id: str, *, path: Optional[Path] = None) -> WorkflowProfile:
    """按 id（文件名不含扩展名）或绝对路径加载 workflow。"""
    if path is not None:
        fp = path
    else:
        fp = workflows_dir() / f"{workflow_id}.yaml"
        if not fp.is_file():
            available = ", ".join(list_workflows()) or "（无）"
            raise FileNotFoundError(
                f"未找到 workflow「{workflow_id}」（{fp}）。可用：{available}")

    raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"workflow 格式无效：{fp}")

    wid = raw.get("id") or workflow_id
    tasks = normalize_plan_tasks(raw.get("tasks") or [])
    if not tasks:
        raise ValueError(f"workflow「{wid}」未定义 tasks")
    loops = parse_loop_specs(raw.get("loops"))
    roster = normalize_agent_ids(roster_from_tasks(tasks, loops))

    profile = WorkflowProfile(
        id=wid,
        version=str(raw.get("version", "1.0")),
        description=str(raw.get("description", "")).strip(),
        roster=roster,
        tasks=tasks,
        options=dict(raw.get("options") or {}),
        phases=list(raw.get("phases") or []),
        loops=parse_loop_specs(raw.get("loops")),
    )
    validate_workflow(profile)
    return profile


def _pgd_bootstrap_agent_ids() -> set[str]:
    tpl = BUSINESS_DIR / "templates" / "pgd-agents.json"
    if not tpl.is_file():
        return set()
    try:
        raw = json.loads(tpl.read_text(encoding="utf-8"))
        return set((raw.get("agents") or {}).keys())
    except (OSError, json.JSONDecodeError):
        return set()


def _validate_template_refs(tasks: list[dict], loops: Optional[list[LoopSpec]] = None) -> None:
    from common.delivery_templates import DeliveryTemplateError, load_delivery_template

    seen: set[str] = set()
    for t in tasks:
        tid = str(t.get("template_id") or "").strip()
        if tid and tid not in seen:
            seen.add(tid)
            try:
                load_delivery_template(tid)
            except DeliveryTemplateError as e:
                raise ValueError(str(e)) from e
    for spec in loops or []:
        for t in spec.body:
            tid = str(t.get("template_id") or "").strip()
            if tid and tid not in seen:
                seen.add(tid)
                try:
                    load_delivery_template(tid)
                except DeliveryTemplateError as e:
                    raise ValueError(str(e)) from e


def validate_workflow(profile: WorkflowProfile) -> None:
    """校验 DAG、agent 可用性、task_type 注册与 agent 能力绑定。"""
    from common.agent_registry import agent_task_type_map, list_available_agent_ids
    from common.registry import get_spec

    team = set(profile.roster)
    instantiated = profile.instantiate_tasks()

    available = set(list_available_agent_ids())
    boot = _pgd_bootstrap_agent_ids()
    used_agents = set()
    for t in profile.tasks:
        aid = str(t.get("agent") or "").strip()
        if aid:
            used_agents.add(aid)
    for spec in profile.loops:
        for t in spec.body:
            aid = str(t.get("agent") or "").strip()
            if aid:
                used_agents.add(aid)
    missing_agents = sorted(a for a in used_agents if a not in available and a not in boot)
    if missing_agents:
        raise ValueError(
            f"workflow「{profile.id}」引用了「管理」中不存在的 Agent：{', '.join(missing_agents)}；"
            f"请先在管理 Tab 创建对应角色。")

    cap_map = agent_task_type_map()
    bind_errors: list[str] = []
    for t in profile.tasks:
        if t.get("loop"):
            continue
        tt = str(t.get("task_type") or "").strip()
        aid = str(t.get("agent") or "").strip()
        if tt and get_spec(tt) is None:
            bind_errors.append(f"未知 task_type「{tt}」")
        allowed = cap_map.get(aid) or []
        if allowed and tt and tt not in allowed:
            bind_errors.append(
                f"{aid} 未配置 task_type「{tt}」（请在管理 Tab → Agent 配置中勾选）")
    if bind_errors:
        raise ValueError(
            f"workflow「{profile.id}」任务绑定无效：\n- " + "\n- ".join(sorted(bind_errors)))

    plan_tasks = instantiated
    if plan_tasks:
        result = check_plan(plan_tasks, team, check_capabilities=True)
        if not result.passed:
            raise ValueError(f"workflow「{profile.id}」校验失败：{result.feedback}")

    if profile.loops:
        validate_loop_specs(profile.loops, profile.tasks, team)
        if profile.options.get("review_enabled"):
            logging.warning(
                "workflow「%s」同时启用 loops 与 review_enabled，建议 loop body 内显式 review 步",
                profile.id,
            )

    _validate_template_refs(profile.tasks, profile.loops)


def read_workflow_raw(workflow_id: str) -> dict:
    """读取 workflow YAML 为 dict（供 Hub 编辑）。"""
    fp = workflows_dir() / f"{workflow_id}.yaml"
    if not fp.is_file():
        raise FileNotFoundError(f"未找到 workflow「{workflow_id}」")
    raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"workflow 格式无效：{fp}")
    return raw


def write_workflow_raw(data: dict, *, workflow_id: Optional[str] = None) -> str:
    """校验并写入 workflow YAML，返回 workflow id。"""
    if not isinstance(data, dict):
        raise ValueError("workflow 必须是对象")
    wid = (data.get("id") or workflow_id or "").strip()
    if not wid:
        raise ValueError("workflow 缺少 id")
    if "/" in wid or ".." in wid or wid.startswith("."):
        raise ValueError("workflow id 非法")
    data = dict(data)
    data["id"] = wid
    tasks = list(data.get("tasks") or [])
    loops = parse_loop_specs(data.get("loops"))
    roster = roster_from_tasks(tasks, loops)
    profile = WorkflowProfile(
        id=wid,
        version=str(data.get("version", "1.0")),
        description=str(data.get("description", "")).strip(),
        roster=roster,
        tasks=tasks,
        options=dict(data.get("options") or {}),
        phases=list(data.get("phases") or []),
        loops=parse_loop_specs(data.get("loops")),
    )
    validate_workflow(profile)

    # roster 由 tasks 推导，不再写入 YAML（避免与任务表重复配置）
    data.pop("roster", None)

    d = workflows_dir()
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"{wid}.yaml"
    fp.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    try:
        from common.store import Store
        Store().save_workflow_version(wid, data)
    except Exception:
        pass
    return wid


def delete_workflow(workflow_id: str) -> None:
    fp = workflows_dir() / f"{workflow_id}.yaml"
    if not fp.is_file():
        raise FileNotFoundError(f"未找到 workflow「{workflow_id}」")
    fp.unlink()
