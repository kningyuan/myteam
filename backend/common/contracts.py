#!/usr/bin/env python3
"""Interaction 统一契约（D11 / D5 / D15）。

框架 ↔ Agent 之间只交换一对结构：InteractionRequest / InteractionResponse，
用 `kind` 做辨识联合（team_config | task_plan | evaluate | execute | review）。

设计原则（D11）：
  - 结构进代码（这里的 Pydantic 模型 + 导出 JSON Schema 给 Agent）。
  - 内容约束进配置（格式注册表，见 templates.yaml / Phase 4）。
  - submit_result 在 Agent 侧按引用本地校验后才写回，框架侧用同一模型再校验
    → 从根上消灭 JSON 抢救（D1/F1）。契约路径已是唯一路径，旧 JSON 抢救与
    INTERACTION_CONTRACTS 迁移开关已删除。
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, model_validator

SCHEMA_VERSION = "1.0"

Kind = Literal["team_config", "task_plan", "evaluate", "execute", "review", "triage"]


# ── 共享子结构 ───────────────────────────────────────────────


class Quality(BaseModel):
    """Agent 自评（D11：execute/review 强制必填）。质量归 Agent，框架只记录。"""

    score: float = Field(ge=0.0, le=1.0, description="自评分 0..1")
    known_gaps: list[str] = Field(default_factory=list)
    notes: str = ""


class Meta(BaseModel):
    """计量/归因（D8）。"""

    model: Optional[str] = None
    backend: Optional[str] = None
    tokens: Optional[int] = None


# ── Outcome = Artifact ∪ Action（D5 / D15）────────────────────


class Artifact(BaseModel):
    path: str
    format: str = "markdown"
    title: str = ""


class Evidence(BaseModel):
    action_type: str
    target: str = ""
    url: str = ""
    screenshots: list[str] = Field(default_factory=list)
    external_id: str = ""
    performed_at: str = ""


class Outcome(BaseModel):
    """一个 task_type 只有一个主 kind（D15）。

    - artifact 始终存在：artifact 类=成果文档；action 类=动作记录文档。
    - evidence 仅 action 类必填：硬证据（URL/截图/external_id）。
    """

    kind: Literal["artifact", "action"]
    artifact: Artifact
    evidence: Optional[Evidence] = None

    @model_validator(mode="after")
    def _check_evidence(self):
        if self.kind == "action" and self.evidence is None:
            raise ValueError("outcome.kind=action 时 evidence 必填（硬证据）")
        return self


# ── 各 kind 的 result（D11）──────────────────────────────────


class TeamConfigResult(BaseModel):
    agents: list[str] = Field(min_length=1)


class PlannedTask(BaseModel):
    id: str
    name: str
    agent: str
    task_type: str
    description: str
    reviewer: str = ""
    dependencies: list[str] = Field(default_factory=list)


class TaskPlanResult(BaseModel):
    tasks: list[PlannedTask] = Field(min_length=1)


class EvaluateResult(BaseModel):
    should_split: bool
    reason: str = ""
    # 子任务 = 完整 PlannedTask：强制带 task_type（registry 锚）+ agent（team 锚），
    # 与顶层任务同一套校验，递归拆解不绕过锚点。agent/task_type 留空时由框架回填父任务值。
    sub_tasks: list[PlannedTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_split(self):
        if self.should_split and not self.sub_tasks:
            raise ValueError("should_split=true 时 sub_tasks 不能为空")
        return self


class ExecuteResult(BaseModel):
    outcome: Outcome


class ReviewResult(BaseModel):
    passed: bool
    feedback: str = ""
    checklist: list[dict] = Field(default_factory=list)


class TriageResult(BaseModel):
    """重试耗尽后委托 Main 的决策（D18）。"""

    decision: Literal["retry", "reassign", "drop", "abort"]
    target_agent: str = ""
    notes: str = ""


# ── Response 信封（辨识联合）─────────────────────────────────


class _BaseResponse(BaseModel):
    interaction_id: str
    schema_version: str = SCHEMA_VERSION
    status: Literal["ok", "needs_retry", "failed"] = "ok"
    quality: Optional[Quality] = None
    meta: Optional[Meta] = None
    notes: str = ""


class TeamConfigResponse(_BaseResponse):
    kind: Literal["team_config"]
    result: TeamConfigResult


class TaskPlanResponse(_BaseResponse):
    kind: Literal["task_plan"]
    result: TaskPlanResult


class EvaluateResponse(_BaseResponse):
    kind: Literal["evaluate"]
    result: EvaluateResult


class ExecuteResponse(_BaseResponse):
    kind: Literal["execute"]
    result: ExecuteResult

    @model_validator(mode="after")
    def _require_quality(self):
        if self.status == "ok" and self.quality is None:
            raise ValueError("execute 响应（status=ok）必须包含 quality 自评（D11）")
        return self


class ReviewResponse(_BaseResponse):
    kind: Literal["review"]
    result: ReviewResult

    @model_validator(mode="after")
    def _require_quality(self):
        if self.status == "ok" and self.quality is None:
            raise ValueError("review 响应（status=ok）必须包含 quality 自评（D11）")
        return self


class TriageResponse(_BaseResponse):
    kind: Literal["triage"]
    result: TriageResult


InteractionResponse = Annotated[
    Union[
        TeamConfigResponse,
        TaskPlanResponse,
        EvaluateResponse,
        ExecuteResponse,
        ReviewResponse,
        TriageResponse,
    ],
    Field(discriminator="kind"),
]

_RESPONSE_ADAPTER = TypeAdapter(InteractionResponse)

_RESPONSE_MODEL_BY_KIND: dict[str, type[_BaseResponse]] = {
    "team_config": TeamConfigResponse,
    "task_plan": TaskPlanResponse,
    "evaluate": EvaluateResponse,
    "execute": ExecuteResponse,
    "review": ReviewResponse,
    "triage": TriageResponse,
}


# ── Request 信封 ─────────────────────────────────────────────


class InteractionRequest(BaseModel):
    interaction_id: str
    schema_version: str = SCHEMA_VERSION
    kind: Kind
    project_id: str
    task_id: Optional[str] = None
    agent_id: str
    intent: str = ""
    input: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    response_schema: str = ""  # 指向注册表引用，如 "execute.result@1.0"
    constraints: dict = Field(default_factory=dict)
    deadline_sec: Optional[int] = None
    retry_feedback: list[str] = Field(default_factory=list)


# ── 校验入口（供 submit_result / 框架侧复用）─────────────────


def parse_response(data: dict):
    """把 dict 反序列化为对应 kind 的响应模型；非法则抛 ValidationError。"""
    return _RESPONSE_ADAPTER.validate_python(data)


def validate_response_dict(data: dict) -> tuple[bool, Optional[object], list[str]]:
    """校验响应 dict。

    Returns: (ok, model_or_None, error_messages)
    """
    try:
        model = parse_response(data)
        return True, model, []
    except ValidationError as e:
        return False, None, [_fmt_error(err) for err in e.errors()]
    except Exception as e:  # 非 dict / 缺 kind 等
        return False, None, [str(e)]


def parse_request(data: dict) -> InteractionRequest:
    return InteractionRequest.model_validate(data)


def _fmt_error(err: dict) -> str:
    loc = ".".join(str(p) for p in err.get("loc", ()))
    return f"{loc}: {err.get('msg', '')}".strip(": ")


def response_json_schema(kind: str) -> dict:
    """导出某 kind 响应的 JSON Schema（下发给 Agent 本地校验用）。"""
    model = _RESPONSE_MODEL_BY_KIND.get(kind)
    if model is None:
        raise ValueError(f"未知 kind：{kind}")
    return model.model_json_schema()
