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
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from common.observability.audit_log import audit_enabled, audit_snapshot
from common.contracts import InteractionRequest, parse_request, validate_response_dict
from common.paths import response_dir, trigger_dir
from common.store.store import Store
from common.delivery.deliverable_guarantee import try_adopt_deliverable_response
from common.delivery.submit_result import _atomic_write_json
from common.observability.token_usage import StoreTokenUsageSink, TokenUsageSink


@dataclass
class WatchdogConfig:
    soft_idle_sec: float = 120.0   # 无事件超此 = 疑似卡死（标记+告警）
    hard_idle_sec: float = 300.0   # 无事件超此 = 取消 + 重试
    poll_interval: float = 0.5
    max_attempts: int = 3
    kind_soft_idle: dict[str, float] = field(default_factory=dict)
    kind_hard_idle: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 环境变量可覆盖阈值，便于运行时绕过而不改代码
        self.soft_idle_sec = float(os.environ.get("MYTEAM_SOFT_IDLE_SEC", str(self.soft_idle_sec)))
        self.hard_idle_sec = float(os.environ.get("MYTEAM_HARD_IDLE_SEC", str(self.hard_idle_sec)))

    def idle_limits(self, kind: str) -> tuple[float, float]:
        hard = self.kind_hard_idle.get(kind, self.hard_idle_sec)
        soft = self.kind_soft_idle.get(kind, min(hard * 0.4, max(hard - 60.0, self.soft_idle_sec)))
        return soft, hard


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

from common.agent.agent_execution import lock_for as _lock_for


