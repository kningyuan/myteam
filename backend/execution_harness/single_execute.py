#!/usr/bin/env python3
"""单 Agent execute 运行器 — 不经过 Workflow，直接走 execute 质量链路。

用法:
  prepare  生成交付目录、骨架、worker prompt
  finish   Gate 通过后 POST（promote / references / 可选 skill_review）
  prompt   仅打印 prompt（调试）

示例:
  PYTHONPATH=backend python backend/execution_harness/single_execute.py prepare \\
    --project sa-q1 --task t-research-01 --agent product --task-type research \\
    --intent "调研单 agent execute harness 注入完整性"

  # Agent 完成交付物与 ledger 后:
  PYTHONPATH=backend python backend/execution_harness/single_execute.py finish \\
    --project sa-q1 --task t-research-01 --task-type research --agent product
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from common.agent.agent_transport import build_worker_prompt
from common.contracts import InteractionRequest
from common.paths import MYTEAM_ROOT, TASKS_DIR, deliverables_dir, response_dir
from common.gate.registry import resolve_format_spec
from common.store.store import Store, default_db_path
from execution_harness.context import TaskCompleteContext
from execution_harness.facade import on_task_complete


def _run_root(project_id: str) -> Path:
    return TASKS_DIR / "single_agent" / project_id


def _task_dir(project_id: str, task_id: str) -> Path:
    return _run_root(project_id) / task_id


def _deliverable_path(project_id: str, task_id: str, task_type: str) -> Path:
    spec = resolve_format_spec(task_type)
    rel = f"{task_id}_deliverable.md"
    if spec and spec.template_id:
        rel = f"{task_id}_{spec.template_id}.md"
    return deliverables_dir(project_id) / rel


def _skeleton_deliverable(task_type: str, intent: str) -> str:
    spec = resolve_format_spec(task_type)
    lines = [f"# 交付物 — {task_type}", ""]
    if intent:
        lines.extend([f"> 任务意图：{intent}", ""])
    if spec and spec.sections:
        for sec in spec.sections:
            name = sec.get("name") if isinstance(sec, dict) else str(sec)
            if name:
                lines.extend([f"## {name}", "", "（待填写）", ""])
    else:
        lines.extend(["## 产出", "", "（待填写）", ""])
    return "\n".join(lines)


def _default_ledger(task_type: str, task_id: str, intent: str) -> str:
    return (
        f"task_id: {task_id}\n"
        f"task_type: {task_type}\n"
        f"intent: {intent}\n"
        "summary: |\n"
        "  （任务完成后填写：关键结论 1-3 句）\n"
        "lesson:\n"
        "  worked: |\n"
        "    （有效做法）\n"
        "  failed: |\n"
        "    （无效或踩坑）\n"
        "pitfalls:\n"
        "  - （下次同类任务须避免）\n"
        "sources:\n"
        "  - （扫描路径 / 文件 / 命令）\n"
    )


def _build_request(
    *,
    project_id: str,
    task_id: str,
    agent_id: str,
    task_type: str,
    intent: str,
    deliv_base: Path,
    deliv_rel: str,
) -> InteractionRequest:
    iid = f"{project_id}:{task_id}:execute:1"
    return InteractionRequest(
        interaction_id=iid,
        kind="execute",
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        intent=intent,
        input={
            "deliverable_path": deliv_rel,
            "deliverable_base": str(deliv_base),
        },
        constraints={"task_type": task_type, "template_id": resolve_format_spec(task_type).template_id or ""},
        response_schema="execute.result@1.0",
    )


def cmd_prepare(args: argparse.Namespace) -> int:
    td = _task_dir(args.project, args.task)
    td.mkdir(parents=True, exist_ok=True)
    deliv_base = deliverables_dir(args.project)
    deliv_base.mkdir(parents=True, exist_ok=True)
    deliv = _deliverable_path(args.project, args.task, args.task_type)
    deliv_rel = deliv.name
    if not deliv.is_file():
        deliv.write_text(
            _skeleton_deliverable(args.task_type, args.intent),
            encoding="utf-8",
        )
    ledger = td / "ledger.entry.yaml"
    if not ledger.is_file():
        ledger.write_text(
            _default_ledger(args.task_type, args.task, args.intent),
            encoding="utf-8",
        )
    meta = {
        "project_id": args.project,
        "task_id": args.task,
        "agent_id": args.agent,
        "task_type": args.task_type,
        "intent": args.intent,
        "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "deliverable": str(deliv),
        "ledger": str(ledger),
    }
    (td / "run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    req = _build_request(
        project_id=args.project,
        task_id=args.task,
        agent_id=args.agent,
        task_type=args.task_type,
        intent=args.intent,
        deliv_base=deliv_base,
        deliv_rel=deliv_rel,
    )
    req.context["store_path"] = str(default_db_path())
    resp_path = response_dir(args.agent) / f"{req.interaction_id}.response"
    prompt = build_worker_prompt(req, resp_path, deliv_base)
    (td / "worker.prompt.txt").write_text(prompt, encoding="utf-8")
    harness_blocks = [
        ln for ln in prompt.splitlines()
        if ln.startswith("【") and any(
            k in ln for k in ("方法论", "经验", "偏好", "工作记忆", "相关知识", "references")
        )
    ]
    (td / "harness.blocks.txt").write_text("\n".join(harness_blocks), encoding="utf-8")
    # 确保 config/USER.md 存在（偏好注入）
    from common.paths import CONFIG_DIR

    user_md = CONFIG_DIR / "USER.md"
    tpl = MYTEAM_ROOT / "business" / "templates" / "USER.md"
    if not user_md.is_file() and tpl.is_file():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        user_md.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✓ 已从模板写入 {user_md}")
    print(f"✓ 任务目录: {td}")
    print(f"✓ 交付物:   {deliv}")
    print(f"✓ ledger:   {ledger}")
    print(f"✓ prompt:   {td / 'worker.prompt.txt'}")
    print(f"✓ harness 块 ({len(harness_blocks)}): {td / 'harness.blocks.txt'}")
    for b in harness_blocks[:8]:
        print(f"    {b}")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    meta_path = _task_dir(args.project, args.task) / "run.meta.json"
    if not meta_path.is_file():
        print("请先 prepare", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    text = (_task_dir(args.project, args.task) / "worker.prompt.txt").read_text(encoding="utf-8")
    print(text)
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    td = _task_dir(args.project, args.task)
    meta_path = td / "run.meta.json"
    if not meta_path.is_file():
        print("请先 prepare", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    deliv = Path(meta["deliverable"])
    if not deliv.is_file() or deliv.stat().st_size < 100:
        print(f"交付物过短或缺失: {deliv}", file=sys.stderr)
        return 1
    ledger = td / "ledger.entry.yaml"
    if not ledger.is_file():
        print(f"缺少 ledger: {ledger}", file=sys.stderr)
        return 1
    store = Store(default_db_path())
    ctx = TaskCompleteContext(
        base_dir=td,
        project_id=args.project,
        task_id=args.task,
        task_type=args.task_type,
        store=store,
        agent_id=args.agent,
        gate_passed=True,
        attempt=1,
        status="completed",
    )
    ref = on_task_complete(ctx, port_run=None)
    summary = {
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kb_ref": ref,
        "deliverable_bytes": deliv.stat().st_size,
        "ledger_bytes": ledger.stat().st_size,
    }
    (td / "finish.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    store.close()
    print(f"✓ POST 完成 kb_ref={ref}")
    print(f"✓ 摘要: {td / 'finish.summary.json'}")
    return 0


def cmd_rerun_prompt(args: argparse.Namespace) -> int:
    """第二次 execute：验证经验/references 是否注入（E-EVO-2 探测）。"""
    task2 = args.task2 or f"{args.task}-followup"
    intent = args.intent or "同类 follow-up：应命中上次 KB/ledger 关键词"
    ns = argparse.Namespace(
        project=args.project,
        task=task2,
        agent=args.agent,
        task_type=args.task_type,
        intent=intent,
    )
    return cmd_prepare(ns)


def main() -> int:
    p = argparse.ArgumentParser(description="单 Agent execute（无 Workflow）")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="准备任务目录与 worker prompt")
    prep.add_argument("--project", required=True)
    prep.add_argument("--task", required=True)
    prep.add_argument("--agent", default="product")
    prep.add_argument("--task-type", default="research")
    prep.add_argument("--intent", default="单 agent execute 质量验证任务")

    sub.add_parser("prompt", help="打印已生成的 prompt")

    fin = sub.add_parser("finish", help="POST promote（需交付物+ledger）")
    fin.add_argument("--project", required=True)
    fin.add_argument("--task", required=True)
    fin.add_argument("--agent", default="product")
    fin.add_argument("--task-type", default="research")

    fol = sub.add_parser("followup-prompt", help="同 project 第二次 prepare（测复利 inject）")
    fol.add_argument("--project", required=True)
    fol.add_argument("--task", required=True, help="已完成的首任务 id")
    fol.add_argument("--task2", default="")
    fol.add_argument("--agent", default="product")
    fol.add_argument("--task-type", default="research")
    fol.add_argument("--intent", default="")

    args = p.parse_args()
    if args.cmd == "prepare":
        return cmd_prepare(args)
    if args.cmd == "prompt":
        return cmd_prompt(args)
    if args.cmd == "finish":
        return cmd_finish(args)
    if args.cmd == "followup-prompt":
        return cmd_rerun_prompt(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
