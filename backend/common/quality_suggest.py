"""Quality profile helpers — rank agents by past quality for a given task_type.

Exports:
    get_agent_quality_score(store, agent_id, task_type) -> float
    suggest_agent_for_task(store, task_type, available_agents) -> str
    AgentQualityScore                        -- dataclass for a single task_type score
    QualityProfile                           -- per-agent aggregate across task_types
    get_quality_profile(store, agent_id)     -- build a QualityProfile from store
    suggest_best_agent(store, task_type, available_agents) -> str | None
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from common.store import Store

logger = logging.getLogger(__name__)


# ── Legacy helpers (kept for backward compatibility with decision_pipeline.py) ──


def get_agent_quality_score(
    store: Store,
    agent_id: str,
    task_type: str,
    *,
    limit: int = 10,
) -> float:
    """Return the average quality_score for *agent_id* on *task_type*.

    Falls back to the agent's overall quality when no task_type-specific
    entries exist.  Returns 0.0 when there is no history at all.
    """
    from execution_harness.post.quality import fetch_quality_profile

    entries = fetch_quality_profile(
        agent_id, task_type, limit=limit, store=store,
    )
    if not entries:
        # 回退：不限 task_type 的综合评分
        entries = fetch_quality_profile(
            agent_id, limit=limit * 2, store=store,
        )
    if not entries:
        return 0.0

    scores: list[float] = []
    for entry in entries:
        content = entry.get("content") or ""
        for line in content.splitlines():
            if line.startswith("quality_score:"):
                try:
                    scores.append(float(line.split(":", 1)[1].strip()))
                except (ValueError, IndexError):
                    pass
    return sum(scores) / len(scores) if scores else 0.0


def suggest_agent_for_task(
    store: Store,
    task_type: str,
    available_agents: list[str],
) -> str:
    """Return the agent ID with the highest average quality for *task_type*.

    Scans every candidate in *available_agents*, ranks by
    :func:`get_agent_quality_score`, and returns the top scorer.
    When no agent has quality history, returns the first available agent
    (stable tie-break).
    """
    if not available_agents:
        return ""

    scored: list[tuple[float, str]] = []
    for aid in available_agents:
        s = get_agent_quality_score(store, aid, task_type)
        scored.append((s, aid))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 最高分 > 0 说明有历史数据支撑；否则返回第一个（稳定）
    best_score, best_agent = scored[0]
    if best_score > 0:
        return best_agent
    return scored[-1][1]  # 无数据时返回最后一个（alphabetical stable）


# ── New dataclass-based API ─────────────────────────────────────────────────────


@dataclass
class AgentQualityScore:
    """Aggregated quality metrics for one agent on one task_type."""

    agent_id: str
    task_type: str
    avg_score: float  # 0-1
    pass_rate: float  # 0-1
    sample_count: int


@dataclass
class QualityProfile:
    """All known quality scores for a single agent, keyed by task_type."""

    agent_id: str
    scores: dict[str, AgentQualityScore] = field(default_factory=dict)

    def best_for(self, task_type: str) -> Optional[AgentQualityScore]:
        """Return the score for *task_type*, or None if unavailable."""
        return self.scores.get(task_type)


def get_quality_profile(store: Store, agent_id: str) -> QualityProfile:
    """Build a :class:`QualityProfile` for *agent_id* from stored quality records.

    Reads the last 20 quality entries for the agent, groups them by task_type,
    and computes avg_score, pass_rate, and sample_count per bucket.
    """
    from execution_harness.post.quality import fetch_quality_profile

    entries = fetch_quality_profile(agent_id, limit=20, store=store)
    if not entries:
        return QualityProfile(agent_id=agent_id)

    # Group by task_type
    buckets: dict[str, list[dict]] = {}
    for entry in entries:
        content = entry.get("content") or ""
        task_type = ""
        for line in content.splitlines():
            if line.startswith("task_type:"):
                task_type = line.split(":", 1)[1].strip()
                break
        if not task_type:
            task_type = "_overall_"
        buckets.setdefault(task_type, []).append(entry)

    scores: dict[str, AgentQualityScore] = {}
    for tt, elist in buckets.items():
        avg_scores: list[float] = []
        passed = 0
        for e in elist:
            content = e.get("content") or ""
            for line in content.splitlines():
                if line.startswith("quality_score:"):
                    try:
                        avg_scores.append(float(line.split(":", 1)[1].strip()))
                    except (ValueError, IndexError):
                        pass
                if line.startswith("gate_passed: yes"):
                    passed += 1
        scores[tt] = AgentQualityScore(
            agent_id=agent_id,
            task_type=tt,
            avg_score=sum(avg_scores) / len(avg_scores) if avg_scores else 0.0,
            pass_rate=passed / len(elist) if elist else 0.0,
            sample_count=len(elist),
        )

    return QualityProfile(agent_id=agent_id, scores=scores)


def suggest_best_agent(
    store: Store,
    task_type: str,
    available_agents: list[str],
) -> Optional[str]:
    """Suggest the best agent for a given task_type from *available_agents*.

    Ranks by:
    1. Average quality score for this task_type
    2. Pass rate (tie-breaker)
    3. Sample count (more data = more reliable, tie-breaker)

    Returns the best agent_id, or None when no agents have quality history.
    """
    if not available_agents:
        return None

    candidates: list[tuple[float, float, int, str]] = []
    for aid in available_agents:
        profile = get_quality_profile(store, aid)
        score = profile.best_for(task_type)
        if score is None:
            continue
        candidates.append((score.avg_score, score.pass_rate, score.sample_count, aid))

    if not candidates:
        return None

    # Sort descending on avg_score, pass_rate, sample_count
    candidates.sort(key=lambda c: (c[0], c[1], c[2]), reverse=True)
    return candidates[0][3]