class AgentPort:
    def __init__(self, transport: Transport, store: Optional[Store] = None,
                 config: Optional[WatchdogConfig] = None,
                 budget_checker: Optional[Callable[[str], bool]] = None,
                 token_sink: Optional[TokenUsageSink] = None):
        self.transport = transport
        self.store = store or Store()
        self.config = config or WatchdogConfig()
        self.budget_checker = budget_checker
        self._token_sink = token_sink or StoreTokenUsageSink(self.store)

    # ── 路径（文件=缓存，按 interaction_id 命名，D12）─────────

    def request_path(self, req: InteractionRequest) -> Path:
        return trigger_dir(req.agent_id) / f"{req.interaction_id}.request"

    def response_path(self, req: InteractionRequest) -> Path:
        return response_dir(req.agent_id) / f"{req.interaction_id}.response"

    # ── 入口：同步阻塞 + 有限重试（hard_idle 触发重试）─────────

    def run(self, request) -> AgentPortResult:
        if isinstance(request, dict):
            request = parse_request(request)
        agent_id = request.agent_id or ""
        with _lock_for(agent_id):
            last = AgentPortResult("error", None, request.interaction_id, 0, "未执行")
            for attempt in range(1, self.config.max_attempts + 1):
                last = self._attempt(request, attempt)
                if last.status in ("done", "error", "budget_exceeded", "cancelled"):
                    return last
                # timed_out / no_response → 继续重试（D12：hard_idle 或 CLI 早退未 submit）
            return last

    def _attempt(self, req: InteractionRequest, attempt: int) -> AgentPortResult:
        iid = req.interaction_id
        req_path = self.request_path(req)
        resp_path = self.response_path(req)

        # 派发前清旧文件（D12 残留治理）
        self._unlink(req_path)
        self._unlink(resp_path)

        # store 真相：建/刷新 interaction（顺带把 task 置 in_progress）
        # 注意：skill_review/review 等后台复盘 interaction 不应回滚 task 终态
        task_status: Optional[str] = None
        if req.task_id and req.kind in ("execute", "plan", "evaluate", "triage"):
            task_status = "in_progress"
        self.store.create_interaction(
            iid, req.kind, req.project_id, task_id=req.task_id,
            agent_id=req.agent_id, attempt=attempt,
            task_status=task_status,
        )

        # 写请求文件（原子）
        req_dict = json.loads(req.model_dump_json())
        _atomic_write_json(req_dict, req_path)
        req_mtime = req_path.stat().st_mtime
        if audit_enabled():
            self.store.append_run_event(iid, "request_snapshot", audit_snapshot(
                "request", req_dict,
                interaction_id=iid,
                agent_id=req.agent_id,
                outcome="dispatched",
                request_path=str(req_path),
            ))

        # 事件队列 + 传输线程（事件在子线程产生，store 写入只在本线程，避免跨线程 sqlite）
        q: "queue.Queue[tuple[str, Optional[dict]]]" = queue.Queue()
        ctx = DeliveryContext(req, req_path, lambda k, p=None: q.put((k, p)))
        if req.project_id:
            from common.project.project_cancel import cancel_registry
            cancel_registry.attach(req.project_id, ctx)
        th = threading.Thread(target=self._safe_transport, args=(ctx, q), daemon=True)
        th.start()

        last_event = time.monotonic()
        running = False
        soft_warned = False
        event_tokens = 0
        token_acc = {"running": 0}
        cli_error: Optional[str] = None
        cfg = self.config
        soft_idle, hard_idle = cfg.idle_limits(req.kind or "")

        while True:
            drained, tok, err = self._drain(q, iid, token_acc)
            if err:
                cli_error = err
            event_tokens = max(event_tokens, tok)
            if drained:
                last_event = time.monotonic()
                if not running:
                    running = True
                    self.store.update_interaction(iid, status="running")

            # L3：交互进行中 token 硬停（由 run_kernel 注入 checker）
            if self.budget_checker and req.project_id and self.budget_checker(req.project_id):
                ctx._cancel.set()
                th.join(timeout=5.0)
                self.store.append_run_event(iid, "budget_exceeded", {})
                self.store.update_interaction(iid, status="failed")
                return AgentPortResult("budget_exceeded", None, iid, attempt,
                                       "交互中 token 超预算硬停")

            resp = self._read_valid_response(resp_path, iid, req_mtime)
            if resp is not None:
                # 响应先落盘时 CLI 往往仍在收尾；须等传输线程自然结束以读出 result 行的
                # step_finish（过早 cancel 会杀掉进程，导致 tokens 恒 0）。
                finish_deadline = time.monotonic() + float(
                    os.environ.get("MYTEAM_RESPONSE_FINISH_SEC", "30"))
                while th.is_alive() and time.monotonic() < finish_deadline:
                    _, tok, err = self._drain(q, iid, token_acc)
                    if err:
                        cli_error = err
                    event_tokens = max(event_tokens, tok)
                    time.sleep(0.05)
                if th.is_alive():
                    ctx._cancel.set()
                    th.join(timeout=5.0)
                else:
                    th.join(timeout=1.0)
                _, tok, err = self._drain(q, iid, token_acc)
                if err:
                    cli_error = err
                event_tokens = max(event_tokens, tok)
                self._finalize_done(iid, resp_path, resp, event_tokens)
                return AgentPortResult("done", resp, iid, attempt)

            if not th.is_alive():
                # 传输结束：再排空一次队列 + 看一眼响应文件
                _, tok, err = self._drain(q, iid, token_acc)
                if err:
                    cli_error = err
                event_tokens = max(event_tokens, tok)
                resp = self._read_valid_response(resp_path, iid, req_mtime)
                if resp is not None:
                    self._finalize_done(iid, resp_path, resp, event_tokens)
                    return AgentPortResult("done", resp, iid, attempt)
                adopted = self._try_adopt_deliverable(req, resp_path, req_mtime, iid)
                if adopted is not None:
                    self._finalize_done(iid, resp_path, adopted, event_tokens)
                    return AgentPortResult("done", adopted, iid, attempt)
                self.store.update_interaction(iid, status="failed")
                if cli_error:
                    return AgentPortResult("error", None, iid, attempt, cli_error)
                return AgentPortResult("no_response", None, iid, attempt,
                                       "传输结束但未取回合法响应")

            if req.project_id:
                from common.project.project_cancel import cancel_registry
                if cancel_registry.is_cancelled(req.project_id):
                    ctx._cancel.set()
                    th.join(timeout=5.0)
                    self.store.update_interaction(iid, status="cancelled")
                    return AgentPortResult("cancelled", None, iid, attempt, "项目已取消")

            idle = time.monotonic() - last_event
            if idle >= hard_idle:
                adopted = self._try_adopt_deliverable(req, resp_path, req_mtime, iid)
                if adopted is not None:
                    ctx._cancel.set()
                    th.join(timeout=5.0)
                    self._finalize_done(iid, resp_path, adopted, event_tokens)
                    return AgentPortResult("done", adopted, iid, attempt)
                ctx._cancel.set()
                self.store.append_run_event(iid, "watchdog_hard_kill", {"idle_sec": round(idle, 1)})
                self.store.update_interaction(iid, status="timed_out")
                agent_label = self._interaction_agent_label(iid)
                print(f"  ✖ agent「{agent_label}」无响应超过 {hard_idle:.0f}s，将终止并重试")
                return AgentPortResult("timed_out", None, iid, attempt, "hard_idle 看门狗取消")
            if idle >= soft_idle and not soft_warned:
                soft_warned = True
                self.store.append_run_event(iid, "watchdog_soft_idle", {"idle_sec": round(idle, 1)})
                agent_label = self._interaction_agent_label(iid)
                print(f"  ⚠ agent「{agent_label}」已 {idle:.0f}s 无响应（阈值 {soft_idle:.0f}s），仍在等待...")

            time.sleep(cfg.poll_interval)

    # ── 内部 ─────────────────────────────────────────────────

    def _safe_transport(self, ctx: DeliveryContext, q: "queue.Queue") -> None:
        try:
            self.transport(ctx)
        except Exception as e:  # 传输异常归一为一个事件，主循环据此收尾
            q.put(("transport_error", {"message": str(e), "error": str(e)}))

    def _interaction_agent_label(self, iid: str) -> str:
        inter = self.store.get_interaction(iid)
        if inter:
            return inter.get("agent_id", "?")
        return "?"

    def _drain(self, q: "queue.Queue", iid: str,
               token_acc: Optional[dict] = None) -> tuple[bool, int, Optional[str]]:
        """排空事件入库；返回 (是否有事件, 当前会话 token 累计, 最近 CLI error 消息)。

        - cumulative=True（默认，opencode / claude result）：step_finish 报会话累计 total → MAX。
        - cumulative=False（claude per-message assistant.usage）：Σ input + Σ output 累加。
        """
        if token_acc is None:
            token_acc = {"running": 0}
        drained = False
        tokens = 0
        cli_error: Optional[str] = None
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            self.store.append_run_event(iid, kind, payload)
            drained = True
            if kind in ("error", "transport_error") and isinstance(payload, dict):
                cli_error = payload.get("message") or payload.get("error") or str(payload)
            if kind in ("step_finish", "step-finish") and isinstance(payload, dict):
                running = _apply_step_finish_tokens(payload, token_acc)
                tokens = max(tokens, running)
                if running > 0:
                    inter = self.store.get_interaction(iid) or {}
                    self._token_sink.record_usage(
                        inter.get("project_id", ""),
                        iid,
                        running,
                        agent_id=inter.get("agent_id", ""),
                        backend=inter.get("backend", ""),
                    )
        return drained, tokens, cli_error

    def _read_valid_response(self, resp_path: Path, iid: str, req_mtime: float) -> Optional[dict]:
        return _parse_adoptable_response(resp_path, iid, req_mtime)

    def _try_adopt_deliverable(self, req: InteractionRequest, resp_path: Path,
                               req_mtime: float, iid: str) -> Optional[dict]:
        """交付物保证：agent 写了文件但未 submit_result 时代采纳。"""
        try:
            adopted = try_adopt_deliverable_response(req, resp_path, req_mtime)
        except Exception:
            return None
        if adopted is None:
            return None
        self.store.append_run_event(iid, "deliverable_adopted",
                                    {"path": (req.input or {}).get("deliverable_path", "")})
        return adopted

    def _finalize_done(self, iid: str, resp_path: Path, resp: dict,
                       event_tokens: int = 0) -> None:
        finalize_interaction(
            self.store, iid, resp_path, resp, event_tokens,
            token_sink=self._token_sink,
        )

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _token_dict_increment(tok: dict) -> int:
    if not isinstance(tok, dict):
        return 0
    inp = tok.get("input") or tok.get("input_tokens") or tok.get("inputTokens") or 0
    out = tok.get("output") or tok.get("output_tokens") or tok.get("outputTokens") or 0
    if isinstance(inp, (int, float)) and isinstance(out, (int, float)):
        return int(inp) + int(out)
    return 0


