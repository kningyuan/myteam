#!/usr/bin/env python3
"""根据 workflow 描述确定性推导任务 DAG（无 LLM，供 Hub 编辑页「自动推导」）。"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from common.workflow_capability_bind import (
    bind_workflow_tasks_to_capabilities,
    capability_bind_warnings,
)
from common.workflow_loader import roster_from_tasks, validate_workflow, WorkflowProfile

_OBJ_PLACEHOLDER = "【对象】目标见【项目目标】"
_GH_OBJ = "【对象】目标 GitHub 仓库（链接见【项目目标】）"
_SCOPE_README = "【范围】仅 README、docs/、Releases；禁止全仓扫源码"


def _match_any(text: str, *patterns: str) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in patterns)


def _extract_github_url(text: str) -> str:
    m = re.search(r"https?://github\.com/[\w.-]+/[\w.-]+", text, re.I)
    return m.group(0) if m else ""


def _github_parallel_tasks() -> list[dict]:
    return [
        {
            "id": "t-product",
            "name": "产品设计调研",
            "agent": "product",
            "task_type": "research",
            "dependencies": [],
            "description": (
                f"{_GH_OBJ}\n"
                "【视角】产品：定位、目标用户、核心场景、与同类差异\n"
                f"{_SCOPE_README}"
            ),
        },
        {
            "id": "t-arch",
            "name": "架构调研",
            "agent": "arch",
            "task_type": "research",
            "dependencies": [],
            "description": (
                f"{_GH_OBJ}\n"
                "【视角】架构：技术栈、模块划分、集成方式、扩展点\n"
                f"{_SCOPE_README}"
            ),
        },
        {
            "id": "t-eng",
            "name": "工程化调研",
            "agent": "developer",
            "task_type": "research",
            "dependencies": [],
            "description": (
                f"{_GH_OBJ}\n"
                "【视角】工程化：构建/测试/CI、依赖、本地开发体验\n"
                f"{_SCOPE_README}"
            ),
        },
        {
            "id": "t-summary",
            "name": "三视角综合报告",
            "agent": "main",
            "task_type": "strategy",
            "dependencies": ["t-product", "t-arch", "t-eng"],
            "description": "【输入】只读 t-product、t-arch、t-eng 三份交付物",
        },
    ]


def _smoke_tasks() -> list[dict]:
    return [
        {
            "id": "t1",
            "name": "调研",
            "agent": "research",
            "task_type": "research",
            "dependencies": [],
            "description": f"{_OBJ_PLACEHOLDER}\n{_SCOPE_README}",
        },
        {
            "id": "t2",
            "name": "汇总",
            "agent": "main",
            "task_type": "strategy",
            "dependencies": ["t1"],
            "description": "【输入】只读 t1 交付物",
        },
    ]


def _content_pipeline_tasks(*, with_publish: bool = False) -> list[dict]:
    tasks = [
        {
            "id": "t-research",
            "name": "调研",
            "agent": "research",
            "task_type": "research",
            "dependencies": [],
            "description": f"{_OBJ_PLACEHOLDER}\n【视角】行业/竞品/受众",
        },
        {
            "id": "t-strategy",
            "name": "策略",
            "agent": "product",
            "task_type": "strategy",
            "dependencies": ["t-research"],
            "description": "【输入】只读 t-research；输出内容策略与排期",
        },
        {
            "id": "t-content",
            "name": "内容产出",
            "agent": "content",
            "task_type": "content",
            "dependencies": ["t-strategy"],
            "description": "【输入】只读 t-strategy；按策略撰写正文",
        },
    ]
    if with_publish:
        tasks.append({
            "id": "t-publish",
            "name": "发布",
            "agent": "social",
            "task_type": "publish-post",
            "dependencies": ["t-content"],
            "description": "【输入】只读 t-content；在目标平台发布并附 URL/截图证据",
        })
    return tasks


def _data_analysis_tasks() -> list[dict]:
    return [
        {
            "id": "t-req",
            "name": "分析需求",
            "agent": "product",
            "task_type": "requirements",
            "dependencies": [],
            "description": f"{_OBJ_PLACEHOLDER}\n【视角】指标口径、分析目标、验收标准",
        },
        {
            "id": "t-analysis",
            "name": "数据分析报告",
            "agent": "analyst",
            "task_type": "data-analysis",
            "dependencies": ["t-req"],
            "description": "【输入】只读 t-req；输出结构化分析报告（按 task_type 章节）",
        },
        {
            "id": "t-script",
            "name": "分析脚本",
            "agent": "analyst",
            "task_type": "code-writing",
            "dependencies": ["t-analysis"],
            "description": "【输入】只读 t-analysis；交付可复用分析脚本/Notebook",
        },
        {
            "id": "t-accept",
            "name": "验收",
            "agent": "product",
            "task_type": "acceptance-report",
            "dependencies": ["t-script"],
            "description": "【输入】只读 t-analysis、t-script；对照 t-req 验收",
        },
    ]


def _geo_pipeline_tasks() -> list[dict]:
    return [
        {
            "id": "t-research",
            "name": "GEO 背景调研",
            "agent": "research",
            "task_type": "research",
            "dependencies": [],
            "description": f"{_OBJ_PLACEHOLDER}\n【视角】AI 搜索可见性、竞品引用、受众问题",
        },
        {
            "id": "t-plan",
            "name": "GEO 策略",
            "agent": "geo",
            "task_type": "geo-plan",
            "dependencies": ["t-research"],
            "description": "【输入】只读 t-research；输出 GEO 优化策略",
        },
        {
            "id": "t-audit",
            "name": "页面审计",
            "agent": "geo",
            "task_type": "geo-audit",
            "dependencies": ["t-plan"],
            "description": "【输入】只读 t-plan；审计目标页面可引用性与结构",
        },
        {
            "id": "t-content",
            "name": "内容改稿",
            "agent": "content",
            "task_type": "content",
            "dependencies": ["t-audit"],
            "description": "【输入】只读 t-audit；按审计意见改稿",
        },
        {
            "id": "t-verify",
            "name": "效果验证",
            "agent": "geo",
            "task_type": "geo-verification",
            "dependencies": ["t-content"],
            "description": "【输入】只读 t-content；执行验证动作并附 URL/截图",
        },
    ]


def _delivery_lite_tasks() -> list[dict]:
    return [
        {
            "id": "t-research",
            "name": "调研",
            "agent": "research",
            "task_type": "research",
            "dependencies": [],
            "description": _OBJ_PLACEHOLDER,
        },
        {
            "id": "t-req",
            "name": "需求",
            "agent": "product",
            "task_type": "requirements",
            "dependencies": ["t-research"],
            "description": "【输入】只读 t-research",
        },
        {
            "id": "t-design",
            "name": "方案设计",
            "agent": "arch",
            "task_type": "system-design",
            "dependencies": ["t-req"],
            "description": "【输入】只读 t-req",
        },
        {
            "id": "t-implement",
            "name": "实现",
            "agent": "developer",
            "task_type": "code-writing",
            "dependencies": ["t-design"],
            "description": "【输入】只读 t-design",
        },
    ]


def _linear_research_tasks() -> list[dict]:
    return [
        {
            "id": "t1",
            "name": "调研",
            "agent": "research",
            "task_type": "research",
            "dependencies": [],
            "description": _OBJ_PLACEHOLDER,
        },
        {
            "id": "t2",
            "name": "分析汇总",
            "agent": "main",
            "task_type": "strategy",
            "dependencies": ["t1"],
            "description": "【输入】只读 t1 交付物",
        },
    ]


WF_PATTERN_LABEL = {
    "github-parallel-research": "GitHub 三视角并行调研",
    "smoke-research": "最小调研+汇总",
    "content-pipeline": "内容生产流水线",
    "content-publish-pipeline": "内容生产+发布",
    "data-analysis-pipeline": "数据分析流水线",
    "geo-pipeline": "GEO 优化流水线",
    "delivery-lite": "轻量软件交付",
    "linear-research": "调研+汇总",
}


def suggest_workflow_from_description(description: str) -> dict[str, Any]:
    """从自然语言描述推导 tasks + options；绑定 Agent 能力后校验。"""
    desc = (description or "").strip()
    if not desc:
        raise ValueError("描述不能为空")

    pattern = "linear-research"
    options: dict[str, Any] = {
        "review_enabled": False,
        "split_enabled": False,
        "parallel_enabled": False,
        "max_parallel": 3,
    }

    if _match_any(
        desc,
        "github",
        "开源",
        "仓库",
        "三视角",
        "产品/架构",
        "产品架构",
    ):
        pattern = "github-parallel-research"
        tasks = _github_parallel_tasks()
        options["parallel_enabled"] = True
        options["max_parallel"] = 3
    elif _match_any(desc, "冒烟", "最小", "简单", "smoke", "速览"):
        pattern = "smoke-research"
        tasks = _smoke_tasks()
    elif _match_any(desc, "数据分析", "指标口径", "留存分析", "转化漏斗", "sql 报表", "数据报表"):
        pattern = "data-analysis-pipeline"
        tasks = _data_analysis_tasks()
    elif _match_any(desc, "geo", "生成式引擎", "perplexity", "ai搜索", "ai 搜索", "可引用性"):
        pattern = "geo-pipeline"
        tasks = _geo_pipeline_tasks()
    elif _match_any(desc, "发布", "知乎", "公众号", "社媒"):
        pattern = "content-publish-pipeline"
        tasks = _content_pipeline_tasks(with_publish=True)
    elif _match_any(desc, "内容", "seo", "营销", "战役", "campaign", "文章"):
        pattern = "content-pipeline"
        tasks = _content_pipeline_tasks(with_publish=False)
    elif _match_any(desc, "软件", "交付", "开发", "实现", "delivery", "hotfix"):
        pattern = "delivery-lite"
        tasks = _delivery_lite_tasks()
    elif _match_any(desc, "并行", "parallel"):
        pattern = "github-parallel-research"
        tasks = _github_parallel_tasks()
        options["parallel_enabled"] = True
        options["max_parallel"] = 3
    else:
        tasks = _linear_research_tasks()

    tasks = deepcopy(tasks)
    gh = _extract_github_url(desc)
    if gh:
        for t in tasks:
            if "GitHub" in t.get("description", "") or "github" in t.get("description", "").lower():
                t["description"] = t["description"].replace(_GH_OBJ, f"【对象】{gh}")

    tasks = bind_workflow_tasks_to_capabilities(tasks)
    warnings = capability_bind_warnings(tasks)

    roster = roster_from_tasks(tasks)
    profile = WorkflowProfile(
        id="suggest-preview",
        version="1.0",
        description=desc,
        roster=roster,
        tasks=tasks,
        options=options,
    )
    validate_workflow(profile)

    return {
        "pattern": pattern,
        "pattern_label": WF_PATTERN_LABEL.get(pattern, pattern),
        "warnings": warnings,
        "workflow": {
            "name": WF_PATTERN_LABEL.get(pattern, pattern),
            "tasks": tasks,
            "options": options,
        },
    }
