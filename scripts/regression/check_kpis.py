#!/usr/bin/env python3
"""回归 KPI 采集脚本 — 直接读取 state.db，公式可审计。

K7：triage 有效决策率。
有效 = interaction.status='done' 且 response_ref 非空（有 response_snapshot 审计快照更佳）。
"""
from __future__ import annotations

import sqlite3
from typing import Union


def _col(row: Union[tuple, sqlite3.Row], idx: int):
    """兼容 tuple / sqlite3.Row 两种 row_factory。"""
    if isinstance(row, sqlite3.Row):
        return row[idx]
    return row[idx]


def check_k7(conn: sqlite3.Connection, project_id: str) -> float:
    """K7: triage 有效决策率（0.0 ~ 1.0）。

    有效决策定义：
    1. interaction.kind='triage' 且 project_id 匹配
    2. interaction.status='done'（收到合法响应）
    3. interaction.response_ref 非空（响应文件已落盘）
    4. （加分）run_event 中存在 response_snapshot 审计快照

    无 triage 交互时返回 0.0。
    """
    rows = conn.execute(
        "SELECT interaction_id, status, response_ref FROM interaction "
        "WHERE kind='triage' AND project_id=?",
        (project_id,),
    ).fetchall()
    if not rows:
        return 0.0
    effective = 0
    for r in rows:
        iid = _col(r, 0)
        status = _col(r, 1) or ""
        ref = _col(r, 2) or ""
        if status != "done" or not ref:
            continue
        # 审计快照存在则更可信；不存在仍计为有效（audit 开关可能关闭）
        snap = conn.execute(
            "SELECT COUNT(*) FROM run_event "
            "WHERE interaction_id=? AND kind='response_snapshot'",
            (iid,),
        ).fetchone()[0]
        if snap >= 0:
            effective += 1
    return effective / len(rows)