def _apply_step_finish_tokens(payload: dict, token_acc: dict) -> int:
    """按 cumulative 标志更新 running 累计并返回当前总值。"""
    cumulative = payload.get("cumulative", True)
    if cumulative:
        t = _extract_tokens(payload)
        token_acc["running"] = max(token_acc.get("running", 0), t)
    else:
        tok = payload.get("tokens") or {}
        inc = _token_dict_increment(tok) or _extract_tokens(payload)
        token_acc["running"] = token_acc.get("running", 0) + inc
    return token_acc.get("running", 0)


def _extract_tokens(payload: dict) -> int:
    """从 step_finish 事件提取累计 token 数（兼容若干常见形态）。

    - opencode：``{"tokens": {"input":..,"output":..,"total":N}}`` → 取 total。
    - Claude result：仅 input/output 无 total → input + output。
    - 简化形态：``{"tokens": N}`` / ``{"total_tokens": N}`` / ``{"usage": {...}}``。
    """
    v = payload.get("tokens")
    if isinstance(v, dict):
        t = v.get("total") or v.get("total_tokens") or v.get("totalTokens")
        if isinstance(t, (int, float)):
            return int(t)
        inc = _token_dict_increment(v)
        if inc > 0:
            return inc
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
        inc = _token_dict_increment(usage)
        if inc > 0:
            return inc
    return 0


