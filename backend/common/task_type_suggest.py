#!/usr/bin/env python3
"""根据任务类型描述确定性推导 templates.yaml 草稿（无 LLM、无 CLI）。"""
from __future__ import annotations

import re
from typing import Any

from common.task_type_store import list_task_type_ids

# Gate 仅识别三种 outcome_kind；下拉文案覆盖常见现实任务形态
OUTCOME_KIND_CATALOG: list[dict[str, Any]] = [
    {
        "id": "artifact",
        "label": "文档报告 artifact",
        "summary": "Markdown 结构化交付物",
        "covers": [
            "调研 / 竞品 / 行业分析",
            "需求 / 用户故事 / 验收标准",
            "策略 / 方案对比 / 决策备忘",
            "架构评审 / 代码评审 / 测试计划",
            "验收报告 / 部署记录（文档式）",
        ],
        "examples": ["research", "requirements", "strategy", "architecture-review", "test-plan"],
    },
    {
        "id": "action",
        "label": "动作证据 action",
        "summary": "须证明「已在外部完成动作」",
        "covers": [
            "内容发布（知乎/公众号等 URL + 截图）",
            "线上配置 / 开关 / 发布操作留痕",
            "任何需要 URL、截图、平台回执的验收",
        ],
        "examples": ["publish-post", "code-deployment"],
    },
    {
        "id": "code_project",
        "label": "代码工程 code_project",
        "summary": "deliverables/<task_id>/ 可运行工程",
        "covers": [
            "功能实现 / 脚本 / 工具交付",
            "补丁 / hotfix / 可执行代码包",
            "须含 README、源码与运行说明",
        ],
        "examples": ["code-writing", "code-deliverable"],
    },
]

_PRESETS: dict[str, dict[str, Any]] = {
    "research-survey": {
        "display_name": "调研报告",
        "outcome_kind": "artifact",
        "id_base": "research",
        "sections": ["调研背景", "信息来源", "关键发现", "结论"],
    },
    "requirements": {
        "display_name": "需求文档",
        "outcome_kind": "artifact",
        "id_base": "requirements",
        "sections": ["背景与目标", "用户与场景", "功能需求", "验收标准"],
    },
    "strategy": {
        "display_name": "策略分析",
        "outcome_kind": "artifact",
        "id_base": "strategy",
        "sections": ["背景", "分析", "方案", "建议"],
    },
    "system-design": {
        "display_name": "系统设计",
        "outcome_kind": "artifact",
        "id_base": "system-design",
        "sections": ["问题与约束", "领域与边界", "架构方案", "接口契约", "演化与风险"],
    },
    "architecture-review": {
        "display_name": "架构评审",
        "outcome_kind": "artifact",
        "id_base": "architecture-review",
        "sections": ["评审范围", "现状摘要", "发现与分级", "技术债务", "演进建议"],
    },
    "code-review": {
        "display_name": "代码评审",
        "outcome_kind": "artifact",
        "id_base": "code-review",
        "sections": ["评审范围", "变更摘要", "发现与分级", "合并建议"],
    },
    "test-plan": {
        "display_name": "测试计划",
        "outcome_kind": "artifact",
        "id_base": "test-plan",
        "sections": ["测试范围", "测试用例", "正常路径", "边界条件", "异常路径"],
    },
    "code-delivery": {
        "display_name": "代码交付",
        "outcome_kind": "code_project",
        "id_base": "code-deliverable",
        "sections": ["实现说明", "运行方式", "变更清单"],
    },
    "code-writing": {
        "display_name": "代码实现",
        "outcome_kind": "code_project",
        "id_base": "code-writing",
        "sections": ["实现说明", "运行方式", "自测说明"],
    },
    "content": {
        "display_name": "内容创作",
        "outcome_kind": "artifact",
        "id_base": "content",
        "sections": ["选题与受众", "大纲", "正文", "发布建议"],
    },
    "publish-action": {
        "display_name": "内容发布",
        "outcome_kind": "action",
        "id_base": "publish-post",
        "sections": ["发布平台", "帖子标题", "已发布URL", "证据截图"],
    },
    "acceptance": {
        "display_name": "验收报告",
        "outcome_kind": "artifact",
        "id_base": "acceptance-report",
        "sections": ["验收范围", "通过项", "阻塞项", "结论"],
    },
    "decision-record": {
        "display_name": "决策记录",
        "outcome_kind": "artifact",
        "id_base": "decision-record",
        "sections": ["背景", "备选方案", "决策", "后续行动"],
    },
    "generic-document": {
        "display_name": "通用文档",
        "outcome_kind": "artifact",
        "id_base": "document",
        "sections": ["背景", "正文", "结论"],
    },
    "data-analysis": {
        "display_name": "数据分析",
        "outcome_kind": "artifact",
        "id_base": "data-analysis",
        "sections": ["分析问题与口径", "数据来源与质量", "分析过程与方法", "关键发现", "结论与行动建议"],
    },
    "geo-plan": {
        "display_name": "GEO策略规划",
        "outcome_kind": "artifact",
        "id_base": "geo-plan",
        "sections": ["目标引擎与场景", "内容可引用性诊断", "结构化与实体策略", "权威来源与E-E-A-T", "试点与度量指标"],
    },
    "geo-audit": {
        "display_name": "GEO内容审计",
        "outcome_kind": "artifact",
        "id_base": "geo-audit",
        "sections": ["审计范围", "现状摘要", "GEO问题分级", "改写与结构建议", "优先级与排期"],
    },
    "geo-verification": {
        "display_name": "GEO效果验证",
        "outcome_kind": "action",
        "id_base": "geo-verification",
        "sections": ["目标页面URL", "目标查询", "AI引擎与回答摘要", "引用情况", "证据截图"],
    },
}

