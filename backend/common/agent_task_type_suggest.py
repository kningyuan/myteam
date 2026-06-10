#!/usr/bin/env python3
"""根据 Agent 职责描述确定性推导可执行 task_type 列表（无 LLM、无 CLI）。"""
from __future__ import annotations

import re
from typing import Any

from common.registry import load_registry
from common.task_type_store import list_task_type_ids

# (关键词, 推荐 task_types)
_AGENT_RULES: list[tuple[list[str], list[str]]] = [
    (["项目经理", "协调", "仲裁", "部署", "决策"], ["strategy", "decision-record", "code-deployment"]),
    (["产品", "需求", "验收", "优先级"], ["requirements", "strategy", "acceptance-report", "research", "architecture-review"]),
    (["架构", "系统设计", "API", "内核"], ["system-design", "architecture-review", "code-review", "research"]),
    (["研发", "开发", "实现", "工程师", "代码"], ["code-writing", "code-deliverable", "code-review", "system-design"]),
    (["前端", "UI", "交互"], ["system-design", "code-writing", "architecture-review", "code-review"]),
    (["测试", "QA", "质量", "回归"], ["test-plan", "code-testing", "code-review", "architecture-review"]),
    (["调研", "竞品", "研究员"], ["research", "architecture-review"]),
    (["数据分析", "指标", "报表", "分析师", "SQL", "可视化"], ["data-analysis", "research", "strategy", "code-writing"]),
    (["GEO", "生成式引擎", "Perplexity", "AI搜索", "可引用"], ["geo-plan", "geo-audit", "geo-verification", "research", "content"]),
    (["SEO", "关键词", "搜索引擎"], ["seo-plan", "research"]),
    (["内容", "写作", "文章", "文案", "编辑"], ["content", "architecture-review"]),
    (["文档", "说明书", "README"], ["content"]),
    (["发布", "知乎", "专栏", "zhihu"], ["publish-post"]),
    (["发布", "小红书", "笔记", "xhs"], ["publish-post"]),
    (["发布", "公众号", "社媒", "运营"], ["publish-post"]),
    (["运维", "部署", "回滚"], ["code-deployment"]),
]


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def suggest_task_types_for_agent(
    description: str,
    *,
    name: str = "",
    agent_id: str = "",
) -> dict[str, Any]:
    """从 Agent 描述推导 task_types；返回 {task_types, matched_rules}。"""
    blob = _norm(f"{name} {agent_id} {description}")
    if not blob:
        raise ValueError("描述不能为空")

    known = set(list_task_type_ids())
    hits: list[str] = []
    matched: list[str] = []

    for keywords, tts in _AGENT_RULES:
        if any(kw.lower() in blob for kw in keywords):
            matched.append(keywords[0])
            for t in tts:
                if t in known and t not in hits:
                    hits.append(t)

    # 显式提及 task_type id 时纳入
    for tid in known:
        if re.search(rf"\b{re.escape(tid)}\b", blob) and tid not in hits:
            hits.append(tid)

    if not hits:
        hits = ["research"]

    return {"task_types": hits, "matched_rules": matched}
