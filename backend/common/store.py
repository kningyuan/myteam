#!/usr/bin/env python3
"""SQLite 运行态真相库（D13 / O4）。

运行态状态 = SQLite（零新依赖、单 .db 文件可移植、ACID 无半截写、可查询）。
表：project / task / interaction / run_event / memory。

- 人类产物仍是文件（deliverables/*.md、evidence/）。
- 静态配置仍是 JSON（agents_config.json 等）。
- task_data.json 退为**只读导出视图**（export_project），不再是真相。
- 对现有 task_data.json 提供一次性导入器（import_task_data）。

并发：WAL + busy_timeout；每线程独立连接（L2 真并行调度）。
状态机（D18）：
  interaction：pending → running → done | failed | cancelled | timed_out
  task：pending → in_progress → completed | needs_review | failed | blocked
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):  # 作为脚本直接运行时，确保 common 包可导入
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.paths import TASKS_DIR
from common.store_backend import StoreBackend
from common.store_sqlite import SQLiteStoreBackend


def default_db_path() -> Path:
    return TASKS_DIR / "state.db"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False) if v is not None else "null"


def _loads(v: Optional[str]) -> Any:
    if v is None:
        return None
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    project_id  TEXT PRIMARY KEY,
    title       TEXT DEFAULT '',
    mode        TEXT DEFAULT 'one_shot',   -- one_shot | recurring
    status      TEXT DEFAULT 'pending',
    created_at  TEXT,
    updated_at  TEXT,
    meta        TEXT DEFAULT 'null'
);

CREATE TABLE IF NOT EXISTS task (
    project_id    TEXT,
    task_id       TEXT,
    parent_id     TEXT DEFAULT NULL,       -- 子任务挂父任务
    name          TEXT DEFAULT '',
    agent         TEXT DEFAULT '',
    reviewer      TEXT DEFAULT '',
    task_type     TEXT DEFAULT '',
    status        TEXT DEFAULT 'pending',
    dependencies  TEXT DEFAULT '[]',
    started_at    TEXT,
    completed_at  TEXT,
    updated_at    TEXT,
    meta          TEXT DEFAULT 'null',
    PRIMARY KEY (project_id, task_id)
);

CREATE TABLE IF NOT EXISTS interaction (
    interaction_id TEXT PRIMARY KEY,
    kind           TEXT,
    project_id     TEXT,
    task_id        TEXT,
    agent_id       TEXT,
    backend        TEXT DEFAULT '',
    status         TEXT DEFAULT 'pending',
    attempt        INTEGER DEFAULT 1,
    started_at     TEXT,
    last_event_at  TEXT,
    response_ref   TEXT DEFAULT '',
    tokens         INTEGER DEFAULT 0,
    meta           TEXT DEFAULT 'null'
);

CREATE TABLE IF NOT EXISTS run_event (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id TEXT,
    seq            INTEGER,
    kind           TEXT,
    payload        TEXT DEFAULT 'null',
    ts             TEXT
);

CREATE TABLE IF NOT EXISTS memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT,
    task_id     TEXT,
    tags        TEXT DEFAULT '[]',
    title       TEXT DEFAULT '',
    content     TEXT DEFAULT '',
    created_at  TEXT
);

-- 对话/记忆一等公民（P0）：人↔agent 多轮历史进库，供 Context Assembler 组装上下文。
CREATE TABLE IF NOT EXISTS conversation (
    conversation_id TEXT PRIMARY KEY,
    kind            TEXT DEFAULT 'dm',      -- dm | group | project
    participants    TEXT DEFAULT '[]',
    project_id      TEXT DEFAULT NULL,
    title           TEXT DEFAULT '',
    created_at      TEXT,
    updated_at      TEXT,
    meta            TEXT DEFAULT 'null'     -- {summary, summarized_through_seq, pins:[...]}
);

CREATE TABLE IF NOT EXISTS message (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    seq             INTEGER,
    role            TEXT,                   -- user | agent | system | tool
    author          TEXT DEFAULT '',
    text            TEXT DEFAULT '',
    parts           TEXT DEFAULT 'null',    -- [{type:text|tool_use|tool_result|citation, ...}]
    backend         TEXT DEFAULT '',
    tokens          INTEGER DEFAULT 0,
    created_at      TEXT,
    meta            TEXT DEFAULT 'null'
);

CREATE INDEX IF NOT EXISTS idx_task_project ON task(project_id);
CREATE INDEX IF NOT EXISTS idx_interaction_task ON interaction(project_id, task_id);
CREATE INDEX IF NOT EXISTS idx_run_event_iid ON run_event(interaction_id, seq);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory(project_id);
CREATE INDEX IF NOT EXISTS idx_message_conv ON message(conversation_id, seq);

CREATE TABLE IF NOT EXISTS workspace_event (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    source          TEXT NOT NULL,
    target          TEXT DEFAULT '',
    payload         TEXT NOT NULL DEFAULT '{}',
    metadata        TEXT NOT NULL DEFAULT '{}',
    visibility      TEXT NOT NULL DEFAULT 'project',
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_we_project ON workspace_event(json_extract(metadata, '$.project_id'));
CREATE INDEX IF NOT EXISTS idx_we_type ON workspace_event(type);

CREATE TABLE IF NOT EXISTS projection_state (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runtime (
    agent_id        TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'offline',
    last_seen       TEXT,
    current_task    TEXT DEFAULT '',
    current_project TEXT DEFAULT '',
    backend         TEXT DEFAULT '',
    model           TEXT DEFAULT '',
    workspace_ok    INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job (
    job_id          TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    pid             INTEGER,
    started_at      TEXT,
    updated_at      TEXT,
    cancel_requested INTEGER DEFAULT 0,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS publish_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT NOT NULL,
    task_id         TEXT DEFAULT '',
    platform        TEXT DEFAULT '',
    deliverable     TEXT DEFAULT '',
    status          TEXT DEFAULT 'completed',
    meta            TEXT DEFAULT 'null',
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_publish_log_project ON publish_log(project_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT NOT NULL,
    task_id         TEXT DEFAULT '',
    audit_type      TEXT DEFAULT 'geo',
    deliverable     TEXT DEFAULT '',
    status          TEXT DEFAULT 'completed',
    meta            TEXT DEFAULT 'null',
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project_id);

CREATE TABLE IF NOT EXISTS agent_config (
    agent_id        TEXT PRIMARY KEY,
    config          TEXT NOT NULL DEFAULT '{}',
    version         INTEGER DEFAULT 1,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS workflow_version (
    workflow_id     TEXT NOT NULL,
    version         INTEGER NOT NULL,
    body            TEXT NOT NULL,
    updated_at      TEXT,
    PRIMARY KEY (workflow_id, version)
);
"""