_CN_TO_ID: list[tuple[str, str]] = [
    ("调研", "survey"), ("竞品", "competitive"), ("分析", "analysis"),
    ("需求", "requirements"), ("用户故事", "user-story"),
    ("架构", "architecture"), ("设计", "design"), ("评审", "review"),
    ("代码", "code"), ("实现", "implementation"), ("开发", "dev"),
    ("测试", "test"), ("内容", "content"), ("文章", "article"),
    ("发布", "publish"), ("策略", "strategy"), ("验收", "acceptance"),
    ("决策", "decision"), ("部署", "deploy"), ("github", "github"),
    ("仓库", "repo"), ("报告", "report"), ("方案", "plan"),
]


def _match_any(text: str, *patterns: str) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in patterns)


def _slugify_id(text: str) -> str:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text)
    if words:
        return "-".join(w.lower()[:24] for w in words[:4])
    parts: list[str] = []
    low = text.lower()
    for cn, en in _CN_TO_ID:
        if cn in text or cn in low:
            parts.append(en)
    if parts:
        return "-".join(dict.fromkeys(parts))[:32]
    return "custom-task"


def _unique_task_type_id(base: str) -> str:
    slug = re.sub(r"[^\w-]", "", (base or "custom-task").strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or "custom-task"
    slug = slug[:32]
    existing = set(list_task_type_ids())
    if slug not in existing:
        return slug
    for i in range(2, 100):
        cand = f"{slug}-{i}"
        if cand not in existing:
            return cand
    return f"{slug}-x"


def _pick_pattern(desc: str) -> str:
    if _match_any(desc, "发布", "上线", "知乎", "公众号", "url", "截图", "publish", "post"):
        return "publish-action"
    if _match_any(desc, "代码交付", "可运行", "脚本交付", "code-deliverable", "工程交付"):
        return "code-delivery"
    if _match_any(desc, "写代码", "编码", "实现功能", "开发任务", "hotfix", "补丁", "code-writing"):
        return "code-writing"
    if _match_any(desc, "测试计划", "测试用例", "qa", "test plan", "回归"):
        return "test-plan"
    if _match_any(desc, "代码评审", "code review", "cr "):
        return "code-review"
    if _match_any(desc, "架构评审", "设计评审", "architecture review"):
        return "architecture-review"
    if _match_any(desc, "系统设计", "方案设计", "system design", "技术方案"):
        return "system-design"
    if _match_any(desc, "需求", "用户故事", "prd", "requirements"):
        return "requirements"
    if _match_any(desc, "验收", "acceptance"):
        return "acceptance"
    if _match_any(desc, "决策", "adr", "decision"):
        return "decision-record"
    if _match_any(desc, "内容", "seo", "文章", "文案", "content"):
        return "content"
    if _match_any(desc, "geo验证", "引用验证", "ai搜索验证", "效果验证", "geo verification"):
        return "geo-verification"
    if _match_any(desc, "geo审计", "页面审计", "geo audit", "可引用性审计"):
        return "geo-audit"
    if _match_any(desc, "geo", "生成式引擎", "generative engine", "perplexity", "ai搜索优化"):
        return "geo-plan"
    if _match_any(desc, "数据分析", "指标", "口径", "sql", "报表", "data analysis"):
        return "data-analysis"
    if _match_any(desc, "调研", "竞品", "行业", "research", "survey", "github", "仓库"):
        return "research-survey"
    if _match_any(desc, "策略", "方案对比", "strategy"):
        return "strategy"
    return "generic-document"


def _display_name_from_desc(desc: str, preset_name: str) -> str:
    line = desc.strip().split("\n")[0].strip()
    if 2 <= len(line) <= 32:
        return line
    return preset_name


def suggest_task_type_from_description(description: str) -> dict[str, Any]:
    """从自然语言描述推导 task_type 草稿；纯规则，不调用 CLI/LLM。"""
    desc = (description or "").strip()
    if not desc:
        raise ValueError("描述不能为空")

    pattern = _pick_pattern(desc)
    preset = _PRESETS[pattern]
    id_from_desc = _slugify_id(desc)
    id_base = preset["id_base"]
    # 描述里能抽出更贴切的 slug 时优先，否则用模板 id_base
    candidate = id_from_desc if id_from_desc != "custom-task" else id_base
    if candidate == id_base and id_base in set(list_task_type_ids()):
        candidate = id_from_desc if id_from_desc != id_base else id_base

    task_type = _unique_task_type_id(candidate)
    display_name = _display_name_from_desc(desc, preset["display_name"])

    return {
        "pattern": pattern,
        "engine": "rules",
        "engine_note": "本地关键词规则匹配，不调用 opencode/claude CLI",
        "task_type": task_type,
        "display_name": display_name,
        "outcome_kind": preset["outcome_kind"],
        "required_sections": list(preset["sections"]),
        "outcome_catalog": OUTCOME_KIND_CATALOG,
    }


def list_outcome_kind_catalog() -> list[dict[str, Any]]:
    return list(OUTCOME_KIND_CATALOG)
