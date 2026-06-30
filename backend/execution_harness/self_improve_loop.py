#!/usr/bin/env python3
"""Agent 自我提升完整闭环编排入口。

端到端流程：
  前置资产加载 -> 执行 -> 全链路采集 -> 量化评测 -> 分级补强 -> 达标沉淀 -> 输出报表

新增（Phase 2）：
  - 若 rubric 评分低于阈值，自动从 rubric 反馈生成改进建议
  - 将改进建议注入 agent prompt 并重跑
  - 最多循环 3 轮
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from common.store.store import Store
from execution_harness.pre.self_improve import merge_constraints
from execution_harness.post.data_collector import DataCollector, TaskTrace
from execution_harness.post.self_eval import evaluate, EvalReport, report_to_json, fetch_baseline, update_baseline
from execution_harness.post.self_improve import (
    classify_defects, determine_improvement_level, build_improvement_prompt, ImprovementAction,
)
from execution_harness.post.capability_pool import (
    store_optimal_skills, store_case, store_defect_mapping, update_baseline_from_score, store_full_report,
)
from execution_harness.post.improvement_generator import (
    generate_improvements, format_improvement_prompt as format_improvement_prompt_list,
    ImprovementSuggestion,
)
from execution_harness.post.rubric_eval import evaluate_deliverable, RubricResult

logger = logging.getLogger("execution_harness.self_improve_loop")

_MAX_IMPROVEMENT_ROUNDS = 3  # 最多补强3轮


@dataclass
class ImprovementRound:
    round_num: int
    action: ImprovementAction
    eval_report: EvalReport
    rubric_result: Optional[RubricResult] = None
    deliverable: str = ""
    improvement_prompt: str = ""
    suggestions: list[ImprovementSuggestion] = field(default_factory=list)


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
    """Agent 自我提升闭环编排器。

    公开回调接口：
      on_execute_round(round_num, constraints, improvement_prompt) -> deliverable_content
        由外部调用者提供，返回本轮交付物的文本内容。
      on_log_event(kind, payload) -> None
        可选，用于将改进事件写入 run_event 或其他日志系统。
    """

    def __init__(
        self,
        agent_id: str,
        task_type: str,
        task_id: str,
        task_name: str,
        store: Optional[Store] = None,
        *,
        rubric_threshold: float = 60.0,
        execute_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
        max_rounds: int = _MAX_IMPROVEMENT_ROUNDS,
    ):
        self.agent_id = agent_id
        self.task_type = task_type
        self.task_id = task_id
        self.task_name = task_name
        self.store = store or Store()
        self.collector = DataCollector()
        self.collector.set_task(task_id, task_type, agent_id)
        self.rubric_threshold = rubric_threshold
        self._execute_callback = execute_callback
        self._log_callback = log_callback
        self._max_rounds = max_rounds

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

        # Step 1: 前置资产加载
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
        accumulated_improvement: str = ""

        for round_idx in range(1, self._max_rounds + 1):
            # Step 2-3: 执行 + 采集 — 由外部回调提供 deliverable
            deliverable = self._get_deliverable(round_idx, constraints, accumulated_improvement)

            if deliverable is None:
                # 外部回调未提供 deliverable，跳过本轮
                logger.warning("第 %d 轮未获得 deliverable，跳过", round_idx)
                continue

            base_deliverable = deliverable
            self.collector.record_output(deliverable)

            # Step 4: 量化评测
            trace = self.collector.finish()
            report = evaluate(
                deliverable, trace, constraints,
                task_type=self.task_type, store=self.store,
            )

            # Step 4b: Rubric 评估（从文件读取最新交付物）
            rubric_result = self._run_rubric_eval(deliverable)

            ir = ImprovementRound(
                round_num=round_idx,
                action=ImprovementAction(),
                eval_report=report,
                rubric_result=rubric_result,
                deliverable=deliverable,
            )
            result.improvements.append(ir)

            logger.info(
                "第 %d 轮评测: total=%.1f quality=%.1f passed=%s rubric_score=%.1f rubric_passed=%s",
                round_idx, report.total_score, report.quality_score,
                report.passed,
                rubric_result.total_score if rubric_result else 0,
                rubric_result.passed if rubric_result else False,
            )

            # Step 5: 判定是否达标（rubric score >= threshold）
            if rubric_result and rubric_result.total_score >= self.rubric_threshold:
                result.passed = True
                result.final_score = rubric_result.total_score
                result.baseline_diff = report.baseline_diff
                result.rounds = round_idx
                self._log_event("self_improve_pass", {
                    "rounds": round_idx,
                    "final_score": result.final_score,
                    "threshold": self.rubric_threshold,
                })
                break

            # 如果已经是最后一轮，直接退出
            if round_idx == self._max_rounds:
                result.final_score = rubric_result.total_score if rubric_result else report.total_score
                result.baseline_diff = report.baseline_diff
                result.rounds = round_idx
                break

            # Step 6: 分级补强 — 生成改进建议
            defects = classify_defects(report.defects)
            action = determine_improvement_level(
                report.total_score,
                result.baseline_score,
                report.defects,
                sum(1 for d in report.defects if d.get("severity") == "redline"),
            )
            ir.action = action

            # 从 rubric 生成具体改进建议
            suggestions = []
            if rubric_result:
                suggestions = generate_improvements(
                    rubric_result, deliverable,
                    task_type=self.task_type,
                )

            ir.suggestions = suggestions
            ir.action.description = (
                f"第{round_idx}轮补强: {len(suggestions)}条改进建议, "
                f"rubric={rubric_result.total_score:.1f}/100 (阈值{self.rubric_threshold}), "
                f"defects={len(report.defects)}"
            )

            # 格式化改进 prompt
            improvement_text = format_improvement_prompt_list(suggestions) if suggestions else ""
            if not improvement_text:
                # Fallback: 使用旧的 self_improve prompt 机制
                improvement_text = build_improvement_prompt(
                    action, self.task_name, report.summary, report.defects,
                )

            ir.improvement_prompt = improvement_text
            accumulated_improvement = improvement_text

            self._log_event("self_improve_round_failed", {
                "round": round_idx,
                "score": rubric_result.total_score if rubric_result else 0,
                "threshold": self.rubric_threshold,
                "suggestions_count": len(suggestions),
            })

            # 准备下一轮
            self.collector = DataCollector()
            self.collector.set_task(self.task_id, self.task_type, self.agent_id)
            self.collector.record_preferences(constraints.get("preferences", []))
            self.collector.record_skills([s["id"] for s in constraints.get("skills", [])])
            self.collector.record_kb([k["title"] for k in constraints.get("kb", [])])
            self.collector.inc_iteration()

        # Step 7: 达标后沉淀
        if result.passed and base_deliverable:
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

        # Step 8: 输出报表
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
            if last.rubric_result:
                report_data["rubric_score"] = last.rubric_result.total_score
                report_data["rubric_passed"] = last.rubric_result.passed
                report_data["rubric_redlines"] = last.rubric_result.hit_redlines
                report_data["rubric_dimension_failures"] = last.rubric_result.dimension_failures
            report_data["shortcomings"] = [
                {"dimension": d.get("dimension"), "detail": d.get("detail")}
                for d in last.eval_report.defects[:10]
            ]
            report_data["improvement_suggestions"] = [
                {
                    "dimension": s.dimension,
                    "what_to_fix": s.what_to_fix,
                    "how_to_fix": s.how_to_fix,
                    "priority": s.priority,
                }
                for s in last.suggestions
            ]
            report_data["current_action"] = {
                "action_type": last.action.action_type,
                "target_skills": last.action.target_skills if last.action.target_skills else [],
                "kb_fragments": last.action.kb_fragments[:3] if last.action.kb_fragments else [],
                "reload_preferences": last.action.reload_preferences,
                "full_rebuild": last.action.full_rebuild,
            }

        result.report_json = json.dumps(report_data, ensure_ascii=False, indent=2)
        store_full_report(self.agent_id, self.task_type, self.task_id, report_data, store=self.store)

        return result

    # ── Internal helpers ──────────────────────────────────────

    def _get_deliverable(
        self,
        round_num: int,
        constraints: dict,
        accumulated_improvement: str,
    ) -> Optional[str]:
        """获取本轮 deliverable。

        优先使用外部回调（execute_callback），否则尝试从文件读取。
        """
        # 外部回调
        if self._execute_callback:
            try:
                result = self._execute_callback(round_num, constraints, accumulated_improvement)
                if isinstance(result, str):
                    return result
            except Exception as e:
                logger.error("execute_callback failed: %s", e)

        # Fallback: 从上一轮的 deliverable 文件读取
        # 路径格式: business/tasks/project/<project_id>/deliverable/<task_id>/<task_type>/
        return None

    def _run_rubric_eval(self, deliverable: str) -> Optional[RubricResult]:
        """从 deliverable 文本执行 rubric 评估。"""
        try:
            return evaluate_deliverable(
                deliverable,
                task_type=self.task_type,
            )
        except Exception as e:
            logger.warning("rubric eval failed: %s", e)
            return None

    def _log_event(self, kind: str, payload: dict) -> None:
        """记录改进事件到 run_event 或外部日志回调。"""
        if self._log_callback:
            try:
                self._log_callback(kind, payload)
            except Exception as e:
                logger.warning("log_callback failed: %s", e)


def run_self_improve_loop(
    agent_id: str,
    task_type: str,
    task_id: str,
    task_name: str,
    deliverable_content: str,
    *,
    store: Optional[Store] = None,
    rubric_threshold: float = 60.0,
    intent: str = "",
    max_rounds: int = _MAX_IMPROVEMENT_ROUNDS,
) -> SelfImproveResult:
    """便捷函数：用已有的 deliverable 文本运行一轮评估。

    适用于 Gate 通过后、rubric 评分低于阈值时触发的单轮改进。
    不触发 agent 重跑，仅做评估和建议生成。

    Args:
        agent_id: Agent ID
        task_type: 任务类型
        task_id: 任务 ID
        task_name: 任务名称
        deliverable_content: 交付物文本内容
        store: Store 实例
        rubric_threshold: Rubric 通过阈值
        intent: 任务意图
        max_rounds: 最大改进轮次（仅用于兼容，单轮调用返回 1 轮）

    Returns:
        SelfImproveResult
    """
    loop = SelfImproveLoop(
        agent_id=agent_id,
        task_type=task_type,
        task_id=task_id,
        task_name=task_name,
        store=store,
        rubric_threshold=rubric_threshold,
        max_rounds=max_rounds,
    )
    return loop.run(intent=intent)
