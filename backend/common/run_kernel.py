#!/usr/bin/env python3
"""新内核运行时入口（D10）—— 用真实 opencode Transport 驱动一个项目跑完整条流程。

这是单内核的可执行入口：组装 Store(真相库) + AgentPort(真实传输) + Process(状态机)，
按目标 goal 经 Main 决策 team_config / task_plan，再串行驱动 DAG（D11/D12/D14/D18）。
定位为旧 `task-executor` / `continuous-executor` 双引擎的统一替代执行入口。

用法：
    python run_kernel.py <project_id> --goal "目标..." [--mode one_shot|recurring]
                         [--title 标题] [--budget 100000]

依赖可注入（store/transport/watchdog/config），便于单测与换后端（claude）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):  # 作为脚本直接运行时确保 common 包可导入
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.agent_port import AgentPort, WatchdogConfig, reconcile_on_start
from common.process import Process, ProcessConfig, ProjectOutcome
from common.store import Store


def run_project(project_id: str, *, goal: str = "", title: str = "",
                mode: str = "one_shot", token_budget: Optional[int] = None,
                max_cycles: int = 3, review: bool = False, split: bool = False,
                backend: str = "opencode",
                store: Optional[Store] = None, transport=None,
                watchdog: Optional[WatchdogConfig] = None,
                config: Optional[ProcessConfig] = None) -> ProjectOutcome:
    """组装并运行新内核。transport/bbackend 缺省用真实 opencode（惰性导入，便于无依赖单测注入）。"""
    store = store or Store()
    reconcile_on_start(store)  # 启动对账 GC（D8）：清理上次残留的 pending/running
    if transport is None:
        from common.agent_transport import AdapterTransport
        transport = AdapterTransport(backend=backend)
    port = AgentPort(transport, store=store, config=watchdog or WatchdogConfig())
    proc = Process(store, port,
                   config or ProcessConfig(mode=mode, token_budget=token_budget,
                                           max_cycles=max_cycles, review_enabled=review,
                                           split_enabled=split,
                                           default_backend=backend))
    return proc.run(project_id, title=title, goal=goal)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="新内核运行时入口（Process + 真实 opencode）")
    p.add_argument("project_id")
    p.add_argument("--goal", default="", help="项目目标（驱动 team_config / task_plan）")
    p.add_argument("--title", default="")
    p.add_argument("--mode", choices=["one_shot", "recurring"], default="one_shot")
    p.add_argument("--budget", type=int, default=None, help="per-project token 硬上限")
    p.add_argument("--max-cycles", type=int, default=3, help="recurring 模式的周期上限")
    p.add_argument("--review", action="store_true",
                   help="开启同行评审（reviewer 由 main 在 task_plan 指派）")
    p.add_argument("--split", action="store_true",
                   help="开启派发前递归展开（evaluate；agent 按复杂度拆子任务）")
    p.add_argument("--backend", default="opencode", choices=["opencode", "claude"],
                   help="驱动 agent 的 CLI 后端（默认 opencode）")
    a = p.parse_args(argv)

    out = run_project(a.project_id, goal=a.goal, title=a.title,
                      mode=a.mode, token_budget=a.budget, max_cycles=a.max_cycles,
                      review=a.review, split=a.split, backend=a.backend)
    print(json.dumps({
        "project_id": out.project_id, "status": out.status,
        "tasks": {tid: {"status": o.status, "attempts": o.attempts, "reason": o.reason}
                  for tid, o in out.tasks.items()},
    }, ensure_ascii=False, indent=2))
    return 0 if out.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