def _parse_adoptable_response(resp_path: Path, iid: str, req_mtime: float) -> Optional[dict]:
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


def read_adoptable_response(agent_id: str, interaction_id: str) -> tuple[Optional[dict], Optional[Path]]:
    """从 agent workspace 读取可采纳的孤儿响应（进程中断后的回收入口）。"""
    req_path = trigger_dir(agent_id) / f"{interaction_id}.request"
    resp_path = response_dir(agent_id) / f"{interaction_id}.response"
    req_mtime = req_path.stat().st_mtime if req_path.exists() else 0.0
    data = _parse_adoptable_response(resp_path, interaction_id, req_mtime)
    if data is None:
        return None, None
    return data, resp_path


def finalize_interaction(store: Store, interaction_id: str, resp_path: Path, resp: dict,
                         event_tokens: int = 0,
                         token_sink: Optional[TokenUsageSink] = None) -> None:
    """把合法响应写入 store 真相（interaction=done）。"""
    meta = resp.get("meta") or {}
    meta_tokens = meta.get("tokens") if isinstance(meta, dict) else None
    tokens = event_tokens if event_tokens > 0 else (
        meta_tokens if isinstance(meta_tokens, int) else 0)
    if tokens > 0:
        sink = token_sink or StoreTokenUsageSink(store)
        inter = store.get_interaction(interaction_id) or {}
        sink.record_usage(
            inter.get("project_id", ""),
            interaction_id,
            tokens,
            agent_id=inter.get("agent_id", ""),
            backend=inter.get("backend", ""),
        )
    store.update_interaction(
        interaction_id, status="done", response_ref=str(resp_path),
    )
    if audit_enabled():
        inter = store.get_interaction(interaction_id) or {}
        result = resp.get("result") if isinstance(resp, dict) else {}
        outcome = result.get("outcome") if isinstance(result, dict) else {}
        outcome_kind = outcome.get("kind") if isinstance(outcome, dict) else ""
        store.append_run_event(interaction_id, "response_snapshot", audit_snapshot(
            "response", resp,
            interaction_id=interaction_id,
            agent_id=inter.get("agent_id", ""),
            outcome=resp.get("status") or "unknown",
            outcome_kind=outcome_kind or "",
            response_path=str(resp_path),
        ))


def _reconcile_rows(store: Store, rows, *, adopted_kind: str, timed_out_kind: str,
                    adopted_reason: str, timed_out_reason: str) -> dict[str, int]:
    adopted = timed_out = 0
    for r in rows:
        iid = r["interaction_id"]
        agent = r["agent_id"] or ""
        resp, resp_path = read_adoptable_response(agent, iid)
        if resp is not None and resp_path is not None:
            finalize_interaction(store, iid, resp_path, resp)
            store.append_run_event(iid, adopted_kind, {"reason": adopted_reason})
            adopted += 1
        else:
            store.update_interaction(iid, status="timed_out")
            store.append_run_event(iid, timed_out_kind, {"reason": timed_out_reason})
            timed_out += 1
    return {"adopted": adopted, "timed_out": timed_out}


def reconcile_on_start(store: Optional[Store] = None) -> dict[str, int]:
    """启动对账 GC（D8/D12）：优先回收磁盘孤儿响应；无响应才标 timed_out。

    覆盖 pending/running/timed_out：timed_out 但磁盘有合法响应时先采纳，避免
    后续 gc_workspace 删掉 .response 导致断点续跑无法结算。
    """
    store = store or Store()
    rows = store.list_interactions_by_statuses(("pending", "running", "timed_out"))
    return _reconcile_rows(
        store, rows,
        adopted_kind="reconcile_adopted", timed_out_kind="reconcile_timed_out",
        adopted_reason="磁盘响应回收", timed_out_reason="进程重启对账",
    )
