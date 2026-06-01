"""非 LLM：整图依赖校验闸门（委托 project-data check-cycle）。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from common.logger import normalize_project_id
from common.paths import TEAM_OK_DIR, project_dir, project_data_script, task_data_path


def _log_step_failure(project_id: str, step: str, detail: str, ctx: str = "") -> None:
    try:
        p = str(TEAM_OK_DIR)
        if p not in sys.path:
            sys.path.insert(0, p)
        from common.logger import log_skill_step_failure

        log_skill_step_failure(project_id, "GRAPH_GATE", step, detail, ctx)
    except Exception:
        pass


def project_data_py() -> Path:
    return project_data_script()


def assert_valid_task_graph(project_id: str) -> None:
    """依赖图须为合法 DAG，否则 stderr + exit(1)。"""
    pid = normalize_project_id(project_id)
    tdf = task_data_path(pid)
    if not tdf.is_file():
        _log_step_failure(pid or (project_id or ""), "task_data_missing", str(tdf))
        print(f"Error: 项目不存在或无 task_data.json: {pid}", file=sys.stderr)
        sys.exit(1)
    r = subprocess.run(
        [str(project_data_py()), "check-cycle", pid],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        _log_step_failure(pid, "check_cycle_failed", msg[:500] if msg else "check-cycle non-zero", msg)
        print(f"Error: 依赖图校验失败，已中止操作: {msg}", file=sys.stderr)
        sys.exit(1)
