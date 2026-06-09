#!/usr/bin/env python3
"""I-06：REG 证明账本 — append-only 归档，reset 前导出不可变 artifact。

每条记录写入 business/regression/runs.jsonl（gitignore 下运行时目录）。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _repo_root() -> Path:
    return Path(os.environ.get("MYTEAM_ROOT", Path(__file__).resolve().parents[2]))


def _ledger_path(repo: Optional[Path] = None) -> Path:
    repo = repo or _repo_root()
    d = repo / "business" / "regression"
    d.mkdir(parents=True, exist_ok=True)
    return d / "runs.jsonl"


def _git_commit(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _cli_version(name: str) -> str:
    try:
        out = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return (out.stdout or out.stderr).strip().split("\n")[0]
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unavailable"


def _export_db_tables(db: Path, dest: Path, project_id: str, repo: Path) -> list[str]:
    """导出 project/task/interaction/run_event 快照到 JSON 文件。"""
    if not db.is_file():
        return []
    dest.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    tables = {
        "project": ("SELECT * FROM project WHERE project_id=?", (project_id,)),
        "task": ("SELECT * FROM task WHERE project_id=?", (project_id,)),
        "interaction": ("SELECT * FROM interaction WHERE project_id=?", (project_id,)),
        "run_event": (
            "SELECT * FROM run_event WHERE interaction_id LIKE ? OR interaction_id=?",
            (f"{project_id}:%", f"{project_id}:dispatch"),
        ),
        "kernel_job": ("SELECT * FROM kernel_job WHERE project_id=?", (project_id,)),
        "workspace_event": (
            "SELECT * FROM workspace_event WHERE project_id=?",
            (project_id,),
        ),
    }
    for name, (sql, params) in tables.items():
        try:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:
            rows = []
        if rows:
            out = dest / f"{name}.json"
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                exported.append(str(out.relative_to(repo)))
            except ValueError:
                exported.append(str(out))
    conn.close()
    return exported


def append_run_record(
    *,
    reg_id: str,
    project_id: str,
    pass_: bool,
    kpis: dict[str, Any],
    meta: Optional[dict[str, Any]] = None,
    repo: Optional[Path] = None,
) -> dict[str, Any]:
    """写入一条 append-only 账本记录；返回完整 record（含 run_id）。"""
    repo = repo or _repo_root()
    db = repo / "business" / "tasks" / "state.db"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    artifact_dir = repo / "business" / "regression" / "artifacts" / run_id
    exported = _export_db_tables(db, artifact_dir, project_id, repo)

    record: dict[str, Any] = {
        "run_id": run_id,
        "reg_id": reg_id,
        "project_id": project_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pass": pass_,
        "git_commit": _git_commit(repo),
        "cli": {
            "claude": _cli_version("claude"),
            "opencode": _cli_version("opencode"),
        },
        "kpis": kpis,
        "artifact_dir": str(artifact_dir.relative_to(repo)),
        "exported_tables": exported,
        "meta": meta or {},
    }
    ledger = _ledger_path(repo)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_runs(reg_id: Optional[str] = None, *, repo: Optional[Path] = None) -> list[dict]:
    ledger = _ledger_path(repo)
    if not ledger.is_file():
        return []
    out: list[dict] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if reg_id is None or rec.get("reg_id") == reg_id:
            out.append(rec)
    return out


def last_run(reg_id: str, *, repo: Optional[Path] = None) -> Optional[dict]:
    runs = list_runs(reg_id, repo=repo)
    return runs[-1] if runs else None


def last_pass_run(reg_id: str, *, repo: Optional[Path] = None) -> Optional[dict]:
    """最近一次 pass=true 的归档记录（CHECK_ONLY 回退用）。"""
    runs = list_runs(reg_id, repo=repo)
    for rec in reversed(runs):
        if rec.get("pass"):
            return rec
    return None
