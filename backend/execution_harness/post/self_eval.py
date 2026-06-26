#!/usr/bin/env python3
"""量化自动评测引擎 — 四大维度指标 + 基线对比 + 缺陷清单。

四大维度：
1. 产出质量 (quality) — 复用 rubric_eval 的 6 维度评分
2. 资产复用 (asset_reuse) — Skill/KB/偏好的实际使用率
3. 偏好执行 (preference_adherence) — 用户偏好是否被遵守
4. 执行效率 (efficiency) — 轮次/token消耗/检索冗余
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from common.store import Store
from execution_harness.post.rubric_eval import evaluate_deliverable
from execution_harness.post.data_collector import TaskTrace

logger = logging.getLogger("execution_harness.post.self_eval")

BASELINE_TAG = "baseline"


@dataclass
class EvalReport:
    """量化评测报告。"""
    total_score: float = 0.0              # 综合得分 0-100
    quality_score: float = 0.0            # 产出质量 0-100
    asset_reuse_score: float = 0.0        # 资产复用 0-100
    preference_score: float = 0.0         # 偏好执行 0-100
    efficiency_score: float = 0.0         # 执行效率 0-100
    baseline_diff: float = 0.0            # 与基线的差值
    baseline_score: float = 0.0           # 基线分数
    defects: list[dict] = field(default_factory=list)
    passed: bool = False
    summary: str = ""


def _calc_quality(deliverable_content: str, task_type: str) -> dict:
    """产出质量评估 — 复用 rubric_eval。"""
    r = evaluate_deliverable(deliverable_content, task_type=task_type)
    quality = r.total_score
    defects = []

    for dim, fails in r.dimension_failures.items():
        for f in fails:
            defects.append({
                "dimension": "quality",
                "sub_dim": dim,
                "detail": f,
                "severity": "redline" if any(kw in f for kw in [
                    "编造", "无来源", "纯ASCII", "不覆盖异常"
                ]) else "warning",
            })
    if r.hit_redlines:
        for hl in r.hit_redlines:
            defects.append({
                "dimension": "quality",
                "sub_dim": "redline",
                "detail": hl,
                "severity": "redline",
            })

    return {"score": round(quality, 1), "defects": defects}


def _calc_asset_reuse(
    trace: TaskTrace,
    constraints: dict,
) -> dict:
    """资产复用评估：
    - Skill 实际调用率
    - KB 引用率
    - 偏好纳入率
    """
    total_skills = len(constraints.get("skills", []))
    used_skills = len(trace.skill_logs)
    total_kb = len(constraints.get("kb", []))
    used_kb = len(trace.kb_fragments)
    total_prefs = len(constraints.get("preferences", []))
    used_prefs = len(trace.loaded_preferences)

    # 偏好执行：检查输出中是否体现了偏好要求
    pref_mentions = 0
    for pref_text in trace.loaded_preferences:
        for keyword in re.findall(r'[\w一-鿿]{2,}', pref_text):
            if len(keyword) >= 4 and keyword in trace.output_text:
                pref_mentions += 1
                break

    skill_rate = min(used_skills / max(total_skills, 1), 1.0)
    kb_rate = min(used_kb / max(total_kb, 1), 1.0)
    pref_rate = min(pref_mentions / max(total_prefs, 1), 1.0)

    score = round((skill_rate * 0.4 + kb_rate * 0.3 + pref_rate * 0.3) * 100, 1)

    defects = []
    if total_skills > 0 and used_skills == 0:
        defects.append({"dimension": "asset_reuse", "sub_dim": "skills",
                        "detail": f"匹配了{total_skills}个Skill但未调用任何Skill", "severity": "warning"})
    if total_kb > 0 and used_kb == 0:
        defects.append({"dimension": "asset_reuse", "sub_dim": "knowledge_base",
                        "detail": f"检索了{total_kb}条知识库但未引用", "severity": "warning"})
    if total_prefs > 0 and pref_mentions == 0:
        defects.append({"dimension": "asset_reuse", "sub_dim": "preferences",
                        "detail": "已加载偏好但输出中未体现", "severity": "warning"})
    if skill_rate < 0.5 and total_skills >= 2:
        defects.append({"dimension": "asset_reuse", "sub_dim": "skills",
                        "detail": f"Skill使用率仅{skill_rate*100:.0f}%", "severity": "info"})

    return {"score": score, "defects": defects}


def _calc_preference(trace: TaskTrace, deliverable_content: str) -> dict:
    """偏好执行评估 — 输出是否遵守了偏好中的具体要求。"""
    pref_text = "\n".join(trace.loaded_preferences)
    if not pref_text.strip():
        return {"score": 100.0, "defects": []}

    defects = []
    score = 100.0

    # 检查偏好中的硬性要求是否被遵守
    checks = [
        ("流程图", lambda: "```mermaid" in deliverable_content or "```plantuml" in deliverable_content or "```dot" in deliverable_content),
        ("Mermaid", lambda: "```mermaid" in deliverable_content),
        ("架构图", lambda: "架构" in deliverable_content and "```" in deliverable_content),
        ("异常", lambda: "异常" in deliverable_content),
        ("验收标准", lambda: "验收" in deliverable_content or "R1" in deliverable_content),
    ]

    for name, check_fn in checks:
        if name in pref_text and not check_fn():
            defects.append({
                "dimension": "preference",
                "sub_dim": name,
                "detail": f"偏好要求包含「{name}」，但交付物中未体现",
                "severity": "warning",
            })
            score -= 15

    return {"score": round(max(score, 0), 1), "defects": defects}


def _calc_efficiency(trace: TaskTrace) -> dict:
    """执行效率评估 — 轮次、token、检索冗余。"""
    defects = []
    score = 100.0

    # 轮次检查
    iters = trace.iteration_round
    if iters > 3:
        score -= 20 * (iters - 3)
        defects.append({"dimension": "efficiency", "sub_dim": "iterations",
                        "detail": f"迭代{iters}轮（上限3轮）", "severity": "warning"})

    # token 检查（>20000 算偏高）
    tokens = trace.token_usage
    if tokens > 20000:
        score -= 10
        defects.append({"dimension": "efficiency", "sub_dim": "tokens",
                        "detail": f"Token消耗{tokens}（偏高）", "severity": "info"})

    # 检索冗余检查
    tool_calls = trace.tool_calls
    if len(tool_calls) >= 3:
        # 检查是否有连续重复检索
        repeated = 0
        prev_query = ""
        for call in tool_calls:
            q = call.get("query", "").lower().strip()
            if q and q == prev_query:
                repeated += 1
            prev_query = q
        if repeated >= 3:
            score -= 15
            defects.append({"dimension": "efficiency", "sub_dim": "redundant_search",
                            "detail": f"连续{repeated}次重复检索无新增信息", "severity": "warning"})

    # 输出长度检查（过短=内容不完整）
    output_len = len(trace.output_text)
    if output_len < 200:
        score -= 20
        defects.append({"dimension": "efficiency", "sub_dim": "output_length",
                        "detail": f"输出仅{output_len}字符，内容过短", "severity": "warning"})

    return {"score": round(max(score, 0), 1), "defects": defects}


def fetch_baseline(task_type: str, agent_id: str, *, store: Optional[Store] = None) -> float:
    """获取同任务类型+同agent的历史基线分数。"""
    if store is None:
        store = Store()
    try:
        entries = store.memory_search(tags=[BASELINE_TAG, task_type, agent_id], limit=1)
        for e in entries:
            content = e.get("content") or ""
            for line in content.splitlines():
                if line.startswith("baseline_score:"):
                    return float(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return 60.0  # 默认基线60分


def update_baseline(
    score: float,
    task_type: str,
    agent_id: str,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """更新基线分数到KB。"""
    if store is None:
        store = Store()
    content = (
        f"baseline_score: {score:.1f}\n"
        f"task_type: {task_type}\n"
        f"agent_id: {agent_id}\n"
        f"updated_at: {__import__('time').time()}"
    )
    return store.memory_write(
        "",
        f"baseline:{agent_id}/{task_type}",
        content,
        tags=[BASELINE_TAG, task_type, agent_id],
    )


def evaluate(
    deliverable_content: str,
    task_trace: TaskTrace,
    constraints: dict,
    *,
    task_type: str = "",
    store: Optional[Store] = None,
) -> EvalReport:
    """四大维度量化评测入口。

    Args:
        deliverable_content: Agent交付物全文
        task_trace: 全链路追踪数据
        constraints: 前置约束（来自 self_improve.merge_constraints）
        task_type: 任务类型
        store: Store 实例（用于读取基线）

    Returns:
        EvalReport: 结构化的量化评测报告
    """
    if store is None:
        store = Store()

    # 维度1：产出质量
    quality = _calc_quality(deliverable_content, task_type)

    # 维度2：资产复用
    reuse = _calc_asset_reuse(task_trace, constraints)

    # 维度3：偏好执行
    preference = _calc_preference(task_trace, deliverable_content)

    # 维度4：执行效率
    efficiency = _calc_efficiency(task_trace)

    # 综合得分（加权）
    total_score = (
        quality["score"] * 0.45
        + reuse["score"] * 0.20
        + preference["score"] * 0.20
        + efficiency["score"] * 0.15
    )

    # 基线对比
    baseline = fetch_baseline(task_type, task_trace.agent_id, store=store)
    baseline_diff = round(total_score - baseline, 1)

    # 合并缺陷清单
    all_defects = (
        quality["defects"]
        + reuse["defects"]
        + preference["defects"]
        + efficiency["defects"]
    )

    passed = total_score >= baseline

    report = EvalReport(
        total_score=round(total_score, 1),
        quality_score=quality["score"],
        asset_reuse_score=reuse["score"],
        preference_score=preference["score"],
        efficiency_score=efficiency["score"],
        baseline_diff=baseline_diff,
        baseline_score=baseline,
        defects=all_defects,
        passed=passed,
    )

    # 生成摘要
    report.summary = _build_summary(report)
    return report


def _build_summary(r: EvalReport) -> str:
    lines = [
        "=" * 50,
        "【量化评测报告】",
        f"综合得分: {r.total_score:.1f}/100 | 基线: {r.baseline_score:.1f} | 差值: {r.baseline_diff:+.1f}",
        f"判定: {'✅通过' if r.passed else '❌未达标'}",
        "",
        "维度明细:",
        f"  产出质量: {r.quality_score:.1f}/100 (权45%)",
        f"  资产复用: {r.asset_reuse_score:.1f}/100 (权20%)",
        f"  偏好执行: {r.preference_score:.1f}/100 (权20%)",
        f"  执行效率: {r.efficiency_score:.1f}/100 (权15%)",
        "",
    ]

    if r.defects:
        lines.append("缺陷清单:")
        redlines = [d for d in r.defects if d.get("severity") == "redline"]
        warnings = [d for d in r.defects if d.get("severity") == "warning"]
        infos = [d for d in r.defects if d.get("severity") == "info"]
        if redlines:
            lines.append(f"  🔴 红线({len(redlines)}):")
            for d in redlines:
                lines.append(f"    - {d['sub_dim']}: {d['detail']}")
        if warnings:
            lines.append(f"  ⚠️  警告({len(warnings)}):")
            for d in warnings:
                lines.append(f"    - {d['sub_dim']}: {d['detail']}")
        if infos:
            lines.append(f"  ℹ️  提示({len(infos)}):")
            for d in infos:
                lines.append(f"    - {d['sub_dim']}: {d['detail']}")
    lines.append("=" * 50)
    return "\n".join(lines)


def report_to_json(report: EvalReport) -> str:
    """导出量化报表JSON。"""
    return json.dumps({
        "total_score": report.total_score,
        "baseline_score": report.baseline_score,
        "baseline_diff": report.baseline_diff,
        "quality_score": report.quality_score,
        "asset_reuse_score": report.asset_reuse_score,
        "preference_score": report.preference_score,
        "efficiency_score": report.efficiency_score,
        "passed": report.passed,
        "defect_count": len(report.defects),
        "defects": report.defects,
        "summary": report.summary,
    }, ensure_ascii=False, indent=2)