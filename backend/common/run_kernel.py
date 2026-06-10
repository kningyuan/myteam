#!/usr/bin/env python3
"""新内核运行时入口（D10）—— 用真实 opencode Transport 驱动一个项目跑完整条流程。

这是单内核的可执行入口：组装 Store(真相库) + AgentPort(真实传输) + Process(状态机)，
按目标 goal 经 Main 决策 team_config / task_plan，再串行驱动 DAG（D11/D12/D14/D18）。
定位为旧 `task-executor` / `continuous-executor` 双引擎的统一替代执行入口。

用法：
    python run_kernel.py <project_id> --goal "目标..." [--mode one_shot|recurring]
                         [--title 标题] [--budget 100000]
    python run_kernel.py --demo          # 快速启动 demo
    python run_kernel.py --init           # 初始化所有 agent workspace
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import NoReturn, Optional

if __package__ in (None, ""):  # 作为脚本直接运行时确保 common 包可导入
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.agent_bootstrap import auto_create_agent
from common.agent_port import AgentPort, WatchdogConfig, reconcile_on_start
from common.observability import BudgetConfig, check_budget
from common.process import Process, ProcessConfig, ProjectOutcome
from common.store import Store
from common.workspace_gc import gc_workspace

_DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "business" / "demo"


def _read_demo_goal() -> str:
    """从 business/demo/goal.txt 读取 demo 目标。"""
    goal_file = _DEMO_DIR / "goal.txt"
    if goal_file.is_file():
        lines = goal_file.read_text(encoding="utf-8").splitlines()
        # 首行为 goal，空行和 # 注释跳过
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped
    return "调研 AI 编码工具 Cursor、Claude Code、GitHub Copilot 的市场定位和核心功能，输出一份简要对比报告。"


def _budget_checker(store: Store, token_budget: Optional[int]):
    """交互进行中硬停：达项目 token 硬上限返回 True。"""
    if not token_budget:
        return None

    def check(project_id: str) -> bool:
        bs = check_budget(store, project_id, BudgetConfig(project_limit=token_budget))
        return bs.state == "over"

    return check


def _system_default_backend() -> str:
    try:
        from store.system_config import system_config
        return system_config.get("system", "default_backend", default="opencode")
    except Exception:
        return "opencode"


def _load_agents_registry() -> dict:
    """读取 agents_registry.json，返回 {agent_id: info}。"""
    try:
        from common.paths import AGENTS_REGISTRY_FILE
        raw = json.loads(AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        return raw.get("agents", {})
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _friendly_traceback(e: BaseException) -> str:
    """把常见异常映射为中文用户提示。"""
    msg = str(e) or type(e).__name__
    if isinstance(e, FileNotFoundError):
        path = getattr(e, "filename", "") or msg
        if "workspace" in path.lower() or "workspace-" in path:
            return (f"找不到 agent 的工作空间「{path}」。\n"
                    f"可执行 python run_kernel.py --init 自动创建所有 agent workspace。")
        if "config" in path.lower() or ".json" in path or ".yaml" in path:
            return (f"缺少配置文件「{path}」。\n"
                    f"请确认 business/config/ 下有完整的配置文件。")
        return f"找不到文件「{path}」，请检查路径是否正确。"
    if isinstance(e, RuntimeError):
        if "plan gate" in msg.lower() or "task_plan" in msg.lower() or "名册" in msg:
            return (f"编排规划失败：{msg}\n"
                    f"可能原因：main 分配了名册外的 agent，或 task_type 不匹配。\n"
                    f"请检查 business/config/agents_registry.json 中的 agent 配置。")
        if "项目不存在" in msg:
            return f"项目不存在，请检查项目 ID 是否正确。"
        if "项目无任务" in msg:
            return f"项目没有任务数据，可能是不完整的中断状态。"
        return f"运行时异常：{msg}"
    if isinstance(e, LookupError):
        return f"找不到配置或数据：{msg}"
    import subprocess as _subprocess
    if isinstance(e, _subprocess.CalledProcessError):
        return (f"CLI 后端执行失败（exit code {e.returncode}）。\n"
                f"请确认 CLI 已安装并登录（opencode 或 claude）。")
    return (f"未知错误：{msg}\n"
            f"详情见日志。如需帮助，请附上 business/tasks/project/ 目录。")


def run_project(project_id: str, *, goal: str = "", title: str = "",
                mode: str = "one_shot", token_budget: Optional[int] = None,
                max_cycles: int = 3, review: bool = False, split: bool = False,
                workflow: Optional[str] = None,
                backend: Optional[str] = None,
                store: Optional[Store] = None, transport=None,
                watchdog: Optional[WatchdogConfig] = None,
                config: Optional[ProcessConfig] = None) -> ProjectOutcome:
    """组装并运行新内核。transport 按各 agent 的 agents_config.backend 选择 CLI（缺省读系统默认）。

    指定 workflow 时加载 business/workflows/<id>.yaml，跳过 team_config/task_plan。
    """
    backend = backend or _system_default_backend()
    store = store or Store()
    reconcile_on_start(store)  # 启动对账 GC（D8）：清理上次残留的 pending/running
    gc_workspace(store)      # 清 agent workspace 里已终态 interaction 的临时件
    if transport is None:
        from common.agent_transport import AdapterTransport, make_gate_session_resolver
        transport = AdapterTransport(
            backend=backend, session_resolver=make_gate_session_resolver(store),
        )

    agents: Optional[list[str]] = None
    tasks: Optional[list[dict]] = None
    wf_review = review
    wf_split = split
    wf_parallel = False
    wf_max_parallel = 4
    wf_skill_extract = False
    workflow_id: Optional[str] = None
    if workflow:
        from common.workflow_bootstrap import ensure_workflow_ready
        profile = ensure_workflow_ready(workflow, backend=backend)
        workflow_id = profile.id
        agents = profile.roster
        tasks = profile.instantiate_tasks(goal=goal)
        opts = profile.options or {}
        if not review and opts.get("review_enabled"):
            wf_review = True
        if not split and opts.get("split_enabled"):
            wf_split = True
        if opts.get("parallel_enabled"):
            wf_parallel = True
            wf_max_parallel = int(opts.get("max_parallel") or 4)
        if opts.get("skill_extract_enabled"):
            wf_skill_extract = True

    if config is None:
        from common.kernel_config import kernel_configs_for_run

        base_cfg, resolved_wdog = kernel_configs_for_run(
            mode=mode, token_budget=token_budget,
            max_cycles=max_cycles, review=wf_review, split=wf_split, backend=backend,
        )
        base_cfg.parallel_enabled = wf_parallel
        base_cfg.max_parallel = wf_max_parallel
        if wf_skill_extract:
            base_cfg.skill_extract_enabled = True
        if watchdog is None:
            watchdog = resolved_wdog
    else:
        base_cfg = config
        if workflow:
            # Hub 传入预建 config，但 workflow 的标志仍需合并（不覆盖请求体的显式参数）
            if wf_parallel:
                base_cfg.parallel_enabled = True
                base_cfg.max_parallel = wf_max_parallel
            if wf_skill_extract:
                base_cfg.skill_extract_enabled = True
            # review / split：只在请求体未显式传 True 时才从 workflow 升级
            if not review and wf_review:
                base_cfg.review_enabled = True
            if not split and wf_split:
                base_cfg.split_enabled = True
    port = AgentPort(
        transport, store=store, config=watchdog or WatchdogConfig(),
        budget_checker=_budget_checker(store, base_cfg.token_budget),
    )
    proc = Process(store, port, base_cfg)
    return proc.run(project_id, title=title, goal=goal, agents=agents, tasks=tasks,
                    workflow=workflow_id)


def resume_project(project_id: str, *,
                   store: Optional[Store] = None, transport=None,
                   watchdog: Optional[WatchdogConfig] = None,
                   config: Optional[ProcessConfig] = None,
                   backend: Optional[str] = None) -> ProjectOutcome:
    """断点续跑 in_progress 项目：回收孤儿响应后继续 DAG（D8）。"""
    backend = backend or _system_default_backend()
    store = store or Store()
    reconcile_on_start(store)
    if transport is None:
        from common.agent_transport import AdapterTransport
        transport = AdapterTransport(backend=backend)
    proj = store.get_project(project_id)
    meta = (proj or {}).get("meta") or {}
    budget = meta.get("token_budget")
    mode = meta.get("mode") or "one_shot"
    if config is None:
        from common.kernel_config import kernel_configs_for_run

        proc_cfg, resolved_wdog = kernel_configs_for_run(
            mode=mode, token_budget=budget, backend=backend,
        )
        if watchdog is None:
            watchdog = resolved_wdog
    else:
        proc_cfg = config
    port = AgentPort(
        transport, store=store, config=watchdog or WatchdogConfig(),
        budget_checker=_budget_checker(store, proc_cfg.token_budget),
    )
    proc = Process(store, port, proc_cfg)
    outcome = proc.resume(project_id)
    # gc 须在 settle 之后：reconcile 可能已将 timed_out 标 done，过早 gc 会删 .response
    gc_workspace(store)
    return outcome


def resume_in_progress_projects(*, store: Optional[Store] = None,
                                backend: Optional[str] = None,
                                on_start=None, on_end=None) -> list[str]:
    """Hub 启动时自动续跑所有 in_progress / paused 项目。返回已续跑的 project_id 列表。

    on_start(pid) / on_end(pid, err) 为可选中性回调：由 Hub 注入以同步运行态
    （标记/清除 _KERNEL_RUNS），堵住「启动续跑期并发再续跑」窗口。内核本身不
    依赖 Hub（D12），回调缺省时行为与原先完全一致。
    """
    store = store or Store()
    reconcile_on_start(store)
    resumed: list[str] = []
    for proj in store.list_projects():
        pid = proj["project_id"]
        if proj.get("status") not in ("in_progress", "paused"):
            continue
        if on_start:
            on_start(pid)
        try:
            resume_project(pid, store=store, backend=backend)
            resumed.append(pid)
            if on_end:
                on_end(pid, None)
        except Exception as e:
            if on_end:
                on_end(pid, e)
            continue
    return resumed


def _run_demo(demo_goal: str, backend: str) -> ProjectOutcome:
    """运行 demo 项目。"""
    project_id = f"demo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"🚀 demo 项目启动：{project_id}")
    print(f"📋 目标：{demo_goal}")
    print(f"⚙️  后端：{backend}")
    print()
    outcome = run_project(project_id, goal=demo_goal,
                          mode="one_shot", backend=backend)
    return outcome


def _print_demo_result(outcome: ProjectOutcome) -> None:
    """打印 demo 结果摘要。"""
    total = len(outcome.tasks)
    done = sum(1 for o in outcome.tasks.values() if o.status == "completed")
    failed = sum(1 for o in outcome.tasks.values() if o.status in ("failed", "blocked"))
    print()
    print("=" * 50)
    print(f"🏁 Demo 完成 — 状态：{outcome.status}")
    print(f"📊 任务进度：{done}/{total} 完成", end="")
    if failed:
        print(f"，{failed} 失败", end="")
    print()
    for tid, o in sorted(outcome.tasks.items()):
        icon = "✔" if o.status == "completed" else "✖" if o.status in ("failed", "blocked") else "○"
        reason = f" — {o.reason}" if o.reason else ""
        print(f"  {icon} {tid} → {o.status}{reason}")
    print("=" * 50)
    if outcome.status == "completed":
        print("✅ Demo 运行成功！交付物位于 business/tasks/project/ 下。")
    else:
        print("⚠️  Demo 未完全成功，请检查日志。")
    print()


def cmd_init() -> int:
    """--init：为所有注册 agent 创建 workspace（幂等）。"""
    from common.paths import WORKSPACES_DIR, WORKSPACE_PREFIX
    agents = _load_agents_registry()
    if not agents:
        print("❌ 未找到 agents_registry.json，请确认 business/config/ 目录存在。")
        return 1

    print(f"📦 初始化 {len(agents)} 个 agent workspace…")
    created = 0
    for agent_id, info in agents.items():
        ws_dir = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"
        if ws_dir.exists():
            print(f"  ○ {agent_id}（{info.get('name','')}）— 已存在")
            continue
        auto_create_agent(
            agent_id,
            name=info.get("name", ""),
            role=info.get("role", "worker"),
            description=info.get("description", ""),
        )
        print(f"  ✓ {agent_id}（{info.get('name','')}）— 已创建")
        created += 1

    print()
    if created:
        print(f"✅ 已创建 {created} 个 workspace，{len(agents) - created} 个已存在。")
    else:
        print(f"✅ 所有 {len(agents)} 个 workspace 已就绪，无需创建。")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="新内核运行时入口（Process + 真实 opencode/claude）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例：
              python run_kernel.py my-project --goal "调研..." --mode one_shot
              python run_kernel.py --demo
              python run_kernel.py --init
        """),
    )
    p.add_argument("project_id", nargs="?", default=None,
                   help="项目 ID（--demo/--init 时无需提供）")
    p.add_argument("--demo", action="store_true",
                   help="快速启动 demo 项目，无需手动配置 goal 和 agent")
    p.add_argument("--init", action="store_true",
                   help="初始化所有 agent workspace（幂等）")
    p.add_argument("--goal", default="", help="项目目标（驱动 team_config / task_plan）")
    p.add_argument("--title", default="")
    p.add_argument("--mode", choices=["one_shot", "recurring"], default="one_shot")
    p.add_argument("--budget", type=int, default=None, help="per-project token 硬上限")
    p.add_argument("--max-cycles", type=int, default=3, help="recurring 模式的周期上限")
    p.add_argument("--workflow", default=None, metavar="ID",
                   help="PGD 工作流 profile（business/workflows/<ID>.yaml），跳过 task_plan")
    p.add_argument("--review", action="store_true",
                   help="开启同行评审（reviewer 由 main 在 task_plan 指派）")
    p.add_argument("--split", action="store_true",
                   help="开启派发前递归展开（evaluate；agent 按复杂度拆子任务）")
    p.add_argument("--backend", default="opencode", choices=["opencode", "claude"],
                   help="驱动 agent 的 CLI 后端（默认 opencode）")
    p.add_argument("--demo-dir", default=None,
                   help="demo 目录路径（默认 business/demo/）")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    p = _build_arg_parser()
    a = p.parse_args(argv)

    # ── --init：初始化 workspace ────────────────────────────
    if a.init:
        return cmd_init()

    # ── --demo：快速启动 demo ────────────────────────────
    if a.demo:
        if a.project_id:
            p.error("--demo 不可与 project_id 同时使用")
        if a.mode != "one_shot":
            p.error("--demo 仅支持 --mode one_shot")
        demo_goal = _read_demo_goal()
        try:
            outcome = _run_demo(demo_goal, a.backend)
        except Exception as e:
            print(f"\n❌ demo 运行失败：{_friendly_traceback(e)}", file=sys.stderr)
            return 1
        _print_demo_result(outcome)
        return 0 if outcome.status == "completed" else 1

    # ── 常规参数校验 ────────────────────────────────────
    if not a.project_id:
        p.error("请指定 project_id，或使用 --demo / --init")

    # ── 正常运行 ────────────────────────────────────
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("run_kernel")
    logger.info("▶ 启动项目：%s", a.project_id)

    try:
        out = run_project(a.project_id, goal=a.goal, title=a.title,
                          mode=a.mode, token_budget=a.budget, max_cycles=a.max_cycles,
                          review=a.review, split=a.split, workflow=a.workflow,
                          backend=a.backend)
    except FileNotFoundError as e:
        print(f"\n❌ {_friendly_traceback(e)}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"\n❌ {_friendly_traceback(e)}", file=sys.stderr)
        return 1
    except LookupError as e:
        print(f"\n❌ {_friendly_traceback(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ {_friendly_traceback(e)}", file=sys.stderr)
        return 1

    print(json.dumps({
        "project_id": out.project_id, "status": out.status,
        "tasks": {tid: {"status": o.status, "attempts": o.attempts, "reason": o.reason}
                  for tid, o in out.tasks.items()},
    }, ensure_ascii=False, indent=2))
    return 0 if out.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
