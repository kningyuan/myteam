#!/usr/bin/env python3
"""REG-L3：自升级 scaffold（CHECK_ONLY 默认 + 可选 E2E）。

G1：self-upgrade workflow 存在且 task_type 已注册。
G2：若 state.db 存在 project self-upgrade，则 skill 草案路径存在。

用法:
    # CHECK_ONLY（suite all 默认）
    REG_L3_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l3_self_upgrade.py

    # 全量 E2E（需 claude CLI）
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l3_self_upgrade.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PROJECT_ID = os.environ.get("REG_L3_PROJECT_ID", "self-upgrade")
WORKFLOW_ID = "self-upgrade"
WORKFLOW_PATH = REPO / "business/workflows/self-upgrade.yaml"
TEMPLATES_PATH = REPO / "business/templates/templates.yaml"
SKILL_EXTRACT_TASK = "skill-extract"
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402

BUDGET = int(os.environ.get("REG_L3_BUDGET", str(REG_DEFAULT_BUDGET)))
GOAL = (
    "myteam L3 自升级 scaffold 验证：plan→execute→review，"
    "skill-extract 任务产出可复用 pattern 草案"
)
AGENTS = ("main", "arch", "qa", "product")

REQUIRED_TASK_TYPES = (
    "requirements",
    "architecture-review",
    "decision-record",
    "code-writing",
    "research",
    "code-review",
    "acceptance-report",
)

sys.path.insert(0, str(REPO / "scripts" / "regression"))
sys.path.insert(0, str(REPO / "backend"))
from common.skill_extract import skill_draft_path  # noqa: E402
from regression_archive import append_run_record  # noqa: E402


def _load_yaml(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _templates_task_types(templates: dict) -> set[str]:
    skip = {"version", "meta"}
    return {k for k in templates if k not in skip and isinstance(templates.get(k), dict)}


def check_g1_prerequisites() -> tuple[bool, list[str]]:
    """G1：workflow 与 templates 前置。"""
    issues: list[str] = []

    if not WORKFLOW_PATH.is_file():
        issues.append(f"缺少 workflow 文件: {WORKFLOW_PATH.relative_to(REPO)}")
        return False, issues

    wf = _load_yaml(WORKFLOW_PATH)
    if not isinstance(wf, dict):
        issues.append(f"workflow YAML 无法解析: {WORKFLOW_PATH}")
        return False, issues

    wf_id = wf.get("id")
    if wf_id != WORKFLOW_ID:
        issues.append(f"workflow id 期望 {WORKFLOW_ID!r}，实际 {wf_id!r}")

    tasks = wf.get("tasks") or []
    if not tasks:
        issues.append("workflow tasks 为空")
    wf_types = {t.get("task_type") for t in tasks if isinstance(t, dict)}
    missing_in_wf = set(REQUIRED_TASK_TYPES) - wf_types
    if missing_in_wf:
        issues.append(f"workflow 未使用预期 task_type: {sorted(missing_in_wf)}")

    if not TEMPLATES_PATH.is_file():
        issues.append(f"缺少 templates.yaml: {TEMPLATES_PATH.relative_to(REPO)}")
        return False, issues

    templates = _load_yaml(TEMPLATES_PATH)
    if not isinstance(templates, dict):
        issues.append("templates.yaml 无法解析")
        return False, issues

    registered = _templates_task_types(templates)
    for tt in REQUIRED_TASK_TYPES:
        if tt not in registered:
            issues.append(f"templates.yaml 缺少 task_type: {tt}")

    return len(issues) == 0, issues


def check_g2_skill_draft(db: Path) -> tuple[bool, str]:
    """G2（场景断言，非通用 Gate）：整项目 E2E 后 skill-extract 草案路径存在。"""
    if not db.is_file():
        return True, "state.db 不存在，跳过 G2"

    import sqlite3

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT status FROM project WHERE project_id=?", (PROJECT_ID,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return True, f"project {PROJECT_ID!r} 不在 db，跳过 G2"

    draft = skill_draft_path(PROJECT_ID, SKILL_EXTRACT_TASK)
    if draft.is_file():
        return True, f"skill 草案: {draft.relative_to(REPO)}"

    return False, f"project 存在但缺少 skill 草案: {draft.relative_to(REPO)}"


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _patch_agent_claude(agent_id: str) -> dict | None:
    cfg_path = REPO / "business/config/agents_config.json"
    if not cfg_path.is_file():
        return None
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    old = data.get(agent_id)
    entry = dict(data.get(agent_id) or {})
    entry["backend"] = "claude"
    entry["model"] = os.environ.get("REG_L3_MODEL", "claude-sonnet-4-6")
    entry.setdefault("workspace", f"business/workspaces/workspace-{agent_id}")
    data[agent_id] = entry
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return old


def _task_statuses(db: Path, project_id: str) -> dict[str, str]:
    if not db.is_file():
        return {}
    import sqlite3

    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT task_id, status FROM task WHERE project_id=?", (project_id,)
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def _reset_failed_leaf(db: Path, project_id: str, leaf_id: str, budget: int) -> None:
    """仅 reset 失败叶子 + 恢复 project 可 resume。"""
    import sqlite3

    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE task SET status='pending' WHERE project_id=? AND task_id=? "
        "AND status IN ('failed','blocked')",
        (project_id, leaf_id),
    )
    row = conn.execute(
        "SELECT meta FROM project WHERE project_id=?", (project_id,)
    ).fetchone()
    meta = {}
    if row and row[0]:
        try:
            meta = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            meta = {}
    meta["token_budget"] = max(int(meta.get("token_budget") or 0), budget)
    conn.execute(
        "UPDATE project SET status='in_progress', meta=? WHERE project_id=? "
        "AND status IN ('failed','partially_failed','paused','in_progress')",
        (json.dumps(meta, ensure_ascii=False), project_id),
    )
    conn.commit()
    conn.close()


def _restore_agent(agent_id: str, old: dict | None) -> None:
    if old is None:
        return
    cfg_path = REPO / "business/config/agents_config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data[agent_id] = old
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _print_gate_criteria() -> None:
    print("=== REG-L3 发版门禁目标 ===")
    print("  [G1] self-upgrade workflow + task_types 注册")
    print("  [G2] project completed 后 skill 草案路径存在（skill-extract）")
    print("  [G3] budget 达 degrade_threshold 时自动降级（kernel 未接线）")
    print("  [G4] content-campaign publish-post evidence_url（见 reg_l3_content_campaign.py）")
    print("  合入须大元帅确认；禁止无人值守 push。")
    print()


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    check_only = os.environ.get("REG_L3_CHECK_ONLY", "1").lower() in ("1", "true", "yes")
    resume = os.environ.get("REG_L3_RESUME", "").lower() in ("1", "true", "yes")
    db = REPO / "business/tasks/state.db"

    print("=== REG-L3 自升级 scaffold ===")
    print(f"  workflow: {WORKFLOW_ID}")
    print(f"  project:  {PROJECT_ID}")
    print(f"  mode:     {'CHECK_ONLY' if check_only else 'E2E'}")
    _print_gate_criteria()

    g1_ok, issues = check_g1_prerequisites()
    g2_ok, g2_msg = check_g2_skill_draft(db)

    if check_only:
        print("=== G1 prerequisites ===")
        if g1_ok:
            print("  workflow 文件:     OK")
            print(f"  task_types ({len(REQUIRED_TASK_TYPES)}): OK")
        else:
            for msg in issues:
                print(f"  FAIL: {msg}")
        print("=== G2 skill draft（CHECK_ONLY 仅参考，不阻塞）===")
        print(f"  {g2_msg} → {'PASS' if g2_ok else 'SKIP/FAIL'}")
        reg_pass = g1_ok
        print(f"REG-L3: {'PASS' if reg_pass else 'FAIL'} (CHECK_ONLY 以 G1 为准)")
        rec = append_run_record(
            reg_id="REG-L3",
            project_id=PROJECT_ID,
            pass_=reg_pass,
            kpis={"G1": g1_ok, "G2": g2_ok, "g2_informational": True},
            meta={"mode": "check_only"},
        )
        print(f"  I-06 archived: run_id={rec['run_id']}")
        return 0 if reg_pass else 1

    if not g1_ok:
        print("=== G1 prerequisites ===")
        for msg in issues:
            print(f"  FAIL: {msg}")
        print("REG-L3: FAIL (G1)")
        return 1

    reg_model = os.environ.get("REG_L3_MODEL", "claude-sonnet-4-6")
    if "haiku" in reg_model.lower():
        print(f"REG-L3: FAIL（plan phase 禁用 haiku：{reg_model}）")
        return 1

    if not _claude_available():
        print("REG-L3: SKIP（claude CLI 不可用）")
        append_run_record(
            reg_id="REG-L3",
            project_id=PROJECT_ID,
            pass_=False,
            kpis={"G1": g1_ok, "G2": False, "skip": True},
            meta={"mode": "skip", "reason": "claude CLI unavailable"},
        )
        return 2

    patched: dict[str, dict | None] = {}
    for agent_id in AGENTS:
        patched[agent_id] = _patch_agent_claude(agent_id)

    if resume and db.is_file():
        tasks_pre = _task_statuses(db, PROJECT_ID)
        append_run_record(
            reg_id="REG-L3",
            project_id=PROJECT_ID,
            pass_=False,
            kpis={"tasks": tasks_pre, "phase": "pre_reset_resume"},
            meta={"mode": "pre_reset_resume"},
        )
        _reset_failed_leaf(db, PROJECT_ID, "upgrade-plan", BUDGET)
        cmd = [
            str(REPO / "venv/bin/python3"),
            "-c",
            (
                "from common.run_kernel import resume_project; "
                f"out = resume_project({PROJECT_ID!r}, backend='claude'); "
                "import json; print(json.dumps({'status': out.status, 'tasks': "
                "{k: v.status for k, v in out.tasks.items()}}, ensure_ascii=False))"
            ),
        ]
        mode = "resume"
    else:
        cmd = [
            str(REPO / "venv/bin/python3"),
            str(REPO / "backend/common/run_kernel.py"),
            PROJECT_ID,
            "--goal", GOAL,
            "--workflow", WORKFLOW_ID,
            "--backend", "claude",
            "--budget", str(BUDGET),
            "--mode", "one_shot",
        ]
        mode = "fresh"
    print("=== REG-L3 E2E ===")
    print("  mode:", mode)
    print("  命令:", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            timeout=int(os.environ.get("REG_L3_TIMEOUT", "7200")),
        )
    finally:
        for agent_id, old in patched.items():
            _restore_agent(agent_id, old)

    proj_status = "N/A"
    if db.is_file():
        import sqlite3

        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT status FROM project WHERE project_id=?", (PROJECT_ID,)
        ).fetchone()
        if row:
            proj_status = row[0]
        conn.close()

    tasks = _task_statuses(db, PROJECT_ID)
    g2_ok, g2_msg = check_g2_skill_draft(db)
    terminal_ok = {"completed", "needs_review"}
    g1_tasks_ok = bool(tasks) and all(s in terminal_ok for s in tasks.values())
    g1_ok_e2e = proj_status == "completed" and g1_tasks_ok
    reg_pass = (
        proc.returncode == 0
        and g1_ok_e2e
        and g2_ok
    )
    failed_task = next((tid for tid, st in tasks.items() if st not in terminal_ok), "")

    print("\n=== REG-L3 结果 ===")
    print(f"  run_kernel exit: {proc.returncode}")
    print(f"  project.status: {proj_status}")
    print(f"  tasks: {tasks}")
    print(f"  G1 (全任务终态+completed): {'PASS' if g1_ok_e2e else 'FAIL'}")
    print(f"  G2: {g2_msg} → {'PASS' if g2_ok else 'FAIL'}")
    if failed_task:
        print(f"  failed_task: {failed_task}")
    print(f"REG-L3: {'PASS' if reg_pass else 'FAIL'}")
    rec = append_run_record(
        reg_id="REG-L3",
        project_id=PROJECT_ID,
        pass_=reg_pass,
        kpis={
            "G1": g1_ok_e2e,
            "G2": g2_ok,
            "project_status": proj_status,
            "tasks": tasks,
            "failed_task": failed_task,
        },
        meta={"mode": mode, "run_kernel_exit": proc.returncode, "budget": BUDGET},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if reg_pass else 1


if __name__ == "__main__":
    sys.exit(main())
