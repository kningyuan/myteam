#!/usr/bin/env python3
"""交付物保证层 — 工业级框架：先保证「有文件、有结构、能过 Gate」，再谈质量。

1. scaffold：execute 前写入带必需章节的 Markdown 骨架（agent 填内容即可）。
2. adopt：CLI 结束但未 submit_result 时，若交付物文件已有实质内容，代构建合法信封。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from common.delivery.delivery_profiles import get_delivery_profile
from common.paths import MYTEAM_ROOT
from common.project.project_artifacts import artifact_rel_path, is_code_project_task
from common.gate.registry import FormatSpec, is_stub, resolve_format_spec
from common.delivery.submit_result import submit

_PROCESS_TEMPLATES = {
    "align.md": "align.md",
    "plan.md": "plan.md",
    "ledger.entry.yaml": "ledger.entry.yaml",
    "trace.manifest.yaml": "trace.manifest.yaml",
}


def scaffold_process_artifacts(base_dir: Path, delivery_profile: str) -> None:
    """按 delivery_profile 预写过程产物模板（attempt 1；不覆盖已有实质内容）。"""
    prof = get_delivery_profile(delivery_profile)
    if not prof.process_artifacts:
        return
    base_dir.mkdir(parents=True, exist_ok=True)
    tpl_root = MYTEAM_ROOT / "business" / "playbooks" / "templates"
    for art in prof.process_artifacts:
        dst = base_dir / art
        if art == "verify.log":
            if not dst.is_file():
                dst.touch()
            continue
        tpl_name = _PROCESS_TEMPLATES.get(art)
        if not tpl_name:
            continue
        src = tpl_root / tpl_name
        if not src.is_file():
            continue
        if dst.is_file():
            existing = dst.read_text(encoding="utf-8", errors="replace").strip()
            if existing and not is_stub(existing, 20):
                continue
        shutil.copy2(src, dst)


def _heading(level: int, title: str) -> str:
    return f"{'#' * max(1, level)} {title}"


def scaffold_markdown_deliverable(
    path: Path,
    spec: Optional[FormatSpec],
    *,
    title: str,
) -> Path:
    """写入 Markdown 交付物骨架（仅当文件不存在或为空时）。

    任务意图仅通过 execute 提示词（req.intent）下发，不写入交付物文件。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8", errors="replace").strip():
        return path

    lines = [f"# {title.strip() or '交付物'}", ""]
    sections = list(spec.required_sections) if spec else []
    if not sections and spec and spec.sections:
        sections = [
            s.get("name", "") for s in spec.sections
            if isinstance(s, dict) and s.get("required", True) and s.get("name")
        ]
    level = (spec.required_heading_level if spec else 2) or 2
    for name in sections:
        lines += [_heading(level, name), "", ""]
    if not sections:
        lines += [_heading(level, "正文"), "", ""]

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def deliverable_abs_path(
    base_dir: Path,
    rel_path: str,
    task_type: str,
) -> Path:
    if is_code_project_task(task_type):
        return base_dir / rel_path.strip("/")
    p = Path(rel_path)
    if p.is_absolute():
        return p
    return base_dir / rel_path


def deliverable_has_substance(content: str, spec: Optional[FormatSpec]) -> bool:
    """交付物是否超出占位/空骨架（代采纳门槛）。"""
    if is_stub(content, (spec.stub_floor if spec else 20)):
        return False
    floor = (spec.stub_floor if spec else 20) * 8
    return len((content or "").strip()) >= max(floor, 120)


def build_execute_envelope(
    *,
    interaction_id: str,
    task_type: str,
    rel_path: str,
    title: str,
    adopted: bool = False,
) -> dict:
    gaps = ["框架代采纳：agent 未调用 submit_result"] if adopted else []
    return {
        "interaction_id": interaction_id,
        "kind": "execute",
        "status": "ok",
        "quality": {
            "score": 0.5 if adopted else 0.7,
            "known_gaps": gaps,
            "notes": "交付物保证层代构建" if adopted else "",
        },
        "result": {
            "outcome": {
                "kind": "artifact",
                "artifact": {
                    "path": rel_path,
                    "format": "code_project" if rel_path.endswith("/") else "markdown",
                    "title": title,
                },
            }
        },
        "notes": "交付物已从磁盘路径提交" if adopted else "",
        "meta": {"task_type": task_type},
    }


def try_adopt_deliverable_response(
    req,
    resp_path: Path,
    req_mtime: float,
) -> Optional[dict]:
    """execute 交互：磁盘交付物已有实质内容但无 .response 时，代构建并写入合法信封。"""
    if getattr(req, "kind", None) != "execute":
        return None
    if resp_path.exists():
        try:
            if resp_path.stat().st_mtime >= req_mtime:
                return None
        except OSError:
            pass

    inp = req.input or {}
    constraints = req.constraints or {}
    task_type = constraints.get("task_type", "") if isinstance(constraints, dict) else ""
    template_id = str(constraints.get("template_id") or "").strip() or None if isinstance(constraints, dict) else None
    from common.gate.registry import resolve_format_spec
    spec = resolve_format_spec(task_type, template_id) if task_type else None
    rel_path = inp.get("deliverable_path") or artifact_rel_path(req.task_id or "", task_type)
    base = inp.get("deliverable_base")
    if not base:
        return None
    abs_path = deliverable_abs_path(Path(base), rel_path, task_type)
    if is_code_project_task(task_type):
        if not abs_path.is_dir():
            return None
        files = [p for p in abs_path.rglob("*") if p.is_file() and not p.name.startswith(".")]
        if len(files) < 1:
            return None
    else:
        if not abs_path.is_file():
            return None
        content = abs_path.read_text(encoding="utf-8", errors="replace")
        if not deliverable_has_substance(content, spec):
            return None

    title = (req.intent or req.task_id or "交付物")[:80]
    envelope = build_execute_envelope(
        interaction_id=req.interaction_id,
        task_type=task_type,
        rel_path=rel_path,
        title=title,
        adopted=True,
    )
    submit(envelope, resp_path, require_dispatch=False)
    return envelope


def scaffold_for_execute_request(
    req,
    *,
    task_name: str = "",
) -> Optional[Path]:
    """为 execute 请求预写交付物骨架（仅 markdown artifact）。"""
    if getattr(req, "kind", None) != "execute":
        return None
    inp = req.input or {}
    constraints = req.constraints or {}
    task_type = constraints.get("task_type", "") if isinstance(constraints, dict) else ""
    template_id = str(constraints.get("template_id") or "").strip() or None if isinstance(constraints, dict) else None
    if is_code_project_task(task_type):
        proj = deliverable_abs_path(
            Path(inp.get("deliverable_base") or "."),
            inp.get("deliverable_path") or f"{req.task_id}/",
            task_type,
        )
        proj.mkdir(parents=True, exist_ok=True)
        return proj
    rel = inp.get("deliverable_path") or artifact_rel_path(req.task_id or "", task_type)
    base = inp.get("deliverable_base")
    if not base:
        return None
    abs_path = deliverable_abs_path(Path(base), rel, task_type)
    spec = resolve_format_spec(task_type, template_id) if task_type else None
    return scaffold_markdown_deliverable(
        abs_path, spec, title=task_name or req.task_id or "交付物",
    )