class Store:
    """SQLite 真相库句柄。每线程独立连接，共享 WAL 文件。

    Persistence I/O is delegated to a pluggable :class:`~common.store_backend.StoreBackend`
    (default: :class:`~common.store_sqlite.SQLiteStoreBackend`).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        backend: StoreBackend | None = None,
    ):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if backend is None:
            self._backend: StoreBackend = SQLiteStoreBackend(self.db_path, _SCHEMA)
        else:
            self._backend = backend

    @property
    def backend(self) -> StoreBackend:
        return self._backend

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._backend.connection

    @property
    def _fts(self) -> bool:
        return self._backend.fts_enabled

    @property
    def _memory_fts(self) -> bool:
        getter = getattr(self._backend, "memory_fts_enabled", None)
        return bool(getter() if callable(getter) else False)

    def close(self):
        self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ── project ──────────────────────────────────────────────

    def upsert_project(self, project_id: str, *, title: str = "", mode: str = "one_shot",
                       status: str = "pending", meta: Optional[dict] = None) -> None:
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO project (project_id, title, mode, status, created_at, updated_at, meta)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(project_id) DO UPDATE SET
                     title=excluded.title, mode=excluded.mode, status=excluded.status,
                     updated_at=excluded.updated_at, meta=excluded.meta""",
                (project_id, title, mode, status, now, now, _dumps(meta)),
            )

    def set_project_status(self, project_id: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE project SET status=?, updated_at=? WHERE project_id=?",
                (status, _now(), project_id),
            )

    def get_project(self, project_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM project WHERE project_id=?", (project_id,)
        ).fetchone()
        return self._row(row) if row else None

    def update_project_meta(self, project_id: str, **kv) -> None:
        """合并写入 project.meta（保留既有键）。"""
        proj = self.get_project(project_id)
        if not proj:
            return
        meta = dict(proj.get("meta") or {})
        meta.update(kv)
        with self._conn:
            self._conn.execute(
                "UPDATE project SET meta=?, updated_at=? WHERE project_id=?",
                (_dumps(meta), _now(), project_id),
            )

    def list_projects(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM project ORDER BY updated_at DESC, rowid DESC"
        ).fetchall()
        return [self._row(r) for r in rows]

    def delete_project(self, project_id: str) -> list[dict]:
        """彻底删除一个项目的全部行（5 表）。

        返回该项目的交互列表 [{interaction_id, agent_id}]，供上层清理 agent 工作目录的
        .trigger/.response 临时文件。run_event 无 project_id 列，按 ``project_id:`` 前缀清
        （含 budget/cycle/blocked 等合成 interaction_id）。
        """
        rows = self._conn.execute(
            "SELECT interaction_id, agent_id FROM interaction WHERE project_id=?",
            (project_id,)).fetchall()
        interactions = [{"interaction_id": r["interaction_id"], "agent_id": r["agent_id"]}
                        for r in rows]
        prefix = f"{project_id}:"
        ev = self._conn.execute("SELECT DISTINCT interaction_id FROM run_event").fetchall()
        ev_iids = [r["interaction_id"] for r in ev
                   if (r["interaction_id"] or "").startswith(prefix)]
        with self._conn:
            for iid in ev_iids:
                self._conn.execute("DELETE FROM run_event WHERE interaction_id=?", (iid,))
            self._conn.execute("DELETE FROM interaction WHERE project_id=?", (project_id,))
            self._conn.execute("DELETE FROM task WHERE project_id=?", (project_id,))
            self._conn.execute("DELETE FROM memory WHERE project_id=?", (project_id,))
            self._conn.execute("DELETE FROM project WHERE project_id=?", (project_id,))
        return interactions

    # ── task ─────────────────────────────────────────────────

    def upsert_task(self, project_id: str, task_id: str, *, name: str = "", agent: str = "",
                    reviewer: str = "", task_type: str = "", status: str = "pending",
                    dependencies: Optional[list] = None, parent_id: Optional[str] = None,
                    meta: Optional[dict] = None) -> None:
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO task
                     (project_id, task_id, parent_id, name, agent, reviewer, task_type,
                      status, dependencies, updated_at, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(project_id, task_id) DO UPDATE SET
                     parent_id=excluded.parent_id, name=excluded.name, agent=excluded.agent,
                     reviewer=excluded.reviewer, task_type=excluded.task_type,
                     dependencies=excluded.dependencies, updated_at=excluded.updated_at,
                     meta=excluded.meta""",
                (project_id, task_id, parent_id, name, agent, reviewer, task_type,
                 status, _dumps(dependencies or []), now, _dumps(meta)),
            )

    def set_task_status(self, project_id: str, task_id: str, status: str) -> None:
        now = _now()
        sets = ["status=?", "updated_at=?"]
        vals: list[Any] = [status, now]
        if status == "in_progress":
            sets.append("started_at=COALESCE(started_at, ?)")
            vals.append(now)
        if status in ("completed", "failed"):
            sets.append("completed_at=COALESCE(completed_at, ?)")
            vals.append(now)
        vals += [project_id, task_id]
        with self._conn:
            self._conn.execute(
                f"UPDATE task SET {', '.join(sets)} WHERE project_id=? AND task_id=?", vals
            )

    def update_task_meta(self, project_id: str, task_id: str, **kv) -> None:
        """合并写入 task.meta（用于存放 agent 摘要/引用等，D16 上下文传递）。"""
        row = self.get_task(project_id, task_id)
        meta = (row.get("meta") if row else None) or {}
        meta.update(kv)
        with self._conn:
            self._conn.execute(
                "UPDATE task SET meta=?, updated_at=? WHERE project_id=? AND task_id=?",
                (_dumps(meta), _now(), project_id, task_id),
            )

    def get_task(self, project_id: str, task_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM task WHERE project_id=? AND task_id=?", (project_id, task_id)
        ).fetchone()
        return self._task_row(row) if row else None

    def list_tasks(self, project_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM task WHERE project_id=? ORDER BY rowid", (project_id,)
        ).fetchall()
        return [self._task_row(r) for r in rows]

    # ── interaction（D8/D12：幂等/恢复/GC/计量）────────────────

    def create_interaction(self, interaction_id: str, kind: str, project_id: str, *,
                           task_id: Optional[str] = None, agent_id: str = "",
                           backend: str = "", attempt: int = 1,
                           task_status: Optional[str] = None) -> None:
        """建 interaction 记录；可在同一事务顺带改 task 状态（D13）。"""
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO interaction
                     (interaction_id, kind, project_id, task_id, agent_id, backend,
                      status, attempt, started_at, last_event_at)
                   VALUES (?,?,?,?,?,?, 'pending', ?, ?, ?)
                   ON CONFLICT(interaction_id) DO UPDATE SET
                     attempt=excluded.attempt, status='pending',
                     started_at=excluded.started_at, last_event_at=excluded.last_event_at""",
                (interaction_id, kind, project_id, task_id, agent_id, backend, attempt, now, now),
            )
            if task_status and task_id:
                # 防御：不回滚已终态的任务（skill_review 等后台 interaction 不应改写）
                row = self._conn.execute(
                    "SELECT status FROM task WHERE project_id=? AND task_id=?", (project_id, task_id),
                ).fetchone()
                if row and row[0] == "completed":
                    pass
                else:
                    self._conn.execute(
                        "UPDATE task SET status=?, updated_at=? WHERE project_id=? AND task_id=?",
                        (task_status, now, project_id, task_id),
                    )

    def update_interaction(self, interaction_id: str, *, status: Optional[str] = None,
                          response_ref: Optional[str] = None, tokens: Optional[int] = None,
                          touch_event: bool = False, meta: Optional[dict] = None) -> None:
        sets: list[str] = []
        vals: list[Any] = []
        if status is not None:
            sets.append("status=?"); vals.append(status)
        if response_ref is not None:
            sets.append("response_ref=?"); vals.append(response_ref)
        if tokens is not None:
            sets.append("tokens=tokens+?"); vals.append(tokens)
        if touch_event:
            sets.append("last_event_at=?"); vals.append(_now())
        if meta is not None:
            sets.append("meta=?"); vals.append(_dumps(meta))
        if not sets:
            return
        vals.append(interaction_id)
        with self._conn:
            self._conn.execute(
                f"UPDATE interaction SET {', '.join(sets)} WHERE interaction_id=?", vals
            )

    def bump_interaction_tokens(self, interaction_id: str, tokens: int) -> None:
        """CLI step_finish 报会话累计 token；取 MAX 写入，避免与 finalize 重复累加。"""
        if tokens <= 0:
            return
        with self._conn:
            self._conn.execute(
                "UPDATE interaction SET tokens=MAX(COALESCE(tokens,0), ?) WHERE interaction_id=?",
                (tokens, interaction_id),
            )

    def get_interaction(self, interaction_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM interaction WHERE interaction_id=?", (interaction_id,)
        ).fetchone()
        return self._row(row) if row else None

    def list_interactions(self, project_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM interaction WHERE project_id=? ORDER BY started_at", (project_id,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_interactions_by_statuses(self, statuses: tuple) -> list[dict]:
        """按 status 集合列出 interaction（对账 / workspace GC 用）。"""
        if not statuses:
            return []
        placeholders = ",".join("?" * len(statuses))
        rows = self._conn.execute(
            f"SELECT * FROM interaction WHERE status IN ({placeholders})",
            statuses,
        ).fetchall()
        return [self._row(r) for r in rows]

    def tokens_total(self, project_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(tokens),0) FROM interaction WHERE project_id=?", (project_id,)
        ).fetchone()
        return int(row[0])

    def tokens_grouped(self, project_id: str, by: str) -> dict[str, int]:
        """token 汇总，by ∈ {'agent_id','task_id'}（D17 计量）。"""
        if by not in ("agent_id", "task_id"):
            raise ValueError("by 仅支持 agent_id / task_id")
        rows = self._conn.execute(
            f"SELECT {by}, COALESCE(SUM(tokens),0) FROM interaction "
            f"WHERE project_id=? GROUP BY {by}", (project_id,)
        ).fetchall()
        return {(r[0] or ""): int(r[1]) for r in rows}

    def append_run_event(self, interaction_id: str, kind: str,
                        payload: Optional[dict] = None) -> int:
        """追加事件（自动 seq）+ 冗余更新 interaction.last_event_at（看门狗读取便宜）。"""
        now = _now()
        with self._conn:
            cur = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0)+1 FROM run_event WHERE interaction_id=?",
                (interaction_id,),
            )
            seq = cur.fetchone()[0]
            self._conn.execute(
                "INSERT INTO run_event (interaction_id, seq, kind, payload, ts) VALUES (?,?,?,?,?)",
                (interaction_id, seq, kind, _dumps(payload), now),
            )
            self._conn.execute(
                "UPDATE interaction SET last_event_at=? WHERE interaction_id=?",
                (now, interaction_id),
            )
        return seq

    def list_run_events(self, interaction_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM run_event WHERE interaction_id=? ORDER BY seq", (interaction_id,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_project_events(self, project_id: str) -> list[dict]:
        """项目级事件流：聚合该项目所有 interaction 的 run_event，
        以及合成 id 事件（如 ``{pid}:budget`` / ``{pid}:cycle:N`` / ``{pid}:{tid}:blocked``），
        按时间排序。每条带交互归属（task_id/agent_id/interaction_kind）。
        """
        rows = self._conn.execute(
            "SELECT re.interaction_id AS interaction_id, re.id AS rid, re.kind AS kind, "
            "       re.payload AS payload, re.ts AS ts, "
            "       i.task_id AS task_id, i.agent_id AS agent_id, i.kind AS interaction_kind "
            "FROM run_event re "
            "LEFT JOIN interaction i ON re.interaction_id = i.interaction_id "
            "WHERE i.project_id = ? OR re.interaction_id LIKE ? "
            "ORDER BY re.ts, re.id",
            (project_id, f"{project_id}:%"),
        ).fetchall()
        return [{
            "ts": r["ts"], "kind": r["kind"], "payload": _loads(r["payload"]),
            "interaction_id": r["interaction_id"],
            "task_id": r["task_id"] or "", "agent_id": r["agent_id"] or "",
            "interaction_kind": r["interaction_kind"] or "",
        } for r in rows]

    # ── 投影轮询（R2-1a）──────────────

    # ── Job（R2-3）──────────────

    def create_job(self, project_id: str, pid: int = 0) -> str:
        job_id = f"job_{int(time.time())}_{project_id[:8]}"
        with self._conn:
            self._conn.execute(
                "INSERT INTO job (job_id, project_id, status, pid, started_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (job_id, project_id, "running", pid, _now(), _now())
            )
        return job_id

    def update_job_status(self, job_id: str, status: str, error: str = ""):
        self._conn.execute(
            "UPDATE job SET status=?, updated_at=?, error=? WHERE job_id=?",
            (status, _now(), error, job_id)
        )
        self._conn.commit()

    def get_latest_job(self, project_id: str):
        row = self._conn.execute(
            "SELECT * FROM job WHERE project_id=? ORDER BY rowid DESC LIMIT 1",
            (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, status: str = "") -> list[dict]:
        sql = "SELECT * FROM job"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def get_job(self, job_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM job WHERE job_id=?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def cancel_job_request(self, project_id: str) -> bool:
        self._conn.execute(
            "UPDATE job SET cancel_requested=1, updated_at=? WHERE project_id=?",
            (_now(), project_id)
        )
        self._conn.commit()
        return True

    # ── Agent Runtime（R2-3）──────────────

    def upsert_agent_runtime(self, agent_id: str, **kw):
        cols = ", ".join(kw.keys())
        vals = ", ".join("?" for _ in kw)
        self._conn.execute(
            f"INSERT OR REPLACE INTO agent_runtime (agent_id, {cols}) "
            f"VALUES (?, {vals})",
            (agent_id, *kw.values())
        )
        self._conn.commit()

    def get_agent_runtime(self, agent_id: str):
        row = self._conn.execute(
            "SELECT * FROM agent_runtime WHERE agent_id=?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_agent_runtimes(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM agent_runtime ORDER BY agent_id"
        ).fetchall()]

    # ── 投影轮询（R2-1a）──────────────

    def list_run_events_since(self, after_id: int = 0, limit: int = 200) -> list[dict]:
        """读取 run_event 表中 id > after_id 的行，按 id 升序。投影器轮询用。"""
        rows = self._conn.execute(
            "SELECT * FROM run_event WHERE id > ? ORDER BY id LIMIT ?",
            (after_id, limit)
        ).fetchall()
        return [self._row(r) for r in rows]

    def get_projection_checkpoint(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM projection_state WHERE key='run_event_last_id'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def set_projection_checkpoint(self, last_id: int):
        self._conn.execute(
            "REPLACE INTO projection_state (key, value) VALUES ('run_event_last_id', ?)",
            (str(last_id),)
        )
        self._conn.commit()

    # ── WorkspaceEvent（R2-1）──────────────

    def append_workspace_event(self, event: dict) -> str:
        """写入一条 WorkspaceEvent。返回 event id。"""
        eid = event.get("id") or f"evt_{int(time.time())}_{hash(json.dumps(event, sort_keys=True)) % 10000:04d}"
        def _json(v):
            return _dumps(v) if isinstance(v, (dict, list)) else (v or "{}")
        with self._conn:
            self._conn.execute(
                "INSERT INTO workspace_event (id, type, source, target, payload, metadata, visibility, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (eid, event["type"], event["source"], event.get("target", ""),
                 _json(event.get("payload")), _json(event.get("metadata")),
                 event.get("visibility", "project"), event.get("timestamp", _now()))
            )
        return eid

    def list_workspace_events(self, project_id: str = None, type: str = None,
                              limit: int = 50, before: str = None) -> list[dict]:
        """查询 WorkspaceEvent。支持按 project_id / type 过滤。"""
        sql = "SELECT * FROM workspace_event WHERE 1=1"
        params = []
        if project_id:
            sql += " AND json_extract(metadata, '$.project_id') = ?"
            params.append(project_id)
        if type:
            sql += " AND type = ?"
            params.append(type)
        if before:
            sql += " AND timestamp < ?"
            params.append(before)
        sql += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    # ── memory（KB SQLite 默认后端，详见 Phase 6）──────────────

    def memory_write(self, project_id: str, title: str, content: str, *,
                    task_id: str = "", tags: Optional[list] = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO memory (project_id, task_id, tags, title, content, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (project_id, task_id, _dumps(tags or []), title, content, _now()),
            )
            mid = cur.lastrowid
            if self._memory_fts:
                self._conn.execute(
                    "INSERT INTO memory_fts(rowid, title, content, project_id, tags) "
                    "VALUES (?,?,?,?,?)",
                    (mid, title or "", content or "", project_id or "",
                     _dumps(tags or [])),
                )
        return mid

    def memory_get(self, mem_id: int) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM memory WHERE id=?", (mem_id,)).fetchone()
        return self._mem_row(row) if row else None

    def memory_search(self, *, tags: Optional[list] = None, text: str = "",
                     project_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        q = (text or "").strip()
        if q and self._memory_fts and len(q) >= 2:
            tokens = [t for t in re.split(r"\s+", q) if len(t) >= 2]
            if not tokens:
                tokens = [q]
            if len(tokens) == 1:
                match_expr = '"' + tokens[0].replace('"', '""') + '"'
            else:
                match_expr = " OR ".join(
                    '"' + t.replace('"', '""') + '"' for t in tokens
                )
            sql = (
                "SELECT m.* FROM memory m JOIN memory_fts ON memory_fts.rowid=m.id "
                "WHERE memory_fts MATCH ?"
            )
            params: list = [match_expr]
            if project_id:
                sql += " AND m.project_id=?"
                params.append(project_id)
            sql += " ORDER BY rank LIMIT ?"
            params.append(max(1, limit))
            try:
                rows = self._conn.execute(sql, params).fetchall()
                out = [self._mem_row(r) for r in rows]
                if tags:
                    out = [d for d in out if set(tags) & set(d["tags"])]
                return out
            except sqlite3.OperationalError:
                pass
        rows = self._conn.execute("SELECT * FROM memory ORDER BY id DESC").fetchall()
        out = []
        for r in rows:
            d = self._mem_row(r)
            if project_id and d["project_id"] != project_id:
                continue
            if tags and not (set(tags) & set(d["tags"])):
                continue
            if q and q not in d["title"] and q not in d["content"]:
                tokens = [t for t in re.split(r"\s+", q) if t]
                if tokens:
                    hay = f"{d.get('title') or ''} {d.get('content') or ''}".lower()
                    if not all(t.lower() in hay for t in tokens):
                        continue
                else:
                    continue
            out.append(d)
            if len(out) >= limit:
                break
        return out

    def memory_update(
        self,
        mem_id: int,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[list] = None,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        row = self.memory_get(mem_id)
        if not row:
            return False
        new_title = title if title is not None else row.get("title") or ""
        new_content = content if content is not None else row.get("content") or ""
        new_tags = tags if tags is not None else row.get("tags") or []
        new_project = project_id if project_id is not None else row.get("project_id") or ""
        new_task = task_id if task_id is not None else row.get("task_id") or ""
        with self._conn:
            self._conn.execute(
                "UPDATE memory SET project_id=?, task_id=?, tags=?, title=?, content=? WHERE id=?",
                (new_project, new_task, _dumps(new_tags), new_title, new_content, mem_id),
            )
            if self._memory_fts:
                self._conn.execute("DELETE FROM memory_fts WHERE rowid=?", (mem_id,))
                self._conn.execute(
                    "INSERT INTO memory_fts(rowid, title, content, project_id, tags) "
                    "VALUES (?,?,?,?,?)",
                    (mem_id, new_title, new_content, new_project, _dumps(new_tags)),
                )
        return True

    def memory_delete(self, mem_id: int) -> bool:
        with self._conn:
            if self._memory_fts:
                self._conn.execute("DELETE FROM memory_fts WHERE rowid=?", (mem_id,))
            cur = self._conn.execute("DELETE FROM memory WHERE id=?", (mem_id,))
        return cur.rowcount > 0

    # ── conversation / message（对话记忆一等公民，P0）──────────

    def create_conversation(self, conversation_id: str, *, kind: str = "dm",
                            participants: Optional[list] = None,
                            project_id: Optional[str] = None, title: str = "",
                            meta: Optional[dict] = None) -> None:
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO conversation
                     (conversation_id, kind, participants, project_id, title,
                      created_at, updated_at, meta)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(conversation_id) DO NOTHING""",
                (conversation_id, kind, _dumps(participants or []), project_id, title,
                 now, now, _dumps(meta)),
            )

    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM conversation WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        if not row:
            return None
        d = self._row(row)
        d["participants"] = _loads(d.get("participants")) or []
        return d

    def list_all_conversations(self) -> list[dict]:
        """列出全部 conversation，按 updated_at 降序。"""
        rows = self._conn.execute(
            "SELECT * FROM conversation ORDER BY updated_at DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = self._row(r)
            d["participants"] = _loads(d.get("participants")) or []
            out.append(d)
        return out

    def get_or_create_dm(self, agent_id: str) -> str:
        """取/建一个人↔单 agent 的 DM 会话，返回 conversation_id。"""
        cid = f"dm:{agent_id}"
        self.create_conversation(cid, kind="dm", participants=["user", agent_id])
        return cid

    def update_conversation_meta(self, conversation_id: str, **kv) -> None:
        """合并写 conversation.meta（摘要 / summarized_through_seq / pins 等）。"""
        conv = self.get_conversation(conversation_id)
        meta = (conv.get("meta") if conv else None) or {}
        meta.update(kv)
        with self._conn:
            self._conn.execute(
                "UPDATE conversation SET meta=?, updated_at=? WHERE conversation_id=?",
                (_dumps(meta), _now(), conversation_id),
            )

    def append_message(self, conversation_id: str, role: str, author: str = "", *,
                       text: str = "", parts: Optional[list] = None, backend: str = "",
                       tokens: int = 0, meta: Optional[dict] = None) -> tuple[int, int]:
        """追加一条消息，返回 (id, seq)。seq 在会话内自增。"""
        with self._conn:
            seq = (self._conn.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM message WHERE conversation_id=?",
                (conversation_id,)).fetchone()[0])
            cur = self._conn.execute(
                """INSERT INTO message
                     (conversation_id, seq, role, author, text, parts, backend, tokens,
                      created_at, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (conversation_id, seq, role, author, text, _dumps(parts), backend, tokens,
                 _now(), _dumps(meta)),
            )
            mid = cur.lastrowid
            if self._fts and text:
                self._conn.execute(
                    "INSERT INTO message_fts(rowid, text, conversation_id) VALUES (?,?,?)",
                    (mid, text, conversation_id),
                )
            self._conn.execute(
                "UPDATE conversation SET updated_at=? WHERE conversation_id=?",
                (_now(), conversation_id),
            )
        return mid, seq

    def clear_conversation(self, conversation_id: str) -> int:
        """清空一个会话的全部消息（含 FTS 索引）+ 重置摘要/pins。返回删除的消息数。"""
        with self._conn:
            ids = [r[0] for r in self._conn.execute(
                "SELECT id FROM message WHERE conversation_id=?",
                (conversation_id,)).fetchall()]
            if self._fts and ids:
                self._conn.executemany(
                    "DELETE FROM message_fts WHERE rowid=?", [(i,) for i in ids])
            self._conn.execute(
                "DELETE FROM message WHERE conversation_id=?", (conversation_id,))
            self._conn.execute(
                "UPDATE conversation SET meta='null', updated_at=? WHERE conversation_id=?",
                (_now(), conversation_id))
        return len(ids)

    def get_message(self, message_id: int) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM message WHERE id=?", (message_id,)).fetchone()
        return self._msg_row(row) if row else None

    def count_messages(self, conversation_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM message WHERE conversation_id=?", (conversation_id,)
        ).fetchone()[0]

    def list_messages(self, conversation_id: str, *, after_seq: int = 0,
                      limit: Optional[int] = None) -> list[dict]:
        """按 seq 升序列出消息（after_seq 之后；limit 可选）。"""
        sql = "SELECT * FROM message WHERE conversation_id=? AND seq>? ORDER BY seq"
        params: list = [conversation_id, after_seq]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._msg_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def recent_messages(self, conversation_id: str, k: int) -> list[dict]:
        """最近 k 条消息，按 seq 升序返回（便于直接拼装）。"""
        if k <= 0:
            return []
        rows = self._conn.execute(
            "SELECT * FROM message WHERE conversation_id=? ORDER BY seq DESC LIMIT ?",
            (conversation_id, k),
        ).fetchall()
        return [self._msg_row(r) for r in reversed(rows)]

    def search_messages(self, query: str, *, conversation_id: Optional[str] = None,
                        limit: int = 5) -> list[dict]:
        """关键词检索消息正文。FTS5(trigram) 优先；不可用或异常时回退 LIKE。"""
        q = (query or "").strip()
        if not q:
            return []
        if self._fts and len(q) >= 3:
            match = '"' + q.replace('"', '""') + '"'
            sql = ("SELECT m.* FROM message m JOIN message_fts ON message_fts.rowid=m.id "
                   "WHERE message_fts MATCH ?")
            params: list = [match]
            if conversation_id:
                sql += " AND m.conversation_id=?"
                params.append(conversation_id)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            try:
                return [self._msg_row(r) for r in self._conn.execute(sql, params).fetchall()]
            except sqlite3.OperationalError:
                pass
        sql = "SELECT * FROM message WHERE text LIKE ?"
        params = [f"%{q}%"]
        if conversation_id:
            sql += " AND conversation_id=?"
            params.append(conversation_id)
        sql += " ORDER BY seq DESC LIMIT ?"
        params.append(limit)
        return [self._msg_row(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── 只读导出视图（task_data.json 形状）─────────────────────

    def export_project(self, project_id: str) -> dict:
        """把 SQLite 状态导成 task_data.json 兼容形状（只读视图、供查看/搬迁）。"""
        proj = self.get_project(project_id) or {"project_id": project_id}
        tasks = self.list_tasks(project_id)
        by_id = {t["task_id"]: t for t in tasks}
        tops: list[dict] = []
        for t in tasks:
            view = {
                "id": t["task_id"], "name": t["name"], "agent": t["agent"],
                "reviewer": t["reviewer"], "task_type": t["task_type"],
                "status": t["status"], "dependencies": t["dependencies"],
                "started_at": t["started_at"], "completed_at": t["completed_at"],
                "updated_at": t["updated_at"], "subtasks": [],
            }
            by_id[t["task_id"]]["_view"] = view
        for t in tasks:
            view = by_id[t["task_id"]]["_view"]
            if t["parent_id"] and t["parent_id"] in by_id:
                by_id[t["parent_id"]]["_view"]["subtasks"].append(view)
            else:
                tops.append(view)
        return {
            "project": {
                "id": project_id, "title": proj.get("title", ""),
                "mode": proj.get("mode", "one_shot"), "status": proj.get("status", "pending"),
            },
            "tasks": tops,
            "exported_at": _now(),
            "_source": "sqlite",
        }

    # ── 一次性导入器（迁移现有 task_data.json）─────────────────

    def import_task_data(self, project_id: str, data: Optional[dict] = None) -> dict:
        """把现有 task_data.json 导入 SQLite。返回导入计数。"""
        if data is None:
            from common.task_data_store import read_task_data
            data = read_task_data(project_id)
        proj = data.get("project", {}) or {}
        self.upsert_project(
            project_id, title=proj.get("title", proj.get("name", "")),
            mode=proj.get("mode", "one_shot"), status=proj.get("status", "pending"),
        )
        n_tasks = n_subs = 0
        for t in data.get("tasks", []):
            tid = t.get("id")
            if not tid:
                continue
            self._import_one(project_id, t, parent_id=None)
            n_tasks += 1
            for st in t.get("subtasks", []):
                if st.get("id"):
                    self._import_one(project_id, st, parent_id=tid)
                    n_subs += 1
        return {"tasks": n_tasks, "subtasks": n_subs}

    def _import_one(self, project_id: str, t: dict, parent_id: Optional[str]) -> None:
        self.upsert_task(
            project_id, t["id"], name=t.get("name", ""), agent=t.get("agent", ""),
            reviewer=t.get("reviewer", ""), task_type=t.get("task_type", ""),
            status=t.get("status", "pending"), dependencies=t.get("dependencies", []),
            parent_id=parent_id,
        )

    # ── 行转 dict ─────────────────────────────────────────────

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        if "meta" in d:
            d["meta"] = _loads(d["meta"])
        if "payload" in d:
            d["payload"] = _loads(d["payload"])
        return d

    @classmethod
    def _task_row(cls, row: sqlite3.Row) -> dict:
        d = cls._row(row)
        d["dependencies"] = _loads(d.get("dependencies")) or []
        return d

    @staticmethod
    def _mem_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["tags"] = _loads(d.get("tags")) or []
        return d

    @classmethod
    def _msg_row(cls, row: sqlite3.Row) -> dict:
        d = cls._row(row)
        d["parts"] = _loads(d.get("parts"))
        return d

    # ── publish_log / audit_log（Phase 3 运营持久化）────────────

    def insert_publish_log(self, project_id: str, *, task_id: str = "", platform: str = "",
                           deliverable: str = "", status: str = "completed",
                           meta: Optional[dict] = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO publish_log
                     (project_id, task_id, platform, deliverable, status, meta, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (project_id, task_id, platform, deliverable, status, _dumps(meta), _now()),
            )
            return int(cur.lastrowid)

    def list_publish_logs(self, project_id: str, *, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM publish_log WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [self._row(r) for r in rows]

    def insert_audit_log(self, project_id: str, *, task_id: str = "", audit_type: str = "geo",
                         deliverable: str = "", status: str = "completed",
                         meta: Optional[dict] = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO audit_log
                     (project_id, task_id, audit_type, deliverable, status, meta, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (project_id, task_id, audit_type, deliverable, status, _dumps(meta), _now()),
            )
            return int(cur.lastrowid)

    def list_audit_logs(self, project_id: str, *, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM audit_log WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [self._row(r) for r in rows]

    # ── agent_config / workflow_version（Phase 4 配置版本）──────

    def upsert_agent_config(self, agent_id: str, config: dict) -> int:
        row = self._conn.execute(
            "SELECT version FROM agent_config WHERE agent_id=?", (agent_id,)
        ).fetchone()
        ver = (int(row[0]) + 1) if row else 1
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO agent_config (agent_id, config, version, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                     config=excluded.config, version=excluded.version,
                     updated_at=excluded.updated_at""",
                (agent_id, _dumps(config), ver, now),
            )
        return ver

    def get_agent_config_row(self, agent_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM agent_config WHERE agent_id=?", (agent_id,)
        ).fetchone()
        return self._row(row) if row else None

    def save_workflow_version(self, workflow_id: str, body: dict) -> int:
        row = self._conn.execute(
            "SELECT MAX(version) FROM workflow_version WHERE workflow_id=?",
            (workflow_id,),
        ).fetchone()
        ver = int(row[0] or 0) + 1
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO workflow_version (workflow_id, version, body, updated_at)
                   VALUES (?,?,?,?)""",
                (workflow_id, ver, _dumps(body), now),
            )
        return ver


def _main(argv: list[str]) -> int:
    """只读导出 / 一次性导入 CLI（D13 透明性）。

    python store.py export <project_id> [--out file.json]
    python store.py import <project_id>            # 从 task_data.json 导入
    """
    import argparse

    parser = argparse.ArgumentParser(description="SQLite 真相库导出/导入")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("export"); pe.add_argument("project_id"); pe.add_argument("--out")
    pi = sub.add_parser("import"); pi.add_argument("project_id")
    args = parser.parse_args(argv)

    with Store() as s:
        if args.cmd == "export":
            view = s.export_project(args.project_id)
            text = json.dumps(view, ensure_ascii=False, indent=2)
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
                print(f"[store] 已导出：{args.out}")
            else:
                print(text)
        elif args.cmd == "import":
            counts = s.import_task_data(args.project_id)
            print(f"[store] 已导入 {args.project_id}：{counts}")
    return 0


if __name__ == "__main__":
    import sys as _sys

    from common.paths import ensure_team_importable
    ensure_team_importable()
    raise SystemExit(_main(_sys.argv[1:]))
