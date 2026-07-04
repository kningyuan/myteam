"""单 Agent execute — Hub 服务层（无 Workflow）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from common.agent.agent_transport import build_worker_prompt
from common.paths import MYTEAM_ROOT, TASKS_DIR, deliverables_dir, response_dir
from common.store.store import Store, default_db_path
from execution_harness.context import TaskCompleteContext
from execution_harness.facade import on_task_complete
from execution_harness.single_execute import (
    _build_request,
    _default_ledger,
    _deliverable_path,
    _run_root,
    _skeleton_deliverable,
    _task_dir,
)


def list_single_execute_projects() -> list[dict[str, Any]]:
    root = TASKS_DIR / "single_agent"
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for proj in sorted(root.iterdir()):
        if not proj.is_dir() or proj.name.startswith("."):
            continue
        tasks = []
        for td in sorted(proj.iterdir()):
            if not td.is_dir():
                continue
            meta_path = td / "run.meta.json"
            if not meta_path.is_file():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tasks.append({
                    "task_id": meta.get("task_id") or td.name,
                    "agent_id": meta.get("agent_id"),
                    "task_type": meta.get("task_type"),
                    "intent": meta.get("intent"),
                    "prepared_at": meta.get("prepared_at"),
                    "finished": (td / "finish.summary.json").is_file(),
                })
            except (json.JSONDecodeError, OSError):
                continue
        out.append({
            "project_id": proj.name,
            "title": proj.name,
            "mode": "single_execute",
            "task_count": len(tasks),
            "tasks": tasks,
        })
    return out


def get_single_execute_task(project_id: str, task_id: str) -> dict[str, Any] | None:
    td = _task_dir(project_id, task_id)
    meta_path = td / "run.meta.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    prompt_path = td / "worker.prompt.txt"
    harness_path = td / "harness.blocks.txt"
    finish_path = td / "finish.summary.json"
    deliv = Path(meta.get("deliverable") or "")
    ledger = td / "ledger.entry.yaml"
    return {
        **meta,
        "project_id": project_id,
        "task_id": task_id,
        "prompt": prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else "",
        "harness_blocks": harness_path.read_text(encoding="utf-8") if harness_path.is_file() else "",
        "deliverable_content": deliv.read_text(encoding="utf-8", errors="replace") if deliv.is_file() else "",
        "ledger_content": ledger.read_text(encoding="utf-8", errors="replace") if ledger.is_file() else "",
        "finish_summary": json.loads(finish_path.read_text(encoding="utf-8")) if finish_path.is_file() else None,
        "finished": finish_path.is_file(),
    }


def prepare_single_execute(
    *,
    project_id: str,
    task_id: str,
    agent_id: str = "product",
    task_type: str = "research",
    intent: str = "单 agent execute 质量验证任务",
) -> dict[str, Any]:
    td = _task_dir(project_id, task_id)
    td.mkdir(parents=True, exist_ok=True)
    deliv_base = deliverables_dir(project_id)
    deliv_base.mkdir(parents=True, exist_ok=True)
    deliv = _deliverable_path(project_id, task_id, task_type)
    deliv_rel = deliv.name
    if not deliv.is_file():
        deliv.write_text(_skeleton_deliverable(task_type, intent), encoding="utf-8")
    ledger = td / "ledger.entry.yaml"
    if not ledger.is_file():
        ledger.write_text(_default_ledger(task_type, task_id, intent), encoding="utf-8")
    meta = {
        "project_id": project_id,
        "task_id": task_id,
        "agent_id": agent_id,
        "task_type": task_type,
        "intent": intent,
        "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "deliverable": str(deliv),
        "ledger": str(ledger),
    }
    (td / "run.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    req = _build_request(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        task_type=task_type,
        intent=intent,
        deliv_base=deliv_base,
        deliv_rel=deliv_rel,
    )
    db_path = default_db_path()
    req.context["store_path"] = str(db_path)
    resp_path = response_dir(agent_id) / f"{req.interaction_id}.response"
    prompt = build_worker_prompt(req, resp_path, deliv_base)
    (td / "worker.prompt.txt").write_text(prompt, encoding="utf-8")
    harness_blocks = [
        ln for ln in prompt.splitlines()
        if ln.startswith("【") and any(
            k in ln for k in ("方法论", "经验", "偏好", "工作记忆", "相关知识", "references")
        )
    ]
    (td / "harness.blocks.txt").write_text("\n".join(harness_blocks), encoding="utf-8")
    store = Store(db_path)
    try:
        store.upsert_project(
            project_id,
            title=f"单Agent · {project_id}",
            status="active",
            mode="single_execute",
        )
    finally:
        store.close()
    from common.paths import CONFIG_DIR

    user_md = CONFIG_DIR / "USER.md"
    tpl = MYTEAM_ROOT / "business" / "templates" / "USER.md"
    if not user_md.is_file() and tpl.is_file():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        user_md.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "success": True,
        "project_id": project_id,
        "task_id": task_id,
        "task_dir": str(td),
        "deliverable": str(deliv),
        "harness_block_count": len(harness_blocks),
        "harness_blocks": harness_blocks,
    }


def finish_single_execute(
    *,
    project_id: str,
    task_id: str,
    agent_id: str = "product",
    task_type: str = "research",
) -> dict[str, Any]:
    td = _task_dir(project_id, task_id)
    meta_path = td / "run.meta.json"
    if not meta_path.is_file():
        return {"success": False, "error": "请先 prepare"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    deliv = Path(meta["deliverable"])
    if not deliv.is_file() or deliv.stat().st_size < 100:
        return {"success": False, "error": f"交付物过短或缺失: {deliv}"}
    ledger = td / "ledger.entry.yaml"
    if not ledger.is_file():
        return {"success": False, "error": f"缺少 ledger: {ledger}"}
    store = Store(default_db_path())
    ctx = TaskCompleteContext(
        base_dir=td,
        project_id=project_id,
        task_id=task_id,
        task_type=task_type,
        store=store,
        agent_id=agent_id,
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
    return {"success": True, **summary}


def update_single_execute(
    *,
    project_id: str,
    task_id: str,
    intent: str | None = None,
    agent_id: str | None = None,
    task_type: str | None = None,
) -> dict[str, Any]:
    """编辑独立任务元数据（intent / agent_id / task_type），重新生成 prompt 与 harness 块。"""
    import re
    td = _task_dir(project_id, task_id)
    meta_path = td / "run.meta.json"
    if not meta_path.is_file():
        return {"success": False, "error": "任务不存在，请先 prepare"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # 仅允许在未 finish 时编辑
    if (td / "finish.summary.json").is_file():
        return {"success": False, "error": "已 finish 的任务不可编辑"}
    new_intent = intent.strip() if intent is not None else meta.get("intent", "")
    new_agent = (agent_id or meta.get("agent_id") or "product").strip()
    new_type = (task_type or meta.get("task_type") or "research").strip()
    meta["intent"] = new_intent
    meta["agent_id"] = new_agent
    meta["task_type"] = new_type
    (td / "run.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # 更新 ledger.entry.yaml 中的 intent/task_type（保留其余字段）
    ledger = td / "ledger.entry.yaml"
    if ledger.is_file():
        text = ledger.read_text(encoding="utf-8")
        text = re.sub(r"^intent:.*$", f"intent: {new_intent}", text, count=1, flags=re.MULTILINE)
        text = re.sub(r"^task_type:.*$", f"task_type: {new_type}", text, count=1, flags=re.MULTILINE)
        ledger.write_text(text, encoding="utf-8")
    # 重新生成 worker.prompt.txt 与 harness.blocks.txt
    deliv_base = deliverables_dir(project_id)
    deliv_base.mkdir(parents=True, exist_ok=True)
    deliv = _deliverable_path(project_id, task_id, new_type)
    if not deliv.is_file():
        deliv.write_text(_skeleton_deliverable(new_type, new_intent), encoding="utf-8")
    req = _build_request(
        project_id=project_id,
        task_id=task_id,
        agent_id=new_agent,
        task_type=new_type,
        intent=new_intent,
        deliv_base=deliv_base,
        deliv_rel=deliv.name,
    )
    req.context["store_path"] = str(default_db_path())
    resp_path = response_dir(new_agent) / f"{req.interaction_id}.response"
    prompt = build_worker_prompt(req, resp_path, deliv_base)
    (td / "worker.prompt.txt").write_text(prompt, encoding="utf-8")
    harness_blocks = [
        ln for ln in prompt.splitlines()
        if ln.startswith("【") and any(
            k in ln for k in ("方法论", "经验", "偏好", "工作记忆", "相关知识", "references")
        )
    ]
    (td / "harness.blocks.txt").write_text("\n".join(harness_blocks), encoding="utf-8")
    return {
        "success": True,
        "project_id": project_id,
        "task_id": task_id,
        "harness_block_count": len(harness_blocks),
    }


def delete_single_execute(*, project_id: str, task_id: str | None = None) -> dict[str, Any]:
    """删除独立任务；task_id 为空时删除整个项目目录。"""
    import shutil
    root = _run_root(project_id)
    if not root.is_dir():
        return {"success": False, "error": "项目不存在"}
    if task_id:
        td = root / task_id
        if not td.is_dir():
            return {"success": False, "error": "任务不存在"}
        shutil.rmtree(td)
        # 项目目录空了就一并清理
        try:
            if not any(root.iterdir()):
                root.rmdir()
        except OSError:
            pass
    else:
        shutil.rmtree(root)
    return {"success": True, "project_id": project_id}
