#!/usr/bin/env python3
"""可配置 Prompt 注入（Strategy Registry）。

按 delivery_profile / task_type 读取 prompt_injections.yaml 并渲染。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from common.paths import MYTEAM_ROOT, prompt_injections_file
from common.prompt.prompt_templates import render_template


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def build_injection_variables(**extra: Any) -> dict[str, Any]:
    """标准路径占位符；扩展键由 PromptComposer 传入。"""
    root = MYTEAM_ROOT
    base = {
        "myteam_root": str(root),
        "all_playbook": str(root / "business" / "playbooks" / "ALL.md"),
        "catalog": str(root / "business" / "skills" / "catalog.yaml"),
        "scaffold_process": str(root / "business" / "playbooks" / "scripts" / "scaffold_process.sh"),
        "scaffold_script": str(root / "business" / "playbooks" / "scripts" / "scaffold_light.sh"),
        "diagram_execution": str(root / "business" / "means" / "diagram-build" / "EXECUTION.md"),
        "diagram_probe": str(root / "business" / "means" / "diagram-build" / "scripts" / "probe.sh"),
    }
    base.update(extra)
    return base


def _collect_blocks(raw_blocks: Any) -> list[str]:
    if isinstance(raw_blocks, str) and raw_blocks.strip():
        return [raw_blocks]
    if isinstance(raw_blocks, list):
        return [b for b in raw_blocks if isinstance(b, str) and b.strip()]
    return []


@lru_cache(maxsize=1)
def _load_injections(path_str: str) -> dict:
    raw = _load_yaml(Path(path_str))
    inj = raw.get("injections")
    return inj if isinstance(inj, dict) else {}


def invalidate_injections_cache() -> None:
    _load_injections.cache_clear()


def load_injections(path: Optional[Path] = None) -> dict:
    if path is not None:
        raw = _load_yaml(path)
        inj = raw.get("injections")
        return inj if isinstance(inj, dict) else {}
    return _load_injections(str(prompt_injections_file()))


def iter_injection_blocks(
    kind: str,
    task_type: str,
    *,
    delivery_profile: str = "none",
    path: Optional[Path] = None,
) -> list[str]:
    """按 delivery_profile → task_type 顺序返回待渲染块。"""
    cfg = load_injections(path).get(kind)
    if not isinstance(cfg, dict):
        return []

    profile = (delivery_profile or "none").strip() or "none"
    out: list[str] = []

    by_prof = cfg.get("by_delivery_profile")
    if isinstance(by_prof, dict) and profile != "none":
        prof_cfg = by_prof.get(profile)
        if isinstance(prof_cfg, dict):
            out.extend(_collect_blocks(prof_cfg.get("blocks")))
        elif isinstance(prof_cfg, list):
            out.extend(_collect_blocks(prof_cfg))

    by_tt = cfg.get("by_task_type")
    if isinstance(by_tt, dict) and task_type:
        tt_cfg = by_tt.get(task_type)
        if isinstance(tt_cfg, dict):
            out.extend(_collect_blocks(tt_cfg.get("blocks")))
        elif isinstance(tt_cfg, list):
            out.extend(_collect_blocks(tt_cfg))

    return out


def append_prompt_injections(
    lines: list[str],
    kind: str,
    task_type: str,
    *,
    delivery_profile: str = "none",
    variables: Optional[dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> None:
    """把配置块渲染后追加到 prompt lines。"""
    vars_ = build_injection_variables(**(variables or {}))
    for block in iter_injection_blocks(
        kind, task_type, delivery_profile=delivery_profile, path=path,
    ):
        rendered = render_template(block, vars_).strip()
        if rendered:
            lines.append(rendered)
            lines.append("")
