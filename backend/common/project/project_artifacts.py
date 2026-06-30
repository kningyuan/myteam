"""项目交付物解析 — 代码类任务在项目 deliverables/<task_id>/ 落成代码工程。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.paths import deliverables_dir, workspace_dir

# 交付物 = 项目内代码工程目录（非单篇 Markdown）
CODE_PROJECT_TASK_TYPES = frozenset({"code-deliverable", "code-writing", "code-testing"})

# P0 边界澄清特性开关：用 outcome_kind 替代硬编码列表（之后会废弃 CODE_PROJECT_TASK_TYPES）
try:
    from config_store.system_config import system_config
    USE_OUTCOME_KIND = bool(system_config.get("system", "use_outcome_kind_detection", default=False)) or False
except Exception:
    USE_OUTCOME_KIND = False


def is_code_project_task(task_type: str) -> bool:
    if USE_OUTCOME_KIND:
        try:
            from common.gate.registry import get_spec
            spec = get_spec(task_type)
            if spec is not None:
                return spec.outcome_kind == "code_project"
        except Exception:
            pass
    return task_type in CODE_PROJECT_TASK_TYPES


_SKIP_DIRS = frozenset({".git", "__pycache__", ".trigger", ".response"})
try:
    from config_store.system_config import system_config
    _CODE_EXTS = frozenset(system_config.get("system", "code_extensions",
        default=[".py", ".sh", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h", ".c", ".rb", ".php", ".swift"]))
except Exception:
    _CODE_EXTS = frozenset({".py", ".sh", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h", ".c", ".rb", ".php", ".swift"})


def task_project_dir(project_id: str, task_id: str) -> Path:
    d = deliverables_dir(project_id) / task_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def task_deliverable_base(project_id: str, task_id: str, task_type: str) -> Path:
    if is_code_project_task(task_type):
        return deliverables_dir(project_id)
    return deliverables_dir(project_id)


def artifact_rel_path(task_id: str, task_type: str) -> str:
    if is_code_project_task(task_type):
        return f"{task_id}/"
    return f"{task_id}_deliverable.md"


def _file_kind(rel: str) -> str:
    low = rel.lower()
    if low.endswith(tuple(_CODE_EXTS)):
        return "script"
    if low.endswith((".md", ".txt", ".rst")):
        return "doc"
    if "/output/" in low or low.startswith("output/"):
        return "output"
    if "/tests/" in low or low.startswith("tests/"):
        return "test"
    if low.endswith((".json", ".yaml", ".yml", ".toml", ".xml")):
        return "data"
    return "file"


def scan_project_dir(proj_dir: Path) -> list[dict]:
    """扫描代码工程目录内的所有产出文件。"""
    if not proj_dir.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(proj_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(proj_dir)
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel.parts):
            continue
        rel_s = rel.as_posix()
        out.append({
            "path": rel_s,
            "name": p.name,
            "size": p.stat().st_size,
            "kind": _file_kind(rel_s),
        })
    return out


def _legacy_deliverable_path(project_id: str, task_id: str) -> Path:
    return deliverables_dir(project_id) / f"{task_id}_deliverable.md"


def _safe_read(path: Path, *, max_bytes: int = 512_000) -> tuple[bool, str]:
    if not path.is_file():
        return False, ""
    try:
        if path.stat().st_size > max_bytes:
            return True, path.read_text(encoding="utf-8", errors="replace")[:max_bytes] + "\n\n…（已截断）"
        return True, path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, ""


def _pick_primary_file(files: list[dict], *, task_type: str = "") -> str:
    if task_type == "code-testing":
        for prefer in ("reports/test_report.md", "tests/cases.md"):
            if any(f["path"] == prefer for f in files):
                return prefer
    for prefer in ("README.md", "readme.md"):
        if any(f["path"] == prefer for f in files):
            return prefer
    for f in files:
        if f.get("kind") == "doc":
            return f["path"]
    for f in files:
        if f.get("kind") == "script":
            return f["path"]
    return files[0]["path"] if files else ""


def _resolve_file_path(project_id: str, task_id: str, relpath: str, *,
                       task_type: str = "") -> Optional[Path]:
    if not relpath or ".." in relpath or relpath.startswith("/"):
        return None
    bases: list[Path] = []
    if is_code_project_task(task_type):
        bases.append(task_project_dir(project_id, task_id))
    bases.append(deliverables_dir(project_id))
    for base in bases:
        candidate = (base / relpath).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def get_task_deliverable_bundle(store, project_id: str, task_id: str) -> dict:
    row = store.get_task(project_id, task_id) or {}
    agent_id = row.get("agent") or ""
    task_type = row.get("task_type") or ""
    meta = row.get("meta") or {}

    code_project = is_code_project_task(task_type)
    base_kind = "code_project" if code_project else "document"

    files: list[dict] = []
    primary_path = ""
    primary_rel = ""

    if code_project:
        proj = task_project_dir(project_id, task_id)
        files = scan_project_dir(proj)
        if meta.get("artifacts"):
            known = {f["path"] for f in files}
            for f in meta.get("artifacts") or []:
                if f.get("path") not in known:
                    files.append(f)
        primary_rel = _pick_primary_file(files, task_type=task_type)
        if primary_rel:
            primary_path = str(proj / primary_rel)
    else:
        legacy = _legacy_deliverable_path(project_id, task_id)
        primary_rel = legacy.name
        primary_path = str(legacy)
        if legacy.is_file():
            files = [{
                "path": legacy.name,
                "name": legacy.name,
                "size": legacy.stat().st_size,
                "kind": "doc",
            }]

    # 兼容旧跑法：代码任务若工程目录空，回退 legacy 文档与 agent workspace
    if code_project and not files:
        legacy = _legacy_deliverable_path(project_id, task_id)
        if legacy.is_file():
            files.append({
                "path": f"_legacy/{legacy.name}",
                "name": legacy.name,
                "size": legacy.stat().st_size,
                "kind": "doc",
                "location": "legacy",
            })
            primary_rel = f"_legacy/{legacy.name}"
            primary_path = str(legacy)
        ws = workspace_dir(agent_id)
        if ws.is_dir():
            for p in sorted(ws.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(ws)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                if p.name in {"IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md", "HEARTBEAT.md", "TOOLS.md"}:
                    continue
                rel_s = rel.as_posix()
                files.append({
                    "path": rel_s,
                    "name": p.name,
                    "size": p.stat().st_size,
                    "kind": _file_kind(rel_s),
                    "location": "workspace",
                })
            if not primary_rel and files:
                primary_rel = _pick_primary_file(files, task_type=task_type)

    exists, content = _safe_read(Path(primary_path)) if primary_path else (False, "")

    return {
        "task_id": task_id,
        "agent_id": agent_id,
        "task_type": task_type,
        "base": base_kind,
        "project_dir": f"{task_id}/" if code_project else "",
        "primary": {
            "path": primary_rel,
            "exists": exists,
            "content": content,
        },
        "files": files,
    }


def read_task_artifact_file(store, project_id: str, task_id: str, relpath: str) -> dict:
    row = store.get_task(project_id, task_id) or {}
    task_type = row.get("task_type") or ""

    if relpath.startswith("_legacy/"):
        path = deliverables_dir(project_id) / relpath.removeprefix("_legacy/")
    elif is_code_project_task(task_type):
        loc = (row.get("meta") or {}).get("artifact_base")
        if loc == "workspace":
            path = workspace_dir(row.get("agent") or "")
            candidate = (path / relpath).resolve()
            if not candidate.is_file():
                path = _resolve_file_path(project_id, task_id, relpath, task_type=task_type)
            else:
                path = candidate
        else:
            path = _resolve_file_path(project_id, task_id, relpath, task_type=task_type)
    else:
        path = _resolve_file_path(project_id, task_id, relpath, task_type=task_type)

    if path is None:
        return {"exists": False, "path": relpath, "content": ""}
    exists, content = _safe_read(path)
    return {
        "exists": exists,
        "path": relpath,
        "name": path.name,
        "size": path.stat().st_size if exists else 0,
        "kind": _file_kind(relpath),
        "content": content,
    }
