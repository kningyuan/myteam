from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class ProjectMeta(BaseModel):
    """统一项目 meta schema（Phase 1.3）。"""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    budget: Optional[int] = None
    goal: str = ""
    workflow_id: str = ""
    coordinator_agent_id: str = ""
    cycle: int = 0
    extra: dict = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectMeta":
        if not d:
            return cls()
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)

class TaskMeta(BaseModel):
    """统一任务 meta schema。"""
    fail_reason: str = ""
    fail_detail: str = ""
    attempts: int = 0
    artifacts: list[dict] = Field(default_factory=list)
    ledger: Optional[dict] = None
    extra: dict = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskMeta":
        if not d:
            return cls()
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)
