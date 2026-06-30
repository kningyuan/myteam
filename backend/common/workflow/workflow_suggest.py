#!/usr/bin/env python3
"""根据 workflow 描述确定性推导任务 DAG（无 LLM，供 Hub 编辑页「自动推导」）。

模板数据从 business/templates/workflow_suggest.json 加载，移除硬编码。
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from common.paths import workflow_suggest_templates_file
from common.workflow.workflow_capability_bind import (
    bind_workflow_tasks_to_capabilities,
    capability_bind_warnings,
)
from common.workflow.workflow_loader import roster_from_tasks, validate_workflow, WorkflowProfile


_TEMPLATES_CACHE: dict[str, Any] | None = None


def _load_templates() -> dict[str, Any]:
    """加载 workflow_suggest.json；结果在模块级别缓存。"""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is not None:
        return _TEMPLATES_CACHE
    path = workflow_suggest_templates_file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法加载 workflow_suggest 模板文件 {path}: {exc}") from exc
    _TEMPLATES_CACHE = data
    return data


_PLACEHOLDER_KEYS: dict[str, str] = {}


def _get_placeholder(key: str) -> str:
    if not _PLACEHOLDER_KEYS:
        data = _load_templates()
        _PLACEHOLDER_KEYS.update(data.get("placeholders", {}))
    return _PLACEHOLDER_KEYS.get(key, "")


def _match_any(text: str, *patterns: str) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in patterns)


def _extract_github_url(text: str) -> str:
    m = re.search(r"https?://github\.com/[\w.-]+/[\w.-]+", text, re.I)
    return m.group(0) if m else ""


def _default_options() -> dict[str, Any]:
    return {
        "review_enabled": False,
        "split_enabled": True,
        "parallel_enabled": False,
        "max_parallel": 3,
    }


def _lookup_pattern(desc: str) -> tuple[str, list[dict], dict[str, Any]]:
    """根据描述文本匹配 pattern key、任务模板、选项覆写。"""
    if _match_any(
        desc,
        "github",
        "开源",
        "仓库",
        "三视角",
        "产品/架构",
        "产品架构",
    ):
        key = "github-parallel-research"
    elif _match_any(desc, "冒烟", "最小", "简单", "smoke", "速览"):
        key = "smoke-research"
    elif _match_any(desc, "数据分析", "指标口径", "留存分析", "转化漏斗", "sql 报表", "数据报表"):
        key = "data-analysis-pipeline"
    elif _match_any(desc, "geo", "生成式引擎", "perplexity", "ai搜索", "ai 搜索", "可引用性"):
        key = "geo-pipeline"
    elif _match_any(desc, "发布", "知乎", "公众号", "社媒"):
        key = "content-publish-pipeline"
    elif _match_any(desc, "内容", "seo", "营销", "战役", "campaign", "文章"):
        key = "content-pipeline"
    elif _match_any(desc, "软件", "交付", "开发", "实现", "delivery", "hotfix"):
        key = "delivery-lite"
    elif _match_any(
        desc,
        "产品规划",
        "方案完善",
        "区块链",
        "架构图",
        "产品架构",
        "系统架构",
        "word 文档",
        "ppt",
        "deck",
    ):
        key = "product-plan-improve"
    elif _match_any(desc, "并行", "parallel"):
        key = "github-parallel-research"
    else:
        key = "linear-research"

    data = _load_templates()
    pattern = data["patterns"].get(key, data["patterns"]["linear-research"])
    options = dict(_default_options())
    options.update(pattern.get("options", {}))
    return key, deepcopy(pattern["tasks"]), options


def suggest_workflow_from_description(description: str) -> dict[str, Any]:
    """从自然语言描述推导 tasks + options；绑定 Agent 能力后校验。"""
    desc = (description or "").strip()
    if not desc:
        raise ValueError("描述不能为空")

    pattern_key, tasks, options = _lookup_pattern(desc)

    gh = _extract_github_url(desc)
    if gh:
        gh_obj = _get_placeholder("gh_obj")
        for t in tasks:
            desc_text = t.get("description", "")
            if "GitHub" in desc_text or "github" in desc_text.lower():
                t["description"] = desc_text.replace(gh_obj, f"【对象】{gh}")

    tasks = bind_workflow_tasks_to_capabilities(tasks)
    warnings = capability_bind_warnings(tasks)

    data = _load_templates()
    label = data["patterns"].get(pattern_key, {}).get("label", pattern_key)

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
        "pattern": pattern_key,
        "pattern_label": label,
        "warnings": warnings,
        "workflow": {
            "name": label,
            "tasks": tasks,
            "options": options,
        },
    }