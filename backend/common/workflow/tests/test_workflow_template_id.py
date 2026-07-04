#!/usr/bin/env python3
"""workflow template_id 校验。"""
from __future__ import annotations

import pytest

from common.workflow.workflow_loader import WorkflowProfile, validate_workflow


def test_validate_workflow_rejects_unknown_template_id():
    profile = WorkflowProfile(
        id="test-wf",
        version="1.0",
        description="",
        roster=["main", "product"],
        tasks=[
            {
                "id": "t1",
                "name": "req",
                "agent": "product",
                "task_type": "research",  # 已注册的 task_type
                "template_id": "no-such-template-xyz",  # 但 template 不存在
                "dependencies": [],
            },
        ],
    )
    with pytest.raises(ValueError, match="未找到交付模板"):
        validate_workflow(profile)
