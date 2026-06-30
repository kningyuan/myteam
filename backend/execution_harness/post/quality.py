"""POST — Agent 质量画像（Path C：跨项目能力追踪）。

每次 task 完成后记录质量指标到 KB（attempts, gate retries, score, review_result），
带 ``["quality", agent_id, task_type]`` tag 持久化。"""

from __future__ import annotations

import logging
from typing import Optional

from common.store.store import Store

logger = logging.getLogger("execution_harness.post.quality")

_QUALITY_TAG = "quality"


def record_quality(
    store: Store,
    project_id: str,
    task_id: str,
    task_type: str,
    agent_id: str,
    attempt: int,
    quality_score: float,
    gate_passed: bool,
    review_result: str = "",
    status: str = "completed",
) -> Optional[int]:
    """记录单次 task 的质量指标到 KB。

    Args:
        store: 可写 Store
        project_id: 当前项目
        task_id: 任务 ID
        task_type: 任务类型
        agent_id: 执行 agent
        attempt: execute 尝试次数（含 Gate retry）
        quality_score: agent 自评分 (0..1)
        gate_passed: Gate 是否最终通过
        review_result: 同行评审结果 (passed|failed|skipped)
        status: 任务终态 (completed|needs_review|failed)

    Returns:
        memory id, or None on failure.
    """
    score_val = max(0.0, min(1.0, float(quality_score))) if quality_score is not None else 0.0
    content_lines = [
        f"agent: {agent_id}",
        f"task_type: {task_type}",
        f"task_id: {task_id}",
        f"project_id: {project_id}",
        f"attempts: {attempt}",
        f"quality_score: {score_val:.2f}",
        f"gate_passed: {'yes' if gate_passed else 'no'}",
        f"review: {review_result}",
        f"status: {status}",
    ]
    suggestion = _quality_suggestion(score_val, attempt, status)
    if suggestion:
        content_lines.append(f"suggestion: {suggestion}")
    content = "\n".join(content_lines)
    title = f"quality:{agent_id}/{task_type}:{task_id}"
    tags = [_QUALITY_TAG, agent_id, task_type, project_id]
    return store.memory_write(project_id, title, content, tags=tags)


def _quality_suggestion(score: float, attempts: int, status: str) -> str:
    """基于质量表现给出简要建议（用于 team_config 参考）。"""
    if status == "failed":
        return "上次任务未完成，建议评估是否继续委派同类任务"
    if attempts > 2 and status == "needs_review":
        return "多次 retry 后仍需评审，建议关注交付质量后再委派"
    if score < 0.4:
        return "自评偏低，建议复核后再委派重要任务"
    if attempts >= 3:
        return f"经过 {attempts} 次重试才完成，效率偏低"
    return ""


def fetch_quality_profile(
    agent_id: str,
    task_type: str = "",
    *,
    limit: int = 5,
    store: Optional[Store] = None,
) -> list[dict]:
    """取 agent 在某 task_type 上的质量画像。

    优先级：跨项目同 agent + 同 task_type → 同 agent 综合。
    """
    if not store:
        return []
    entries: list[dict] = []

    # 当前 agent + 当前 task_type
    if task_type:
        entries = store.memory_search(
            tags=[_QUALITY_TAG, agent_id, task_type],
            limit=limit,
        )
    if len(entries) >= limit:
        return entries[:limit]

    # 当前 agent 综合（不限 task_type）
    general = store.memory_search(
        tags=[_QUALITY_TAG, agent_id],
        limit=limit * 2,
    )
    seen = {e.get("id") for e in entries}
    for e in general:
        if e.get("id") in seen:
            continue
        entries.append(e)
        if len(entries) >= limit:
            break

    return entries[:limit]


def summarize_quality(entries: list[dict]) -> str:
    """从 quality 条目列表合成摘要（供 team_config prompt 注入）。"""
    if not entries:
        return ""
    total = len(entries)
    passed = sum(1 for e in entries if "gate_passed: yes" in (e.get("content") or ""))
    failed = sum(1 for e in entries if "status: failed" in (e.get("content") or ""))
    avg_score = 0.0
    scores = []
    for e in entries:
        content = e.get("content") or ""
        for line in content.splitlines():
            if line.startswith("quality_score:"):
                try:
                    scores.append(float(line.split(":", 1)[1].strip()))
                except (ValueError, IndexError):
                    pass
    if scores:
        avg_score = sum(scores) / len(scores)
    lines = [f"【Agent {_extract_agent(entries)} 质量画像（最近 {total} 次任务）】"]
    lines.append(f"  Gate 通过率：{passed}/{total}（{passed * 100 // total if total else 0}%）")
    if failed:
        lines.append(f"  失败次数：{failed}")
    if scores:
        lines.append(f"  平均自评：{avg_score:.2f}")
    return "\n".join(lines)


def _extract_agent(entries: list[dict]) -> str:
    for e in entries:
        content = e.get("content") or ""
        for line in content.splitlines():
            if line.startswith("agent:"):
                return line.split(":", 1)[1].strip()
    return "unknown"