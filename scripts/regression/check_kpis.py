#!/usr/bin/env python3
"""从 state.db 读取 KPI 并输出 pass/fail。

用法:
    python check_kpis.py --db <path> --project <id> [--k4-adopted N] [--k4-total N]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def check_k1(conn: sqlite3.Connection, project_id: str) -> float:
    """叶子任务完成率：done/needs_review 叶子数 / 叶子总数。"""
    rows = _query(conn, """
        SELECT status FROM task
        WHERE project_id = ?
          AND task_id NOT IN (SELECT parent_id FROM task WHERE project_id = ? AND parent_id IS NOT NULL)
    """, (project_id, project_id))
    if not rows:
        return 0.0
    done = sum(1 for r in rows if r["status"] in ("completed", "needs_review"))
    return done / len(rows)


def check_k4(adopted: int, total: int) -> float:
    """孤儿交付物回收率：从调用方传入分子/分母（REG-04 脚本统计）。"""
    if total == 0:
        return 1.0
    return adopted / total


def _gate_task_attempt(interaction_id: str, project_id: str) -> tuple[str, int] | None:
    """从 ``{project}:{task}:execute:{attempt}`` 解析 task_id 与 attempt。"""
    marker = ":execute:"
    if not interaction_id or marker not in interaction_id:
        return None
    head, attempt_str = interaction_id.rsplit(":", 1)
    if not head.endswith(marker.rstrip(":")):
        return None
    try:
        attempt = int(attempt_str)
    except ValueError:
        return None
    prefix = f"{project_id}:"
    if not head.startswith(prefix):
        return None
    task_id = head[len(prefix):].rsplit(":", 1)[0]
    return task_id, attempt


def check_k2(conn: sqlite3.Connection, project_id: str) -> float:
    """Gate 首次通过率：首次 execute 即 gate_passed 的任务数 / 有过 Gate 的任务数。"""
    rows = conn.execute(
        "SELECT re.interaction_id, re.kind FROM run_event re "
        "LEFT JOIN interaction i ON re.interaction_id = i.interaction_id "
        "WHERE (i.project_id = ? OR re.interaction_id LIKE ?) "
        "AND re.kind IN ('gate_passed', 'gate_failed')",
        (project_id, f"{project_id}:%"),
    ).fetchall()
    first_pass: dict[str, int] = {}
    gated: set[str] = set()
    for iid, kind in rows:
        parsed = _gate_task_attempt(iid or "", project_id)
        if not parsed:
            continue
        task_id, attempt = parsed
        gated.add(task_id)
        if kind == "gate_passed":
            prev = first_pass.get(task_id)
            if prev is None or attempt < prev:
                first_pass[task_id] = attempt
    if not gated:
        return 1.0
    passed_first = sum(1 for tid in gated if first_pass.get(tid) == 1)
    return passed_first / len(gated)


def check_k8(conn: sqlite3.Connection, project_id: str) -> float:
    """并行度：parallel_wave 最大 count / 无依赖叶子数（无事件则 0）。"""
    leaves = conn.execute(
        "SELECT COUNT(*) FROM task WHERE project_id=? "
        "AND (dependencies IS NULL OR dependencies='[]')",
        (project_id,),
    ).fetchone()[0]
    if not leaves:
        return 0.0
    rows = conn.execute(
        "SELECT payload FROM run_event WHERE interaction_id=? AND kind='parallel_wave'",
        (f"{project_id}:dispatch",),
    ).fetchall()
    max_wave = 0
    for (payload,) in rows:
        try:
            max_wave = max(max_wave, int(json.loads(payload or "{}").get("count") or 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return max_wave / leaves


def _triage_result_from_row(conn: sqlite3.Connection, row: dict) -> dict:
    """从 response_ref 文件或 response_snapshot 事件读取 triage result。"""
    ref = row.get("response_ref") or ""
    if ref:
        p = Path(ref)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data.get("result") or {}
            except (OSError, json.JSONDecodeError):
                pass
    iid = row.get("interaction_id") or ""
    snap = conn.execute(
        "SELECT payload FROM run_event WHERE interaction_id=? AND kind='response_snapshot' "
        "ORDER BY id DESC LIMIT 1",
        (iid,),
    ).fetchone()
    if snap:
        try:
            payload = json.loads(snap[0] or "{}")
            resp = payload.get("response") or {}
            return resp.get("result") or {}
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _is_effective_triage(result: dict) -> bool:
    """有效决策：非盲目 retry（reassign/drop/abort、有 notes 或 target）。"""
    decision = (result.get("decision") or "").strip()
    notes = (result.get("notes") or "").strip()
    target = (result.get("target_agent") or "").strip()
    if decision in ("reassign", "drop", "abort"):
        return True
    if notes or target:
        return True
    return False


def check_k7(conn: sqlite3.Connection, project_id: str) -> float:
    """triage 有效决策率：有效 triage 数 / 已完成 triage 总数（无 triage 则 1.0）。"""
    rows = _query(conn, """
        SELECT interaction_id, response_ref
        FROM interaction
        WHERE project_id = ? AND kind = 'triage' AND status = 'done'
    """, (project_id,))
    if not rows:
        return 1.0
    effective = sum(
        1 for r in rows if _is_effective_triage(_triage_result_from_row(conn, r))
    )
    return effective / len(rows)


def check_k5(conn: sqlite3.Connection, project_id: str) -> float:
    """token 计量准确率：tokens>0 的 interaction 数 / 总数。"""
    rows = _query(conn, """
        SELECT tokens FROM interaction
        WHERE project_id = ? AND status IN ('done')
    """, (project_id,))
    if not rows:
        return 0.0
    ok = sum(1 for r in rows if (r["tokens"] or 0) > 0)
    return ok / len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="state.db 路径（不传则跳过 DB 查询）")
    ap.add_argument("--project", default=None, help="项目 ID")
    ap.add_argument("--k4-adopted", type=int, default=None)
    ap.add_argument("--k4-total", type=int, default=None)
    ap.add_argument("--k8-threshold", type=float, default=0.8, help="K8 并行度阈值（默认 0.8）")
    ap.add_argument("--k7-threshold", type=float, default=0.8, help="K7 triage 有效决策率阈值（默认 0.8）")
    ap.add_argument("--k2-threshold", type=float, default=0.7, help="K2 Gate 首错率阈值（默认 0.7）")
    args = ap.parse_args()

    results: dict = {}

    if args.db and args.project:
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"[check_kpis] state.db 不存在: {db_path}", file=sys.stderr)
            return 2
        conn = sqlite3.connect(str(db_path))
        try:
            k1 = check_k1(conn, args.project)
            k2 = check_k2(conn, args.project)
            k5 = check_k5(conn, args.project)
            k7 = check_k7(conn, args.project)
            k8 = check_k8(conn, args.project)
            results["k1"] = round(k1, 4)
            results["k2"] = round(k2, 4)
            results["k5"] = round(k5, 4)
            results["k7"] = round(k7, 4)
            results["k8"] = round(k8, 4)
            results["k1_pass"] = k1 >= 0.80
            results["k2_pass"] = k2 >= args.k2_threshold
            results["k5_pass"] = k5 >= 1.0
            results["k7_pass"] = k7 >= args.k7_threshold
            results["k8_pass"] = k8 >= args.k8_threshold
        finally:
            conn.close()

    if args.k4_adopted is not None and args.k4_total is not None:
        k4 = check_k4(args.k4_adopted, args.k4_total)
        results["k4"] = round(k4, 4)
        results["k4_adopted"] = args.k4_adopted
        results["k4_total"] = args.k4_total
        results["k4_pass"] = k4 >= 0.95

    print(json.dumps(results, indent=2, ensure_ascii=False))

    failed = [k for k in ("k1_pass", "k2_pass", "k4_pass", "k5_pass", "k7_pass", "k8_pass")
              if k in results and not results[k]]
    if failed:
        print(f"[check_kpis] KPI 未通过: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
