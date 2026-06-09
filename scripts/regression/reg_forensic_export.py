#!/usr/bin/env python3
"""A-01：法证导出脚本 — 将指定 project 的所有运行数据快照到独立目录，供离线审计。

用法示例：
    python scripts/regression/reg_forensic_export.py --project-id myproj-20240601
    python scripts/regression/reg_forensic_export.py --project-id myproj-20240601 \
        --output-dir /tmp/forensics/myproj
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(os.environ.get("MYTEAM_ROOT", Path(__file__).resolve().parents[2]))


def _state_db(repo: Path) -> Path:
    return repo / "business" / "tasks" / "state.db"


def _workspaces_root(repo: Path) -> Path:
    return repo / "business" / "workspaces"


# ---------------------------------------------------------------------------
# 数据库导出
# ---------------------------------------------------------------------------

def _export_db(
    db: Path,
    project_id: str,
    dest: Path,
) -> dict[str, int]:
    """从 state.db 导出所有与 project_id 相关的表行，返回各表行数。"""
    counts: dict[str, int] = {}
    if not db.is_file():
        return counts

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    # 表名 → (SQL, params)
    queries: dict[str, tuple[str, tuple[Any, ...]]] = {
        "project": (
            "SELECT * FROM project WHERE project_id=?",
            (project_id,),
        ),
        "task": (
            "SELECT * FROM task WHERE project_id=?",
            (project_id,),
        ),
        "interaction": (
            "SELECT * FROM interaction WHERE project_id=?",
            (project_id,),
        ),
        "run_event": (
            "SELECT * FROM run_event WHERE interaction_id LIKE ? OR interaction_id=?",
            (f"{project_id}:%", f"{project_id}:dispatch"),
        ),
        "kernel_job": (
            "SELECT * FROM kernel_job WHERE project_id=?",
            (project_id,),
        ),
        "workspace_event": (
            "SELECT * FROM workspace_event WHERE project_id=?",
            (project_id,),
        ),
    }

    for table, (sql, params) in queries.items():
        try:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:
            # 表不存在时跳过
            rows = []
        counts[table] = len(rows)
        if rows:
            out_file = dest / f"{table}.json"
            out_file.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    conn.close()
    return counts


def _get_interaction_agent_ids(db: Path, project_id: str) -> list[tuple[str, str]]:
    """返回项目所有 interaction 的 (interaction_id, agent_id) 对。"""
    if not db.is_file():
        return []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT interaction_id, agent_id FROM interaction WHERE project_id=?",
            (project_id,),
        ).fetchall()
        result = [(r["interaction_id"], r["agent_id"]) for r in rows if r["agent_id"]]
    except sqlite3.OperationalError:
        result = []
    conn.close()
    return result


# ---------------------------------------------------------------------------
# Workspace .response 文件收集
# ---------------------------------------------------------------------------

def _collect_response_files(
    repo: Path,
    project_id: str,
    interaction_agent_pairs: list[tuple[str, str]],
    dest: Path,
) -> list[str]:
    """将各 agent workspace 中与本项目相关的 .response 文件复制到 dest/responses/。

    扫描路径：business/workspaces/workspace-<agent_id>/.response/<interaction_id>.*
    同时写入每个 agent workspace 的 .response 目录列表（目录不存在时跳过）。
    返回已复制的文件相对路径列表。
    """
    workspaces = _workspaces_root(repo)
    copied: list[str] = []

    # 按 agent_id 分组 interaction_id
    agent_to_interactions: dict[str, list[str]] = {}
    for iid, aid in interaction_agent_pairs:
        agent_to_interactions.setdefault(aid, []).append(iid)

    for agent_id, iids in agent_to_interactions.items():
        ws_resp = workspaces / f"workspace-{agent_id}" / ".response"
        agent_dest = dest / "responses" / agent_id
        agent_dest.mkdir(parents=True, exist_ok=True)

        # 写出目录列表
        if ws_resp.is_dir():
            listing = sorted(p.name for p in ws_resp.iterdir())
        else:
            listing = []
        listing_file = agent_dest / "_dir_listing.json"
        listing_file.write_text(
            json.dumps(
                {"agent_id": agent_id, "path": str(ws_resp), "files": listing},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # 复制匹配本项目 interaction_id 前缀的 .response 文件
        if ws_resp.is_dir():
            for iid in iids:
                # 文件名可能是 <interaction_id>.response 或带其他后缀
                for candidate in ws_resp.iterdir():
                    if candidate.name.startswith(iid):
                        target = agent_dest / candidate.name
                        shutil.copy2(str(candidate), str(target))
                        copied.append(str(target.relative_to(dest)))

    return copied


# ---------------------------------------------------------------------------
# summary.json
# ---------------------------------------------------------------------------

def _task_statuses(db: Path, project_id: str) -> list[dict[str, Any]]:
    """返回项目所有 task 的 task_id / task_type / status 摘要。"""
    if not db.is_file():
        return []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT task_id, task_type, status FROM task WHERE project_id=?",
            (project_id,),
        ).fetchall()
        result = [dict(r) for r in rows]
    except sqlite3.OperationalError:
        result = []
    conn.close()
    return result


def _write_summary(
    dest: Path,
    project_id: str,
    db_counts: dict[str, int],
    response_files: list[str],
    task_statuses: list[dict[str, Any]],
    timestamp: str,
) -> None:
    summary = {
        "project_id": project_id,
        "exported_at": timestamp,
        "db_row_counts": db_counts,
        "response_files_copied": len(response_files),
        "response_files": response_files,
        "task_count": len(task_statuses),
        "task_statuses": task_statuses,
    }
    (dest / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run_export(project_id: str, output_dir: Optional[Path] = None) -> Path:
    """执行导出；返回输出目录路径。"""
    repo = _repo_root()
    db = _state_db(repo)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if output_dir is None:
        output_dir = repo / "business" / "regression" / "forensics" / f"{project_id}-{ts}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 导出数据库表
    db_counts = _export_db(db, project_id, output_dir)

    # 2. 收集 workspace .response 文件
    pairs = _get_interaction_agent_ids(db, project_id)
    response_files = _collect_response_files(repo, project_id, pairs, output_dir)

    # 3. 获取任务状态
    statuses = _task_statuses(db, project_id)

    # 4. 写 summary.json
    _write_summary(output_dir, project_id, db_counts, response_files, statuses, ts)

    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A-01 法证导出：将 project 的 DB 数据与 workspace response 文件导出到独立目录。"
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="要导出的 project_id（必填）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="导出目录（默认：business/regression/forensics/<project_id>-<timestamp>/）",
    )
    args = parser.parse_args()

    out = run_export(
        project_id=args.project_id,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(str(out))


if __name__ == "__main__":
    main()
