#!/usr/bin/env python3
"""Process 配置与结果类型 — 从 process.py 拆出，供编排与单测复用。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from store.system_config import system_config

TERMINAL_OK = {"completed", "needs_review"}
TERMINAL_BAD = {"failed", "blocked"}


class BudgetExceededError(Exception):
    """交互级 budget 硬停：AgentPort 在 interaction 进行中检测到超预算。"""


@dataclass
class ProcessConfig:
    mode: str = "one_shot"                 # one_shot | recurring
    max_gate_retries: int = 3              # 确定性门禁失败的重试上限（D18 → D19 PATCH 减为 3）
    max_plan_retries: int = 2              # task_plan 指派团队外 agent 时的重试上限
    review_enabled: bool = False           # 是否走同行评审（TaskPipeline.peer_review）
    quality_floor: float = 0.6             # 自评低于此 → needs_review
    needs_review_blocks: bool = False      # needs_review 是否阻塞依赖者（默认否，D18）
    enforce_must_include: bool = False     # 透传 Gate（D14 默认关）
    inject_context: bool = True            # 注入直接上游摘要+引用（D16 第 1 层）
    token_budget: Optional[int] = None     # per-project token 硬上限（D17；None=不限）
    budget_alert_ratio: float = 0.8        # 预算告警阈值
    budget_degrade_threshold: float = 0.8  # L3：达此比例触发降级（默认 80%）
    budget_degrade_backend: str = ""       # L3：降级目标 backend（空=不改）
    budget_degrade_model: str = ""         # L3：降级目标 model（空=不改）
    skill_extract_enabled: bool = False    # L3：项目完成后是否触发 skill 抽提
    max_cycles: int = 3                    # recurring 模式的周期上限（防空转，D10）
    split_enabled: bool = False            # evaluate 拆分：派发前 + 执行中待调度任务；默认关，opt-in
    max_split_depth: int = 2               # 递归拆分深度上限 → 终止性硬底（无论 agent 怎么判都收敛）
    max_subtasks: int = 8                  # 单次拆分子任务数上限（防扇出爆炸）
    coordinator_agent_id: str = field(
        default_factory=lambda: system_config.get("system", "coordinator_agent_id", default="main")
    )
    deputy_agent_id: str = "deputy"        # 副协调者 ID（workers_only 排除用）
    auto_create_agents: bool = True        # team_config 时自动创建未就绪 agent
    default_backend: str = "opencode"      # 自动创建 agent 时的默认后端
    default_model: str = ""                # 自动创建 agent 时的默认模型
    parallel_enabled: bool = False         # L2：同波次无依赖任务真并行
    max_parallel: int = 4                  # 单波次最大并发任务数
    plan_enabled: bool = True              # 路径 A：execute 前是否插入 plan 交互


@dataclass
class TaskOutcome:
    task_id: str
    status: str                            # completed | needs_review | failed | blocked
    reason: str = ""
    attempts: int = 0
    response: Optional[dict] = None


@dataclass
class TaskExecuteResult:
    """单任务执行结果（含 triage 与失败时拆分）。"""

    outcome: TaskOutcome
    triage_decision: Optional[str] = None
    split_subtasks: Optional[list[dict]] = None


@dataclass
class ProjectOutcome:
    project_id: str
    status: str                            # completed | partially_failed | failed | aborted
    tasks: dict[str, TaskOutcome] = field(default_factory=dict)
