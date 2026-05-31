#!/usr/bin/env python3
"""Task Dispatch Skill - 任务分发

注意：通报统一由 project-data update-task 发送
"""

import sys
import json
import subprocess
import logging
import re
import argparse
import time
from datetime import datetime
from pathlib import Path

# 导入公共日志模块
sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.agent_auth import assert_agent_allowed
from common.graph_gate import assert_valid_task_graph
from common.config import DISPATCH_RETRY_SLEEP
from common.logger import get_skill_logger, log_skill_step_failure, normalize_project_id
from common.notify_handshake import (
    ACK_TIMEOUT_SEC,
    cleanup_trigger,
    release_queue,
    run_notify_dispatch,
    wait_for_agent_ack,
)



def dispatch(project_id, task_id, agent_id):
    """分发任务给指定 Agent（带项目验证）"""

    # 角色边界检查：仅 Main Agent 可调用 dispatch
    assert_agent_allowed("task-dispatch")

    # 标准化 project_id
    corrected_id = normalize_project_id(project_id)

    # 验证项目是否已初始化
    project_dir = Path.home() / f".openclaw/tasks/projects/{corrected_id}"
    if not (project_dir / "task_data.json").exists():
        logger = get_skill_logger(corrected_id)
        logger.error(
            f"[DISPATCH_FAIL] 项目未初始化：{corrected_id}",
            extra={"skill_name": "DISPATCH"},
        )
        print(f"Error: 项目未初始化（缺少 task_data.json）：{corrected_id}", file=sys.stderr)
        print(f"请先调用 project-init 重新创建项目", file=sys.stderr)
        log_skill_step_failure(
            corrected_id,
            "DISPATCH",
            "project_not_initialized",
            "missing task_data.json",
            str(project_dir),
        )
        sys.exit(1)

    # 图验证：确保任务依赖图为合法 DAG（无环、无未知依赖）
    assert_valid_task_graph(corrected_id)

    # 获取日志器（使用修正后的 ID）
    logger = get_skill_logger(corrected_id)

    # 【防重复派发】检查任务是否已在执行或已完成
    try:
        with open(project_dir / "task_data.json", "r", encoding="utf-8") as f:
            task_data = json.load(f)
        for t in task_data.get("tasks", []):
            if t["id"] == task_id:
                if t.get("status") == "in_progress":
                    logger.warning(
                        f"[DISPATCH_SKIP] task={task_id} already in_progress",
                        extra={"skill_name": "DISPATCH"},
                    )
                    print(f"⚠️ Task {task_id} already in_progress, skipping dispatch")
                    return
                if t.get("status") == "completed":
                    logger.warning(
                        f"[DISPATCH_SKIP] task={task_id} already completed",
                        extra={"skill_name": "DISPATCH"},
                    )
                    print(f"⚠️ Task {task_id} already completed, skipping dispatch")
                    return
                break
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            f"[DISPATCH_CHECK_FAIL] cannot read task_data.json: {e}",
            extra={"skill_name": "DISPATCH"},
        )
        # 非致命，继续执行（让 queue lock 做最终守卫）
    logger.info(f"[DISPATCH_START] project={corrected_id}, task={task_id}, agent={agent_id}", 
                extra={'skill_name': 'DISPATCH'})
    
    try:
        # 1. 获取队列锁（阻塞直到可以执行）
        result = subprocess.run(
            [
                str(
                    Path.home()
                    / ".openclaw"
                    / "skills"
                    / "team-ok"
                    / "task-queue"
                    / "scripts"
                    / "task_queue.py"
                ),
                "start",
                corrected_id,
                task_id,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                f"[QUEUE_LOCK_FAIL] project={corrected_id}, task={task_id}, error={result.stderr}",
                extra={"skill_name": "DISPATCH"},
            )
            print(f"Error acquiring queue lock: {result.stderr}", file=sys.stderr)
            log_skill_step_failure(
                corrected_id,
                "DISPATCH",
                "queue_start_failed",
                (result.stderr or result.stdout or "")[:500],
                task_id,
            )
            sys.exit(1)
        
        logger.info(
            f"[QUEUE_LOCK] project={corrected_id}, task={task_id}, result=success",
            extra={"skill_name": "DISPATCH"},
        )
        print(f"✅ Queue lock acquired for task {task_id}")

        # 【持锁重检】防止 TOCTOU：获取锁后重新读取 task_data.json
        # 注意：task_queue.py start 会将任务置为 in_progress，因此只关注 completed（异常状态）
        try:
            with open(project_dir / "task_data.json", "r", encoding="utf-8") as f:
                locked_data = json.load(f)
            for t in locked_data.get("tasks", []):
                if t["id"] == task_id:
                    if t.get("status") == "completed":
                        logger.warning(
                            f"[DISPATCH_TOCTOU] task={task_id} completed while acquiring lock",
                            extra={"skill_name": "DISPATCH"},
                        )
                        print(f"⚠️ Task {task_id} already completed, releasing queue lock")
                        release_queue(corrected_id)
                        return
                    break
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                f"[DISPATCH_LOCKED_CHECK_FAIL] cannot re-read task_data.json: {e}",
                extra={"skill_name": "DISPATCH"},
            )
            # 非致命，继续执行

        # 2. 创建触发文件（如果失败需释放锁）；文件名与 JSON 内 project_id 一律用规范化 ID，与 task-complete / project-data 对齐
        trigger_dir = Path.home() / f".openclaw/workspace-{agent_id}/.trigger"
        trigger_file = trigger_dir / f"{corrected_id}_{task_id}.trigger"
        try:
            trigger_dir.mkdir(parents=True, exist_ok=True)

            trigger_data = {
                "project_id": corrected_id,
                "task_id": task_id,
                "dispatched_at": datetime.now().isoformat(),
            }

            with open(trigger_file, "w", encoding="utf-8") as f:
                json.dump(trigger_data, f, ensure_ascii=False)

            logger.info(
                f"[TRIGGER_CREATED] file={trigger_file}, project={corrected_id}, task={task_id}, agent={agent_id}",
                extra={"skill_name": "DISPATCH"},
            )
            print(f"✅ Trigger file created: {trigger_file}")
        except Exception as e:
            logger.error(
                f"[TRIGGER_CREATE_FAIL] file={trigger_file}, project={corrected_id}, task={task_id}, agent={agent_id}, error={str(e)}",
                extra={"skill_name": "DISPATCH"},
            )
            logger.info(
                f"[QUEUE_RELEASE] project={corrected_id}, task={task_id}, reason=trigger_create_failed",
                extra={"skill_name": "DISPATCH"},
            )
            subprocess.run(
                [
                    str(
                        Path.home()
                        / ".openclaw"
                        / "skills"
                        / "team-ok"
                        / "task-queue"
                        / "scripts"
                        / "task_queue.py"
                    ),
                    "release",
                    corrected_id,
                ],
                capture_output=True,
                text=True,
            )
            print(f"Error creating trigger file: {e}", file=sys.stderr)
            log_skill_step_failure(
                corrected_id,
                "DISPATCH",
                "trigger_create_failed",
                str(e),
                str(trigger_file),
            )
            sys.exit(1)

        # 3. 通知目标 Agent（detach + 握手，或 DISPATCH_NOTIFY_MODE=sync 全同步）
        #    重试 2 次，间隔 5 秒
        notify_ok = False
        notify_err = ""
        for attempt in range(1, 3):
            print(f"📨 Notifying agent {agent_id} (reliable notify handshake, attempt {attempt}/2)...")
            ok, err = run_notify_dispatch(
                corrected_id, task_id, agent_id, logger, skill_name="DISPATCH"
            )
            if ok:
                notify_ok = True
                break
            notify_err = err
            if attempt < 2:
                logger.warning(
                    f"[AGENT_NOTIFY_RETRY] agent={agent_id}, project={corrected_id}, task={task_id}, attempt={attempt}",
                    extra={"skill_name": "DISPATCH"},
                )
                time.sleep(DISPATCH_RETRY_SLEEP)
        if not notify_ok:
            logger.error(
                f"[AGENT_NOTIFY_FAIL] agent={agent_id}, project={corrected_id}, task={task_id}, error={notify_err[:200]}",
                extra={"skill_name": "DISPATCH"},
            )
            logger.info(
                f"[QUEUE_RELEASE] project={corrected_id}, task={task_id}, reason=notify_failed",
                extra={"skill_name": "DISPATCH"},
            )
            release_queue(corrected_id)
            log_skill_step_failure(
                corrected_id,
                "DISPATCH",
                "notify_handshake_failed",
                notify_err[:500],
                f"task={task_id}, agent={agent_id}",
            )
            print(f"Error: Agent 通知未启动（握手失败）: {notify_err}", file=sys.stderr)
            sys.exit(1)

        # 4. 等待 Agent 执行确认（ACK）
        #     握手只确认通知脚本启动，ACK 确认 Agent 实际开始执行任务
        print(f"⏳ Waiting for agent {agent_id} to confirm execution (ACK timeout={ACK_TIMEOUT_SEC}s)...")
        ack_ok, ack_err = wait_for_agent_ack(agent_id, corrected_id, task_id, logger)
        if not ack_ok:
            logger.error(
                f"[ACK_FAIL] agent={agent_id}, project={corrected_id}, task={task_id}, error={ack_err[:200]}",
                extra={"skill_name": "DISPATCH"},
            )
            logger.info(
                f"[QUEUE_RELEASE] project={corrected_id}, task={task_id}, reason=ack_timeout",
                extra={"skill_name": "DISPATCH"},
            )
            release_queue(corrected_id)
            cleanup_trigger(agent_id, corrected_id, task_id)
            log_skill_step_failure(
                corrected_id,
                "DISPATCH",
                "ack_timeout",
                ack_err[:500],
                f"task={task_id}, agent={agent_id}",
            )
            print(f"Error: Agent 未确认执行（ACK 超时）: {ack_err}", file=sys.stderr)
            sys.exit(1)

        logger.info(
            f"[DISPATCH_END] project={corrected_id}, task={task_id}, agent={agent_id}, status=success",
            extra={"skill_name": "DISPATCH"},
        )
        print(f"✅ Agent notify handshake OK; ACK received from {agent_id}")
        print(f"\n🎯 Task {task_id} dispatched to {agent_id}")

    except Exception as e:
        logger.exception(
            f"[DISPATCH_ERROR] project={corrected_id}, task={task_id}, error={str(e)}",
            extra={"skill_name": "DISPATCH"},
        )
        print(f"Error: dispatch 未预期失败: {e}", file=sys.stderr)
        log_skill_step_failure(
            corrected_id,
            "DISPATCH",
            "dispatch_uncaught_exception",
            str(e),
            task_id,
        )
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Task Dispatch — 分发任务给 Agent")
    parser.add_argument("project_id", help="项目 ID")
    parser.add_argument("task_id", help="任务 ID")
    parser.add_argument("agent_id", help="目标 Agent ID")
    args = parser.parse_args()
    dispatch(
        args.project_id,
        args.task_id,
        args.agent_id,
    )

if __name__ == "__main__":
    main()
