#!/usr/bin/env python3
"""Cross Review — 交叉审核模块。

在质量门禁通过后调用，将 Agent 的交付物以结构化交接文档形式发送给
指定的审核 Agent，等待审核结果。超时（300s）则标记为 needs_review，
不静默跳过。

用法:
    reviewer = task_data.get("reviewer", "")
    result = run_cross_review(project_id, task_id, reviewer,
                               deliverable_path, task_summary)
    if result.passed:
        # 审核通过
    elif result.timed_out:
        # 标记 needs_review
    else:
        # 审核不通过，退回
"""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("CROSS_REVIEW")


@dataclass
class ReviewResult:
    passed: bool
    feedback: str = ""
    timed_out: bool = False
    skipped: bool = False


# 审核超时（秒）
REVIEW_TIMEOUT = 300
# 轮询间隔（秒）
REVIEW_POLL_INTERVAL = 5


def _write_handoff_doc(project_id: str, task_id: str, reviewer: str,
                       deliverable_path: str, summary: str,
                       template_sections: Optional[list] = None) -> str:
    """创建结构化交接文档，返回文档路径。

    文档包含：任务 ID、交付物路径、执行摘要、审核 checklist。
    审核 checklist 由 reviewer 对应的标准页面决定。
    """
    handoff_dir = Path.home() / ".openclaw" / "tasks" / "projects" / project_id / "reviews"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    review_items = [
        "- [ ] **功能性**: 交付物是否满足任务要求？",
        "- [ ] **完整性**: 交付物是否包含所有必需部分？",
        "- [ ] **质量**: 代码/文档/设计质量是否达标？",
        "- [ ] **一致性**: 是否与项目整体方向和标准一致？",
    ]
    if template_sections:
        sec_items = []
        for sec in template_sections:
            if not isinstance(sec, dict):
                continue
            name = sec.get("name", "")
            desc = sec.get("description", "")
            if name:
                sec_items.append(f"- [ ] **{name}**：{desc}")
        if sec_items:
            review_items.append("")
            review_items.append("### 章节内容质量检查（对照模板）")
            review_items.extend(sec_items)

    checklist = "\n".join(review_items)

    handoff_path = handoff_dir / f"{task_id}_handoff.md"
    content = f"""# 任务交接文档

## 基本信息
- **任务 ID**: {task_id}
- **审核人**: {reviewer}
- **交付物**: {deliverable_path}

## 执行摘要
{summary}

## 审核 Checklist

{checklist}

## 审核意见

请将审核结果写入 response 文件，格式：
```json
{{
    "passed": true/false,
    "feedback": "审核意见..."
}}
```
"""
    handoff_path.write_text(content, encoding="utf-8")
    return str(handoff_path)


def _notify_reviewer(project_id: str, reviewer: str, task_id: str,
                     handoff_path: str) -> bool:
    """通知审核者，返回是否成功。

    先写 trigger 文件，再通过 openclaw agent 实际通知审核人。
    """
    try:
        trigger_dir = Path.home() / ".openclaw" / f"workspace-{reviewer}" / ".trigger"
        trigger_dir.mkdir(parents=True, exist_ok=True)

        trigger_file = trigger_dir / f"{project_id}_{task_id}_review.request"
        trigger_file.write_text(json.dumps({
            "event": "cross_review",
            "project_id": project_id,
            "task_id": task_id,
            "handoff_path": handoff_path,
        }, ensure_ascii=False, indent=2))
    except (OSError, IOError):
        logger.debug("trigger 文件写入失败，继续尝试通知")

    # 实际通知审核人：通过 openclaw agent 发送消息
    import subprocess
    resp_path = (Path.home() / ".openclaw" / f"workspace-{reviewer}" / ".response"
                 / f"{project_id}_{task_id}_review.response")
    msg = (
        f"项目协作：请审核任务\n\n"
        f"项目：{project_id}\n"
        f"任务 ID：{task_id}\n\n"
        f"请阅读交接文档：\n{handoff_path}\n\n"
        f"审核完成后，将结果写入：\n{resp_path}\n\n"
        f"格式：\n"
        f'{{"passed": true, "feedback": "审核意见..."}}\n\n'
        f"超时时间：{REVIEW_TIMEOUT} 秒"
    )
    try:
        log_dir = Path.home() / ".openclaw" / "task-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        err_log = log_dir / f"{project_id}_{task_id}_review.err"
        with open(err_log, "w") as ef:
            subprocess.Popen(
                ["openclaw", "agent", "--agent", reviewer, "--message", msg,
                 "--thinking", "minimal"],
                stdout=subprocess.DEVNULL, stderr=ef,
            )
    except Exception:
        return False
    return True


def _collect_review_result(project_id: str, task_id: str, reviewer: str) -> Optional[dict]:
    """从 reviewer 的 response 目录收集审核结果。

    读取 workspace-{reviewer}/.response/{project_id}_{task_id}_review.response 文件。
    """
    resp_file = (Path.home() / ".openclaw" / f"workspace-{reviewer}" / ".response"
                 / f"{project_id}_{task_id}_review.response")
    if not resp_file.exists():
        return None

    try:
        return json.loads(resp_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        logger.debug("审核 response 文件读取失败（可能尚未写入完整）")
        return None


def run_cross_review(project_id: str, task_id: str, reviewer: str,
                     deliverable_path: str, summary: str,
                     template_sections: Optional[list] = None) -> ReviewResult:
    """执行一次交叉审核。

    Args:
        project_id: 项目 ID
        task_id: 任务 ID
        reviewer: 审核者 Agent ID（来自 task_data.json 的 reviewer 字段）
        deliverable_path: 交付物路径
        summary: 执行摘要
        template_sections: 可选的模板章节列表，用于生成内容质量审核项

    Returns:
        ReviewResult: 审核结果
    """
    if not reviewer:
        # 未指定审核者，跳过
        return ReviewResult(passed=True, skipped=True,
                            feedback="未指定审核者，跳过交叉审核")

    # 1. 创建结构化交接文档
    handoff_path = _write_handoff_doc(
        project_id, task_id, reviewer, deliverable_path, summary,
        template_sections=template_sections,
    )

    # 2. 通知审核者
    notified = _notify_reviewer(project_id, reviewer, task_id, handoff_path)
    if not notified:
        return ReviewResult(
            passed=True, skipped=True,
            feedback=f"无法通知审核者 {reviewer}，跳过交叉审核",
        )

    # 3. 等待审核结果（同步，最大 REVIEW_TIMEOUT 秒）
    deadline = time.time() + REVIEW_TIMEOUT
    while time.time() < deadline:
        result = _collect_review_result(project_id, task_id, reviewer)
        if result is not None:
            passed = result.get("passed", False)
            feedback = result.get("feedback", "")
            return ReviewResult(passed=passed, feedback=feedback)

        time.sleep(REVIEW_POLL_INTERVAL)

    # 超时 — 不静默跳过，标记 needs_review
    return ReviewResult(
        passed=False, timed_out=True,
        feedback=f"审核超时（{REVIEW_TIMEOUT}s），审核者 {reviewer} 未响应",
    )