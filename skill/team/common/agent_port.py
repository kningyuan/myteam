#!/usr/bin/env python3
"""AgentPort — 把一次 Interaction 投递给 Agent 并取回合法结果（D12 / D7 / D8）。

定位（D12）：
  - 同步阻塞 `run(InteractionRequest) -> AgentPortResult`，**串行**（同一时刻一个 interaction）。
  - 文件做缓存/传输（请求写 .trigger、结果写 .response），**store 做真相**（D13）。
  - 混合取回：事件流负责「存活 + 计量」；最终结果由 Agent 侧 submit_result 校验后原子写 .response。
  - 两段式看门狗（D7）：首个事件=已送达+存活；soft_idle 疑似卡死（标记+告警）；hard_idle 取消+重试。
  - 幂等/残留治理（D8）：按 interaction_id 命名；响应须 interaction_id 匹配且 mtime 晚于请求；
    派发前清旧文件；启动对账 GC。

传输方式可注入（Transport = Callable[[DeliveryContext], None]），便于测试与多后端（opencode/claude）。
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from common.contracts import InteractionRequest, parse_request, validate_response_dict
from common.paths import response_dir, trigger_dir
from common.store import Store
from common.submit_result import _atomic_write_json


@dataclass
class WatchdogConfig:
    soft_idle_sec: float = 120.0   # 无事件超此 = 疑似卡死（标记+告警）
    hard_idle_sec: float = 300.0   # 无事件超此 = 取消 + 重试
    poll_interval: float = 0.5
    max_attempts: int = 3


@dataclass
class AgentPortResult:
    status: str               # done | timed_out | no_response | error
    response: Optional[dict]  # 合法响应信封（done 时非空）
    interaction_id: str
    attempt: int
    reason: str = ""


class DeliveryContext:
    """投递上下文：传给 Transport，提供事件回传与取消信号。"""

    def __init__(self, request: InteractionRequest, request_path: Path,
                 emit: Callable[[str, Optional[dict]], None]):
        self.request = request
        self.request_path = request_path
        self._emit = emit
        self._cancel = threading.Event()

    def emit(self, kind: str, payload: Optional[dict] = None) -> None:
        """线程安全地回传一个事件（心跳/token/...）。"""
        self._emit(kind, payload)

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def cancel_event(self) -> threading.Event:
        """供适配器（如 opencode）订阅取消信号。"""
        return self._cancel


# Transport 协议：阻塞执行一次投递；通过 ctx.emit 回传事件；Agent 自行写 .response。
Transport = Callable[[DeliveryContext], None]


class AgentPort:
    def __init__(self, transport: Transport, store: Optional[Store] = None,
                 config: Optional[WatchdogConfig] = None):
        self.transport = transport
        self.store = store or Store()
        self.config = config or WatchdogConfig()

    # ── 路径（文件=缓存，按 interaction_id 命名，D12）─────────

    def request_path(self, req: InteractionRequest) -> Path:
        return trigger_dir(req.agent_id) / f"{req.interaction_id}.request"

    def response_path(self, req: InteractionRequest) -> Path:
        return response_dir(req.agent_id) / f"{req.interaction_id}.response"

    # ── 入口：同步阻塞 + 有限重试（hard_idle 触发重试）─────────

    def run(self, request) -> AgentPortResult:
        if isinstance(request, dict):
            request = parse_request(request)
        last = AgentPortResult("error", None, request.interaction_id, 0, "未执行")
        for attempt in range(1, self.config.max_attempts + 1):
            last = self._attempt(request, attempt)
            if last.status in ("done", "no_response", "error"):
                return last
            # timed_out → 继续重试（D12：hard_idle 取消 + 重试）
        return last

    def _attempt(self, req: InteractionRequest, attempt: int) -> AgentPortResult:
        iid = req.interaction_id
        req_path = self.request_path(req)
        resp_path = self.response_path(req)

        # 派发前清旧文件（D12 残留治理）
        self._unlink(req_path)
        self._unlink(resp_path)

        # store 真相：建/刷新 interaction（顺带把 task 置 in_progress）
        self.store.create_interaction(
            iid, req.kind, req.project_id, task_id=req.task_id,
            agent_id=req.agent_id, attempt=attempt,
            task_status="in_progress" if req.task_id else None,
        )

        # 写请求文件（原子）
        _atomic_write_json(json.loads(req.model_dump_json()), req_path)
        req_mtime = req_path.stat().st_mtime

        # 事件队列 + 传输线程（事件在子线程产生，store 写入只在本线程，避免跨线程 sqlite）
        q: "queue.Queue[tuple[str, Optional[dict]]]" = queue.Queue()
        ctx = DeliveryContext(req, req_path, lambda k, p=None: q.put((k, p)))
        th = threading.Thread(target=self._safe_transport, args=(ctx, q), daemon=True)
        th.start()

        last_event = time.time()
        running = False
        soft_warned = False
        event_tokens = 0
        cfg = self.config

        while True:
            drained, tok = self._drain(q, iid)
            event_tokens = max(event_tokens, tok)
            if drained:
                last_event = time.time()
                if not running:
                    running = True
                    self.store.update_interaction(iid, status="running")

            resp = self._read_valid_response(resp_path, iid, req_mtime)
            if resp is not None:
                ctx._cancel.set()
                _, tok = self._drain(q, iid)  # 收尾排空已入队事件
                event_tokens = max(event_tokens, tok)
                self._finalize_done(iid, resp_path, resp, event_tokens)
                return AgentPortResult("done", resp, iid, attempt)

            if not th.is_alive():
                # 传输结束：再排空一次队列 + 看一眼响应文件
                _, tok = self._drain(q, iid)
                event_tokens = max(event_tokens, tok)
                resp = self._read_valid_response(resp_path, iid, req_mtime)
                if resp is not None:
                    self._finalize_done(iid, resp_path, resp, event_tokens)
                    return AgentPortResult("done", resp, iid, attempt)
                self.store.update_interaction(iid, status="failed")
                return AgentPortResult("no_response", None, iid, attempt,
                                       "传输结束但未取回合法响应")

            idle = time.time() - last_event
            if idle >= cfg.hard_idle_sec:
                ctx._cancel.set()
                self.store.append_run_event(iid, "watchdog_hard_kill", {"idle_sec": round(idle, 1)})
                self.store.update_interaction(iid, status="timed_out")
                return AgentPortResult("timed_out", None, iid, attempt, "hard_idle 看门狗取消")
            if idle >= cfg.soft_idle_sec and not soft_warned:
                soft_warned = True
                self.store.append_run_event(iid, "watchdog_soft_idle", {"idle_sec": round(idle, 1)})

            time.sleep(cfg.poll_interval)

    # ── 内部 ─────────────────────────────────────────────────

    def _safe_transport(self, ctx: DeliveryContext, q: "queue.Queue") -> None:
        try:
            self.transport(ctx)
        except Exception as e:  # 传输异常归一为一个事件，主循环据此收尾
            q.put(("transport_error", {"error": str(e)}))

    def _drain(self, q: "queue.Queue", iid: str) -> tuple[bool, int]:
        """排空事件入库；返回 (是否有事件, 本次见到的最大 step_finish 累计 token)。

        opencode 的 step_finish 报的是**会话累计** total（单调递增），故取 max 而非求和。
        """
        drained = False
        tokens = 0
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            self.store.append_run_event(iid, kind, payload)
            drained = True
            if kind in ("step_finish", "step-finish") and isinstance(payload, dict):
                tokens = max(tokens, _extract_tokens(payload))
        return drained, tokens

    def _read_valid_response(self, resp_path: Path, iid: str, req_mtime: float) -> Optional[dict]:
        """只采纳：存在 + mtime 晚于请求 + 合法信封 + interaction_id 匹配（D12 防残留误用）。"""
        if not resp_path.exists():
            return None
        try:
            if resp_path.stat().st_mtime < req_mtime:
                return None
            data = json.loads(resp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        ok, _model, _errs = validate_response_dict(data)
        if not ok:
            return None
        if data.get("interaction_id") != iid:
            return None
        return data

    def _finalize_done(self, iid: str, resp_path: Path, resp: dict,
                       event_tokens: int = 0) -> None:
        # 计量优先级：适配器 step_finish 累计 > 响应 meta.tokens（D17）。
        meta = resp.get("meta") or {}
        meta_tokens = meta.get("tokens") if isinstance(meta, dict) else None
        tokens = event_tokens if event_tokens > 0 else (
            meta_tokens if isinstance(meta_tokens, int) else None)
        self.store.update_interaction(
            iid, status="done", response_ref=str(resp_path), tokens=tokens,
        )

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _extract_tokens(payload: dict) -> int:
    """从 step_finish 事件提取累计 token 数（兼容若干常见形态）。

    - opencode：``{"tokens": {"input":..,"output":..,"total":N}}`` → 取 total。
    - 简化形态：``{"tokens": N}`` / ``{"total_tokens": N}`` / ``{"usage": {...}}``。
    """
    v = payload.get("tokens")
    if isinstance(v, dict):
        t = v.get("total") or v.get("total_tokens") or v.get("totalTokens")
        if isinstance(t, (int, float)):
            return int(t)
    if isinstance(v, (int, float)):
        return int(v)
    for key in ("total_tokens", "totalTokens"):
        x = payload.get(key)
        if isinstance(x, (int, float)):
            return int(x)
    usage = payload.get("usage")
    if isinstance(usage, dict):
        x = usage.get("total_tokens") or usage.get("totalTokens") or usage.get("total")
        if isinstance(x, (int, float)):
            return int(x)
    return 0


def reconcile_on_start(store: Optional[Store] = None) -> int:
    """启动对账 GC（D8/D12）：进程重启后，把卡在 pending/running 的 interaction 标 timed_out。

    返回被对账的条数。
    """
    store = store or Store()
    rows = store._conn.execute(
        "SELECT interaction_id FROM interaction WHERE status IN ('pending','running')"
    ).fetchall()
    for r in rows:
        store.update_interaction(r["interaction_id"], status="timed_out")
        store.append_run_event(r["interaction_id"], "reconcile_timed_out",
                               {"reason": "进程重启对账"})
    return len(rows)
