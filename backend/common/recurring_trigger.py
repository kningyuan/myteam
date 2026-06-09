#!/usr/bin/env python3
"""R-K16：外部 recurring 触发入口。

本模块不是常驻调度器；cron / webhook bridge 只需调用本脚本或
`trigger_recurring()`，由内核执行一次 recurring tick（默认 1 cycle）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional


Runner = Callable[..., Any]


def _read_payload(path: str) -> dict:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload 必须是 JSON object")
    return data


def normalize_trigger(payload: dict) -> dict:
    """把 cron/webhook payload 归一成 run_project 参数。"""
    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id 必填")
    max_cycles = int(payload.get("max_cycles") or 1)
    if max_cycles < 1:
        raise ValueError("max_cycles 必须 >= 1")
    budget = payload.get("token_budget", payload.get("budget"))
    return {
        "project_id": project_id,
        "goal": str(payload.get("goal") or ""),
        "title": str(payload.get("title") or ""),
        "token_budget": int(budget) if budget is not None else None,
        "max_cycles": max_cycles,
        "review": bool(payload.get("review")),
        "split": bool(payload.get("split")),
        "workflow": payload.get("workflow") or None,
        "backend": payload.get("backend") or None,
    }


def trigger_recurring(payload: dict, *, runner: Optional[Runner] = None):
    """由外部触发一次 recurring run。

    默认只跑 1 cycle，避免 cron 高频触发时一次调用占用过久；需要连续多周期时
    可显式传 `max_cycles`。
    """
    args = normalize_trigger(payload)
    runner = runner or _default_runner()
    return runner(
        args["project_id"],
        goal=args["goal"],
        title=args["title"],
        mode="recurring",
        token_budget=args["token_budget"],
        max_cycles=args["max_cycles"],
        review=args["review"],
        split=args["split"],
        workflow=args["workflow"],
        backend=args["backend"],
    )


def _default_runner() -> Runner:
    from common.run_kernel import run_project

    return run_project


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="R-K16 外部 recurring 触发入口（cron/webhook bridge）",
    )
    p.add_argument("--payload", help="JSON payload 文件路径；'-' 表示 stdin")
    p.add_argument("--project-id")
    p.add_argument("--goal", default="")
    p.add_argument("--title", default="")
    p.add_argument("--budget", type=int, default=None)
    p.add_argument("--max-cycles", type=int, default=1)
    p.add_argument("--workflow", default=None)
    p.add_argument("--backend", choices=["opencode", "claude"], default=None)
    p.add_argument("--review", action="store_true")
    p.add_argument("--split", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _read_payload(args.payload) if args.payload else {
            "project_id": args.project_id,
            "goal": args.goal,
            "title": args.title,
            "budget": args.budget,
            "max_cycles": args.max_cycles,
            "workflow": args.workflow,
            "backend": args.backend,
            "review": args.review,
            "split": args.split,
        }
        outcome = trigger_recurring(payload)
    except Exception as e:
        print(f"❌ recurring trigger 失败：{e}", file=sys.stderr)
        return 1
    print(json.dumps({
        "project_id": outcome.project_id,
        "status": outcome.status,
        "tasks": {tid: {"status": t.status, "attempts": t.attempts, "reason": t.reason}
                  for tid, t in outcome.tasks.items()},
    }, ensure_ascii=False, indent=2))
    return 0 if outcome.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
