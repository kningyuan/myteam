"""WorkspaceEvent 投影器 — 轮询 Store.run_event → 映射为 WorkspaceEvent。

设计规格：docs/myteam-upgrade-design-spec.md §4.3 R2-1a

主路径：定时轮询（2s 间隔），非回调。
原因：run_kernel 是独立 subprocess，无法同步回调 Hub 进程。
"""

import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("workspace_events")


# run_event.kind → WorkspaceEvent.type 映射 + payload 构造
def _map_to_workspace_event(row: dict, project_id: str) -> Optional[dict]:
    kind = row.get("kind", "")
    payload = row.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    interaction_id = row.get("interaction_id", "")
    ts = row.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    base = {
        "source": "kernel/process",
        "target": f"channel/project-{project_id}",
        "metadata": json.dumps({"project_id": project_id}),
        "visibility": "project",
        "timestamp": ts,
    }

    # ── 任务生命周期 ──
    if kind == "step_start":
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.updated",
            "payload": json.dumps({"interaction_id": interaction_id, "status": "running"}),
        }

    if kind == "step_finish":
        tokens = payload.get("tokens", {}) if isinstance(payload, dict) else {}
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.updated",
            "payload": json.dumps({
                "interaction_id": interaction_id,
                "status": "awaiting_gate",
                "tokens": tokens,
            }),
        }

    # ── Gate 结果 ──
    if kind == "gate_passed":
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.gate.completed",
            "payload": json.dumps({
                "interaction_id": interaction_id,
                "gate_type": "execution",
                "result": "passed",
            }),
        }

    if kind == "gate_failed":
        failures = payload.get("failures", []) if isinstance(payload, dict) else []
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.gate.rejected",
            "payload": json.dumps({
                "interaction_id": interaction_id,
                "gate_type": "execution",
                "failures": failures,
            }),
        }

    # ── 任务阻塞/失败 ──
    if kind in ("blocked", "plan_rejected", "split_rejected"):
        reason = payload.get("reason", "") if isinstance(payload, dict) else str(payload)
        gate_type_map = {"plan_rejected": "plan", "split_rejected": "split", "blocked": "execution"}
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.blocked",
            "payload": json.dumps({
                "interaction_id": interaction_id,
                "reason": reason,
                "gate_type": gate_type_map.get(kind, "execution"),
            }),
        }

    # ── 项目生命周期 ──
    if kind == "cycle_done":
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.updated",
            "payload": json.dumps({"cycle": interaction_id, "status": "cycle_done"}),
        }

    if kind == "budget_alert":
        used = payload.get("used", 0) if isinstance(payload, dict) else 0
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "budget.threshold.reached",
            "payload": json.dumps({"used_pct": used, "alert": "warning"}),
        }

    if kind == "budget_over":
        used = payload.get("used", 0) if isinstance(payload, dict) else 0
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "budget.threshold.reached",
            "payload": json.dumps({"used_pct": used, "alert": "over"}),
        }

    # ── Watchdog ──
    if kind in ("watchdog_soft_idle", "watchdog_hard_kill"):
        idle_sec = payload.get("idle_sec", 0) if isinstance(payload, dict) else 0
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.blocked",
            "payload": json.dumps({
                "interaction_id": interaction_id,
                "reason": f"watchdog: {kind}",
                "idle_sec": idle_sec,
            }),
        }

    # ── Review ──
    if kind == "review_done":
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.updated",
            "payload": json.dumps({"interaction_id": interaction_id, "status": "review_done"}),
        }

    if kind == "review_unreachable":
        reason = payload.get("reason", "") if isinstance(payload, dict) else str(payload)
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.blocked",
            "payload": json.dumps({"interaction_id": interaction_id, "reason": reason}),
        }

    # ── 断点续跑 ──
    if kind == "resume_adopted":
        reason = payload.get("reason", "") if isinstance(payload, dict) else str(payload)
        return {
            **base,
            "id": f"evt_{ts}_{row['id']}",
            "type": "project.task.updated",
            "payload": json.dumps({"interaction_id": interaction_id, "status": "resumed", "reason": reason}),
        }

    # ── State snapshot（跳过，不投影） ──
    if kind in ("request_snapshot", "response_snapshot", "text", "tool_use", "tool_result"):
        return None

    # ── 未匹配 kind → 降级投影 ──
    return {
        **base,
        "id": f"evt_{ts}_{row['id']}",
        "type": "project.task.updated",
        "payload": json.dumps({"raw_kind": kind, "raw_payload": payload}),
    }


def _resolve_project_id(store, interaction_id: str) -> Optional[str]:
    """从 interaction_id 反查 project_id。"""
    if not interaction_id:
        return None
    prefix = interaction_id.split(":", 1)[0]
    if prefix:
        return prefix
    interaction = store.get_interaction(interaction_id)
    return interaction.get("project_id") if interaction else None


class ProjectionRunner:
    """轮询 Store.run_event → 转换为 WorkspaceEvent 写入。"""

    def __init__(self, store, poll_interval: float = 2.0):
        self.store = store
        self.poll_interval = poll_interval
        self._last_id = self.store.get_projection_checkpoint()

    async def poll_once(self) -> int:
        """单次轮询：读取未投影 run_event → 映射 → 写入 workspace_event。返回投影数。"""
        rows = self.store.list_run_events_since(after_id=self._last_id)
        count = 0
        for row in rows:
            project_id = _resolve_project_id(self.store, row.get("interaction_id", ""))
            if not project_id:
                continue
            ws_event = _map_to_workspace_event(row, project_id)
            if ws_event:
                try:
                    self.store.append_workspace_event(ws_event)
                    count += 1
                except Exception as e:
                    logger.error("append_workspace_event failed: %s", e)
            self._last_id = max(self._last_id, row["id"])
        if count:
            self.store.set_projection_checkpoint(self._last_id)
        return count

    async def start_polling(self):
        """启动轮询循环。"""
        while True:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error("ProjectionRunner poll error: %s", e)
            await asyncio.sleep(self.poll_interval)

    def project_all(self, project_id: str) -> int:
        """全量投影某项目的所有 run_event。用于 Hub 启动时补投。"""
        total = 0
        rows = self.store.list_run_events_since(after_id=0)
        for row in rows:
            pid = _resolve_project_id(self.store, row.get("interaction_id", ""))
            if pid == project_id:
                ws_event = _map_to_workspace_event(row, pid)
                if ws_event:
                    try:
                        self.store.append_workspace_event(ws_event)
                        total += 1
                    except Exception as e:
                        logger.error("project_all append failed: %s", e)
        return total