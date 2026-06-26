#!/usr/bin/env python3
"""Agent 自我提升完整闭环编排入口。

端到端流程：
  前置资产加载 → 执行 → 全链路采集 → 量化评测 → 分级补强 → 达标沉淀 → 输出报表
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from common.store import Store
from execution_harness.pre.self_improve import merge_constraints
from execution_harness.post.data_collector import DataCollector, TaskTrace
from execution_harness.post.self_eval import evaluate, EvalReport, report_to_json, fetch_baseline, update_baseline
from execution_harness.post.self_improve import (
    classify_defects, determine_improvement_level, build_improvement_prompt, ImprovementAction,
)
from execution_harness.post.capability_pool import (
    store_optimal_skills, store_case, store_defect_mapping, update_baseline_from_score, store_full_report,
)

logger = logging.getLogger("execution_harness.self_improve_loop")

_MAX_IMPROVEMENT_ROUNDS = 3  # 最多补强3轮


@dataclass
class ImprovementRound:
    round_num: int
    action: ImprovementAction
    eval_report: EvalReport
    deliverable: str = ""
    improvement_prompt: str = ""


@dataclass
class SelfImproveResult:
    """完整闭环输出的量化报表。"""
    task_id: str
    task_type: str
    agent_id: str
    passed: bool = False
    final_score: float = 0.0
    baseline_score: float = 0.0
    baseline_diff: float = 0.0
    rounds: int = 0
    improvements: list[ImprovementRound] = field(default_factory=list)
    total_token_usage: int = 0
    report_json: str = ""


class SelfImproveLoop:
    """Agent 自我提升闭环编排器。"""

    def __init__(
        self,
        agent_id: str,
        task_type: str,
        task_id: str,
        task_name: str,
        store: Optional[Store] = None,
    ):
        self.agent_id = agent_id
        self.task_type = task_type
        self.task_id = task_id
        self.task_name = task_name
        self.store = store or Store()
        self.collector = DataCollector()
        self.collector.set_task(task_id, task_type, agent_id)

    def run(self, intent: str = "") -> SelfImproveResult:
        """执行完整闭环。

        Args:
            intent: 任务意图描述

        Returns:
            SelfImproveResult 含所有迭代数据和最终报表
        """
        result = SelfImproveResult(
            task_id=self.task_id,
            task_type=self.task_type,
            agent_id=self.agent_id,
            baseline_score=fetch_baseline(self.task_type, self.agent_id, store=self.store),
        )

        # ══ Step 1: 前置资产加载 ══
        constraints = merge_constraints(
            self.agent_id, self.task_type, self.task_name,
            intent=intent, store=self.store,
        )
        self.collector.record_preferences(constraints.get("preferences", []))
        self.collector.record_skills([s["id"] for s in constraints.get("skills", [])])
        self.collector.record_kb([k["title"] for k in constraints.get("kb", [])])
        self.collector.record_constraints(constraints.get("constraints_text", ""))

        logger.info(
            "前置资产: %d偏好, %dSkill, %dKB条",
            len(constraints["preferences"]),
            len(constraints["skills"]),
            len(constraints["kb"]),
        )

        base_deliverable = ""
        for round_idx in range(1, _MAX_IMPROVEMENT_ROUNDS + 1):
            # ══ Step 2-3: 执行 + 全链路采集 ══
            # 本轮执行的实际调用方（ChatService / AgentPort）需要在外部传入 deliverable
            # 这里先预留钩子
            # deliverable = self._execute_round(round_idx, constraints, ...)

            # ══ Step 4: 量化评测 ══
            if not base_deliverable:
                continue  # 首次执行需外部传入 deliverable

            trace = self.collector.finish()
            report = evaluate(
                base_deliverable, trace, constraints,
                task_type=self.task_type, store=self.store,
            )

            ir = ImprovementRound(
                round_num=round_idx,
                action=ImprovementAction(),  # 外部确定补强策略
                eval_report=report,
                deliverable=base_deliverable,
            )
            result.improvements.append(ir)

            # ══ Step 5: 判定是否达标 ══
            if report.passed:
                result.passed = True
                result.final_score = report.total_score
                result.baseline_diff = report.baseline_diff
                result.rounds = round_idx
                break

            # ══ Step 6: 分级补强 ══
            defects = classify_defects(report.defects)
            action = determine_improvement_level(
                report.total_score,
                result.baseline_score,
                report.defects,
                sum(1 for d in report.defects if d.get("severity") == "redline"),
            )
            ir.action = action
            improve_prompt = build_improvement_prompt(
                action, self.task_name, report.summary, report.defects,
            )
            ir.improvement_prompt = improve_prompt

            # 下一轮使用改进后的 prompt
            # base_deliverable = self._execute_with_prompt(improve_prompt)
            self.collector.inc_iteration()

        # ══ Step 7: 达标后沉淀 ══
        if result.passed:
            store_optimal_skills(
                self.agent_id, self.task_type,
                [s["id"] for s in constraints.get("skills", [])],
                result.final_score, store=self.store,
            )
            store_case(
                self.agent_id, self.task_type, self.task_id,
                result.final_score, [],
                base_deliverable[:500], store=self.store,
            )
            update_baseline_from_score(result.final_score, self.task_type, self.agent_id, store=self.store)

        # ══ Step 8: 输出报表 ══
        report_data = {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "agent_id": self.agent_id,
            "final_score": result.final_score,
            "baseline_score": result.baseline_score,
            "baseline_diff": result.baseline_diff,
            "passed": result.passed,
            "rounds": result.rounds,
            "total_improvements": len(result.improvements),
            "metrics": {},
        }
        if result.improvements:
            last = result.improvements[-1]
            report_data["metrics"] = {
                "产出质量": last.eval_report.quality_score,
                "资产复用": last.eval_report.asset_reuse_score,
                "偏好执行": last.eval_report.preference_score,
                "执行效率": last.eval_report.efficiency_score,
            }
            report_data["短板清单"] = [
                {"维度": d.get("dimension"), "详情": d.get("detail")}
                for d in last.eval_report.defects[:10]
            ]
            report_data["本次补强"] = {
                "Skill": last.action.target_skills if last.action.target_skills else [],
                "知识库": last.action.kb_fragments[:3] if last.action.kb_fragments else [],
                "重载偏好": last.action.reload_preferences,
                "全量重建": last.action.full_rebuild,
            }

        result.report_json = json.dumps(report_data, ensure_ascii=False, indent=2)
        store_full_report(self.agent_id, self.task_type, self.task_id, report_data, store=self.store)

        return result