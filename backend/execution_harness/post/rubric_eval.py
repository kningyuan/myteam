#!/usr/bin/env python3
"""Rubric-based Quality Evaluator — 基于 evaluation rubric 的自动化质量评审。

通过解析 rubric 规范文件中的可执行判定规则与红线，对 Agent 交付物进行
逐条自动化检查，产出结构化质量报告。

核心能力：
  - 关键词检索（模糊无量化词匹配）
  - 格式正则校验（章节完整性、数据源标注检测）
  - 结构化 DSL 识别（Mermaid / PlantUML / Graphviz）
  - 语义重复检测
  - 逻辑闭环检测（基础版）
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from common.store import Store

logger = logging.getLogger("execution_harness.post.rubric_eval")

# ── Rubric Template Registry ──────────────────────────────────

# Known task_type prefixes → template family mapping
_TASK_TYPE_FAMILIES: dict[str, str] = {
    # code family
    "code-deliverable": "code",
    "code-writing": "code",
    "code-testing": "testing",
    "coding": "code",
    "code-review": "code",
    "code-generation": "code",
    "test": "testing",
    "qa": "testing",
    # research family
    "research": "research",
    "product-research": "research",
    "market-research": "research",
    "competitive-analysis": "research",
    "literature-review": "research",
    # publish family
    "publish-post": "publish",
    "publish": "publish",
    "social-post": "publish",
    "content-publish": "publish",
    # architecture family
    "architecture": "architecture",
    "system-design": "architecture",
    "arch-review": "architecture",
    # documentation family
    "documentation": "documentation",
    "docs": "documentation",
    "api-docs": "documentation",
    # product family (default)
    "product": "product",
    "prd": "product",
    "requirements": "product",
    "strategy": "product",
    "product-planning": "product",
    "product-research": "research",
}

# Path to rubric templates YAML
# Resolution order: RUBRIC_TEMPLATES_PATH env var > relative to this file location
def _resolve_templates_path() -> Path:
    """Resolve the rubric templates YAML path."""
    env_path = os.environ.get("RUBRIC_TEMPLATES_PATH")
    if env_path:
        return Path(env_path)
    # Try to resolve relative to this module's actual location
    try:
        import __main__ as main_mod
        mod_dir = Path(main_mod.__file__).resolve().parent.parent.parent
        candidate = mod_dir / "business" / "config" / "rubric_templates.yaml"
        if candidate.is_file():
            return candidate
    except (AttributeError, ImportError):
        pass
    # Fallback: relative to CWD (works when run from repo root)
    return Path("business/config/rubric_templates.yaml")


_RUBRIC_TEMPLATES_PATH: Path = _resolve_templates_path()

# Cached template data
_loaded_templates: Optional[dict[str, Any]] = None


def _load_templates() -> dict[str, Any]:
    """Load rubric templates from YAML. Results are cached."""
    global _loaded_templates
    if _loaded_templates is not None:
        return _loaded_templates

    if not _RUBRIC_TEMPLATES_PATH.is_file():
        logger.warning("Rubric templates file not found: %s — falling back to defaults", _RUBRIC_TEMPLATES_PATH)
        _loaded_templates = {}
        return _loaded_templates

    try:
        with open(_RUBRIC_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "templates" in data:
            _loaded_templates = data["templates"]
        else:
            _loaded_templates = data
    except Exception as exc:
        logger.error("Failed to load rubric templates: %s", exc)
        _loaded_templates = {}

    return _loaded_templates


def resolve_template_family(task_type: str) -> str:
    """Map a task_type string to a rubric template family name.

    Falls back to "product" (the original rubric) when no mapping is found.
    """
    if not task_type:
        return "product"

    # Exact match first
    if task_type in _TASK_TYPE_FAMILIES:
        return _TASK_TYPE_FAMILIES[task_type]

    # Prefix match (e.g. "code-deliverable-v2" → "code")
    for prefix, family in _TASK_TYPE_FAMILIES.items():
        if task_type.startswith(prefix):
            return family

    # Default to product (original rubric)
    return "product"


def get_template(family: str) -> Optional[dict[str, Any]]:
    """Return the rubric template dict for a given family name."""
    templates = _load_templates()
    return templates.get(family)


def _check_dimension(template_dim: dict[str, Any], content: str) -> tuple[float, list[str]]:
    """Evaluate a single dimension against content.

    Returns (score_0_to_1, list_of_failure_reasons).
    """
    failures: list[str] = []
    checks = template_dim.get("checks", [])
    if not checks:
        return (1.0, [])

    scores: list[float] = []

    for check in checks:
        check_type = check.get("type", "")

        if check_type == "keyword":
            keywords = check.get("keywords", [])
            min_match = check.get("min_match", 1)
            matched = sum(1 for kw in keywords if kw.lower() in content.lower())
            if matched < min_match:
                missing = [kw for kw in keywords if kw.lower() not in content.lower()]
                failures.append(f"缺少关键词：{', '.join(missing[:3])}")
            scores.append(min(matched / max(min_match, 1), 1.0))

        elif check_type == "neg_keyword":
            forbidden = check.get("forbidden", [])
            max_match = check.get("max_match", 0)
            count = sum(1 for fw in forbidden if fw.lower() in content.lower())
            if count > max_match:
                hits = [fw for fw in forbidden if fw.lower() in content.lower()]
                failures.append(f"出现禁用词：{', '.join(hits[:3])}")
            scores.append(max(0.0, 1.0 - count))

        elif check_type == "pattern":
            regex_str = check.get("regex", "")
            min_matches = check.get("min_matches", 1)
            min_capture = check.get("min_capture", 0)
            matches = re.findall(regex_str, content)
            if len(matches) < min_matches:
                failures.append(f"模式 '{regex_str}' 匹配不足（期望≥{min_matches}，实际{len(matches)}）")
            if min_capture > 0 and matches:
                captured = int(matches[-1]) if matches else 0
                if captured < min_capture:
                    failures.append(f"捕获值 {captured} 低于阈值 {min_capture}")
            scores.append(min(len(matches) / max(min_matches, 1), 1.0))

        elif check_type == "content_length":
            min_chars = check.get("min_chars", 0)
            if min_chars and len(content) < min_chars:
                failures.append(f"内容过短（{len(content)} 字符，期望≥{min_chars}）")
            scores.append(min(len(content) / max(min_chars, 1), 1.0))

        elif check_type == "section":
            required = check.get("required", [])
            for section in required:
                if section not in content:
                    failures.append(f"缺失章节：{section}")
            scores.append(len(required) / max(len(required), 1))

        elif check_type == "structure":
            min_headings = check.get("min_headings", 1)
            heading_count = len(re.findall(r'^#{1,3}\s', content, re.MULTILINE))
            if heading_count < min_headings:
                failures.append(f"章节结构不足（{heading_count} 个标题，期望≥{min_headings}）")
            scores.append(min(heading_count / max(min_headings, 1), 1.0))

        elif check_type == "data_source":
            markers = check.get("markers", [])
            has_any = any(m in content for m in markers)
            if not has_any:
                failures.append("缺少数据来源标注")
            scores.append(1.0 if has_any else 0.0)

    if not scores:
        scores = [1.0]

    dim_score = sum(scores) / len(scores)
    return (round(dim_score, 3), failures)


def _compute_weighted_score(template: dict[str, Any], content: str) -> tuple[float, dict[str, float], dict[str, list[str]], list[str]]:
    """Evaluate all dimensions in a template against content.

    Returns:
        (weighted_total, dimension_scores, dimension_failures, redline_hits)
    """
    dimensions = template.get("dimensions", [])
    total_weight = 0.0
    weighted_sum = 0.0
    dim_scores: dict[str, float] = {}
    dim_failures: dict[str, list[str]] = {}

    for dim in dimensions:
        name = dim.get("name", "unknown")
        weight = dim.get("weight", 0.0)
        score, failures = _check_dimension(dim, content)
        dim_scores[name] = score
        if failures:
            dim_failures[name] = failures
        weighted_sum += score * weight
        total_weight += weight

    # Normalize by total weight
    if total_weight > 0:
        weighted_total = weighted_sum / total_weight
    else:
        weighted_total = 0.0

    # Check redlines
    redlines = template.get("redlines", [])
    redline_hits: list[str] = []
    for rl in redlines:
        # Each redline is a keyword/pattern — if found, it's a hit
        if rl.lower() in content.lower():
            redline_hits.append(rl)

    return (round(weighted_total, 4), dim_scores, dim_failures, redline_hits)


# ── Legacy constants (kept for backward compatibility) ────────

# 重复检索阈值（可通过 env 覆盖）
REPEAT_SEARCH_THRESHOLD = int(os.environ.get("RUBRIC_REPEAT_SEARCH_N", "3"))
# 模糊不可量化词列表
FUZZY_WORDS = frozenset({
    "提升体验", "加快响应", "提升用户", "优化体验", "更加便捷",
    "反应更快", "更流畅", "更高效", "更友好", "提升效率",
    "改善体验", "增强功能", "提高性能", "系统稳定",
})
# 数据源标注要求：关键字
DATA_SOURCE_MARKERS = frozenset({
    "来源", "数据源", "报告", "官网", "第三方", "引自",
    "据", "来源于", "数据来自",
})
# 结构化 DSL 标识
DSL_MARKERS = frozenset({
    "```mermaid", "```plantuml", "```puml", "```graphviz", "```dot",
})
# 产品思维四要素
THINKING_ELEMENTS = frozenset({
    "目标用户", "用户定位", "用户画像", "核心痛点", "用户痛点",
    "业务痛点", "解决方案", "应对方案", "产品方案",
    "衡量指标", "数据指标", "KPI", "关键指标", "效果评估",
})


@dataclass
class RubricResult:
    """单次 rubric 评估结果。"""
    passed: bool
    total_score: float = 0.0
    dimension_scores: dict[str, float] = field(default_factory=dict)
    dimension_failures: dict[str, list[str]] = field(default_factory=dict)
    hit_redlines: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    feedback: str = ""
    score_breakdown: str = ""


def _check_content_exists(content: str) -> bool:
    """检查内容是否非空。"""
    return bool(content and len(content.strip()) > 100)


def _check_section_exists(content: str, section_names: list[str]) -> list[str]:
    """检查必需章节是否存在。返回缺失列表。"""
    missing = []
    for name in section_names:
        if name not in content:
            missing.append(name)
    return missing


def _check_fuzzy_words(content: str) -> list[str]:
    """检测模糊不可量化词。返回命中列表。"""
    hits = []
    for word in FUZZY_WORDS:
        if word in content:
            hits.append(word)
    return hits


def _check_data_source(content: str) -> bool:
    """检测行业数据是否有来源标注。"""
    # 寻找含数字的数据声明（如 "800 万月活"、"50 亿"）
    data_patterns = re.findall(r'[\d,]+[万亿千万百万]+\s*(?:月活|用户|规模|收入|市场|占比)', content)
    if not data_patterns:
        return True  # 没有数据声明，跳过
    # 检查是否有来源标注
    for pattern in data_patterns[:5]:
        # 查找数据声明前后 200 字符内是否有来源标注
        idx = content.find(pattern)
        if idx == -1:
            continue
        window = content[max(0, idx - 200):idx + len(pattern) + 200]
        if not any(marker in window for marker in DATA_SOURCE_MARKERS):
            return False
    return True


def _check_diagram_format(content: str) -> bool:
    """检测流程图/架构图是否采用结构化 DSL。"""
    # 查找 "流程图"、"架构图" 相关章节
    diagram_sections = re.findall(
        r'(?:流程图|架构图|时序图|系统图|模块图)[^#\n]*(?:\n[^#\n]*)*',
        content,
    )
    for section in diagram_sections:
        if len(section) > 50 and not any(marker in section for marker in DSL_MARKERS):
            # 检查是否仅用文字/ASCII 描述
            ascii_chars = sum(1 for c in section if c in "+-|*/\\")
            if ascii_chars < 5 and len(section) > 100:
                return False  # 有图相关文字但无 DSL 代码块
    return True


def _check_thinking_elements(content: str) -> set[str]:
    """检测产品思维的 4 个必含要素。"""
    found = set()
    for element in THINKING_ELEMENTS:
        if element in content:
            found.add(element)
    # 归类
    categories = set()
    if found & {"目标用户", "用户定位", "用户画像"}:
        categories.add("目标用户定位")
    if found & {"核心痛点", "用户痛点", "业务痛点"}:
        categories.add("核心痛点拆解")
    if found & {"解决方案", "应对方案", "产品方案"}:
        categories.add("对应解决方案")
    if found & {"衡量指标", "数据指标", "KPI", "关键指标", "效果评估"}:
        categories.add("效果衡量数据指标")
    return categories


def _check_p0_p1_priority(content: str) -> bool:
    """检查是否有 P0/P1/P2 优先级标注。"""
    return bool(re.search(r'\bP[012]\b', content))


def _check_exception_scenarios(content: str) -> bool:
    """检查是否覆盖异常场景。"""
    exception_markers = frozenset({
        "异常", "边界", "空数据", "失败", "无权限", "超时",
        "错误处理", "容错", "降级", "兜底",
    })
    return any(marker in content for marker in exception_markers)


def _check_task_decomposition(content: str) -> bool:
    """检查任务拆解是否完整（分阶段）。"""
    phase_markers = frozenset({
        "调研", "问题分析", "方案设计", "风险评估",
        "阶段一", "阶段二", "阶段三", "Phase", "步骤",
    })
    return any(marker in content for marker in phase_markers)


def _check_deliverable_sections(deliverable_content: str) -> dict:
    """检查交付物完整性。

    使用模糊匹配，检测各类 PRD 常见章节。
    """
    missing = []
    present = []

    # 章节检测：使用关键词模糊匹配
    section_checks = [
        ("业务背景", ["业务背景", "项目背景", "背景", "现状"]),
        ("用户角色", ["用户角色", "目标用户", "角色定义", "目标人群", "利益相关者"]),
        ("正常流程", ["正常流程", "主流程", "核心流程", "业务流程", "流程图"]),
        ("异常分支", ["异常分支", "异常处理", "异常场景", "边界情况", "异常流程"]),
        ("验收指标", ["验收标准", "验收指标", "验收", "可验证"]),
        ("功能清单", ["功能清单", "功能模块", "功能列表", "产品功能"]),
        ("业务流程图", ["业务流程图", "流程图```", "```mermaid", "```plantuml", "```dot"]),
    ]

    for section_name, keywords in section_checks:
        found = any(kw in deliverable_content for kw in keywords)
        if found:
            present.append(section_name)
        else:
            missing.append(section_name)

    return {
        "present": present,
        "missing": missing,
        "completeness": len(present) / max(len(section_checks), 1),
    }


# ── 主评估接口 ─────────────────────────────────────────────


def evaluate_deliverable(
    deliverable_content: str,
    task_type: str = "",
    *,
    tool_logs: Optional[list[dict]] = None,
    execution_rounds: int = 1,
    total_retries: int = 0,
) -> RubricResult:
    """对 Agent 交付物执行完整的 Rubric 评估。

    Args:
        deliverable_content: 交付物全文（markdown 文本）
        task_type: 任务类型（影响维度权重和检查规则）
        tool_logs: 工具调用日志列表（可选，用于效率/鲁棒性评估）
        execution_rounds: 执行轮次
        total_retries: 总重试次数

    Returns:
        RubricResult: 结构化评估结果
    """
    result = RubricResult(passed=True)
    content = deliverable_content or ""

    if not _check_content_exists(content):
        result.passed = False
        result.feedback = "交付物为空或内容过短"
        return result

    # Resolve template family for this task_type
    family = resolve_template_family(task_type)
    template = get_template(family)

    if template and family != "product":
        # ── Template-driven evaluation ──
        pass_threshold = template.get("pass_threshold", 0.70)
        weighted_total, dim_scores, dim_failures, redline_hits = _compute_weighted_score(
            template, content
        )

        result.dimension_scores = dim_scores
        result.dimension_failures = dim_failures
        result.hit_redlines = redline_hits

        # Compute raw score (0-100)
        raw_score = weighted_total * 100
        result.total_score = round(raw_score, 1)

        # Determine pass
        result.passed = weighted_total >= pass_threshold
        if redline_hits:
            result.passed = False

        # Build feedback
        fb_lines = [f"### Rubric 评估报告（总分：{result.total_score:.1f}/100，模板：{family}）"]
        grade = _grade(result.total_score)
        fb_lines.append(f"**评级：{grade['label']}**")
        fb_lines.append("")

        # Dimension breakdown
        fb_lines.append("**维度评分：**")
        for dim_name, score in dim_scores.items():
            bar_len = int(score * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            fb_lines.append(f"  {dim_name}: {score:.2f} [{bar}]")
        fb_lines.append("")

        if dim_failures:
            fb_lines.append("**维度问题：**")
            for dim, failures in dim_failures.items():
                for f in failures:
                    fb_lines.append(f"  - ❌ {dim}: {f}")
            fb_lines.append("")

        if redline_hits:
            fb_lines.append("**⚠️ 命中红线（直接不通过）：**")
            for r in redline_hits:
                fb_lines.append(f"  - 🔴 {r}")
            fb_lines.append("")

        # Execution efficiency (still tracked via env params)
        eff_failures: list[str] = []
        if execution_rounds > 3:
            eff_failures.append(f"执行轮次过多（{execution_rounds} 轮）")
        if total_retries > 4:
            eff_failures.append(f"重试次数过多（{total_retries} 次）")
        if eff_failures:
            result.dimension_failures["执行效率"] = eff_failures

        fb_lines.append(f"**判定：{'✅ 通过' if result.passed else '❌ 不通过'}**")
        if not result.passed:
            fb_lines.append("需要修正后重新提交。")

        result.feedback = "\n".join(fb_lines)
        result.score_breakdown = (
            f"模板: {family}\n"
            f"阈值: {pass_threshold:.2f}\n"
            f"加权得分: {weighted_total:.4f}\n"
            + "\n".join(f"  {k}: {v:.3f}" for k, v in dim_scores.items())
        )
    else:
        # ── Legacy product-class evaluation (unchanged logic) ──
        _evaluate_product_legacy(result, content, execution_rounds, total_retries)

    return result


def _evaluate_product_legacy(
    result: RubricResult,
    content: str,
    execution_rounds: int,
    total_retries: int,
) -> None:
    """Legacy product-class evaluation logic (preserved for backward compatibility)."""
    if not _check_content_exists(content):
        result.passed = False
        result.feedback = "交付物为空或内容过短"
        return

    # ── 维度 1.1：需求目标匹配度 ──
    dim_1_1_failures: list[str] = []

    # 检查是否包含对业务约束/边界的讨论
    boundary_markers = frozenset({"约束", "边界", "范围", "限制", "前提条件"})
    if not any(m in content for m in boundary_markers):
        dim_1_1_failures.append("未标注业务约束/边界")

    # 检查角色/用户识别
    if not re.search(r'(?:用户|角色|人群|目标群体)', content):
        dim_1_1_failures.append("未识别目标用户或角色")

    if dim_1_1_failures:
        result.dimension_failures["需求目标匹配度"] = dim_1_1_failures
        result.dimension_scores["需求目标匹配度"] = 0.5

    # ── 维度 1.2：交付物完整度 ──
    dim_1_2_failures: list[str] = []
    sections = _check_deliverable_sections(content)

    if sections["missing"]:
        dim_1_2_failures.append(f"缺失章节：{'、'.join(sections['missing'][:5])}")
        result.missing_items.extend([f"缺失章节：{s}" for s in sections["missing"]])

    if not _check_diagram_format(content):
        dim_1_2_failures.append("流程图未使用结构化 DSL（Mermaid/PlantUML/Graphviz）")
        result.hit_redlines.append("流程图未使用结构化 DSL")

    if dim_1_2_failures:
        result.dimension_failures["交付物完整度"] = dim_1_2_failures
        result.dimension_scores["交付物完整度"] = 0.5

    # ── 维度 1.3：专业准确率 ──
    dim_1_3_failures: list[str] = []

    if not _check_data_source(content):
        dim_1_3_failures.append("行业数据/市场数据缺少来源标注")
        result.hit_redlines.append("行业数据无来源标注")

    # 检测模糊不可量化词
    fuzzy_hits = _check_fuzzy_words(content)
    if fuzzy_hits:
        dim_1_3_failures.append(f"使用模糊不可量化词：{'、'.join(fuzzy_hits[:3])}")
        result.hit_redlines.append(f"模糊词：{'、'.join(fuzzy_hits[:3])}")

    if dim_1_3_failures:
        result.dimension_failures["专业准确率"] = dim_1_3_failures
        result.dimension_scores["专业准确率"] = 0.5

    # ── 维度 1.4：落地可行性 ──
    dim_1_4_failures: list[str] = []

    feasibility_markers = frozenset({
        "技术成本", "开发成本", "运营成本", "现有系统", "现有架构",
        "折中", "替代方案", "轻量化", "分阶段", "落地约束",
    })
    if not any(m in content for m in feasibility_markers):
        dim_1_4_failures.append("未考虑落地约束（技术/运营/现有系统限制）")

    if dim_1_4_failures:
        result.dimension_failures["落地可行性"] = dim_1_4_failures
        result.dimension_scores["落地可行性"] = 0.5

    # ── 维度 2.1：任务拆解 ──
    dim_2_1_failures: list[str] = []

    if not _check_task_decomposition(content):
        dim_2_1_failures.append("缺少任务拆解/分阶段设计")

    if not _check_p0_p1_priority(content):
        dim_2_1_failures.append("未标注功能优先级（P0/P1/P2）")

    if dim_2_1_failures:
        result.dimension_failures["任务拆解"] = dim_2_1_failures
        result.dimension_scores["任务拆解"] = 0.5

    # ── 维度 2.2：信息调研 ──
    dim_2_2_failures: list[str] = []

    # 检查信息缺口标注
    info_gap_markers = frozenset({
        "信息缺口", "数据缺失", "已知不足", "需进一步调研",
        "缺少数据", "未获取到", "建议补充",
    })
    if not any(m in content for m in info_gap_markers):
        dim_2_2_failures.append("未标注信息缺口/数据缺失情况")

    if dim_2_2_failures:
        result.dimension_failures["信息调研"] = dim_2_2_failures
        result.dimension_scores["信息调研"] = 0.5

    # ── 维度 2.3：产品思维完整性 ──
    dim_2_3_failures: list[str] = []
    elements = _check_thinking_elements(content)
    if len(elements) < 2:
        dim_2_3_failures.append(
            f"产品思维不完整，仅覆盖：{'、'.join(elements) if elements else '无'}"
        )
        if "目标用户定位" not in elements:
            dim_2_3_failures.append("缺少目标用户定位")
        if "效果衡量数据指标" not in elements:
            dim_2_3_failures.append("缺少效果衡量数据指标")

    if dim_2_3_failures:
        result.dimension_failures["产品思维完整性"] = dim_2_3_failures
        result.dimension_scores["产品思维完整性"] = 0.5

    # ── 维度 2.4：思考可解释性 ──
    dim_2_4_failures: list[str] = []

    # 检查"为什么"、"基于"、"依据"等推导词
    reasoning_markers = frozenset({
        "基于", "原因是", "因为", "因此", "考虑到", "依据",
        "为了", "目标", "定位",
    })
    if not any(m in content for m in reasoning_markers):
        dim_2_4_failures.append("缺少功能设计的推导依据")

    if dim_2_4_failures:
        result.dimension_failures["思考可解释性"] = dim_2_4_failures
        result.dimension_scores["思考可解释性"] = 0.5

    # ── 维度 3：执行效率 ──
    dim_3_failures: list[str] = []

    if execution_rounds > 3:
        dim_3_failures.append(f"执行轮次过多（{execution_rounds} 轮）")
        result.hit_redlines.append(f"执行轮次{execution_rounds}超过上限3")
    if total_retries > 4:
        dim_3_failures.append(f"重试次数过多（{total_retries} 次）")

    # 检查无关科普内容比例
    if len(content) > 500:
        edu_markers = ("什么是", "是指", "是指的", "是一种", "指一种")
        edu_count = sum(content.count(m) for m in edu_markers)
        if edu_count > 5 and len(content) > 2000:
            dim_3_failures.append("含过多无关行业科普内容")

    if dim_3_failures:
        result.dimension_failures["执行效率"] = dim_3_failures
        result.dimension_scores["执行效率"] = 0.5

    # ── 维度 4：鲁棒性 ──
    dim_4_failures: list[str] = []

    if not _check_exception_scenarios(content):
        dim_4_failures.append("未覆盖异常场景（空数据/失败/无权限等）")
        result.hit_redlines.append("未覆盖异常场景")

    if dim_4_failures:
        result.dimension_failures["业务鲁棒性"] = dim_4_failures
        result.dimension_scores["业务鲁棒性"] = 0.5

    # ── 维度 5：合规与风险 ──
    dim_5_failures: list[str] = []

    privacy_markers = frozenset({
        "合规", "隐私", "数据合规", "风险", "安全",
        "授权", "权限管控", "数据保护",
    })
    if not any(m in content for m in privacy_markers):
        dim_5_failures.append("未标注合规/隐私风险")

    if dim_5_failures:
        result.dimension_failures["合规与风险"] = dim_5_failures
        result.dimension_scores["合规与风险"] = 0.5

    # ── 维度 6：交付可复用 ──
    dim_6_failures: list[str] = []

    # 检查文档结构化程度
    heading_count = len(re.findall(r'^#{1,3}\s', content, re.MULTILINE))
    if heading_count < 3:
        dim_6_failures.append("文档章节结构不清晰（标题过少）")

    if dim_6_failures:
        result.dimension_failures["交付可复用"] = dim_6_failures
        result.dimension_scores["交付可复用"] = 0.5

    # ── 总分计算 ──
    # 权重：结果产出 40%，专业过程 28%，效率 12%，鲁棒性 10%，合规 7%，交付复用 3%
    weights = {
        "结果产出": 0.40,
        "专业过程": 0.28,
        "执行效率": 0.12,
        "业务鲁棒性": 0.10,
        "合规与风险": 0.07,
        "交付可复用": 0.03,
    }

    # 维度 1 子项（结果产出）
    d1_scores = [
        result.dimension_scores.get("需求目标匹配度", 1.0),
        result.dimension_scores.get("交付物完整度", 1.0),
        result.dimension_scores.get("专业准确率", 1.0),
        result.dimension_scores.get("落地可行性", 1.0),
    ]
    d1_avg = sum(d1_scores) / len(d1_scores)

    # 维度 2 子项（专业过程）
    d2_scores = [
        result.dimension_scores.get("任务拆解", 1.0),
        result.dimension_scores.get("信息调研", 1.0),
        result.dimension_scores.get("产品思维完整性", 1.0),
        result.dimension_scores.get("思考可解释性", 1.0),
    ]
    d2_avg = sum(d2_scores) / len(d2_scores)

    # 其他维度
    d3_score = result.dimension_scores.get("执行效率", 1.0)
    d4_score = result.dimension_scores.get("业务鲁棒性", 1.0)
    d5_score = result.dimension_scores.get("合规与风险", 1.0)
    d6_score = result.dimension_scores.get("交付可复用", 1.0)

    total = (
        d1_avg * weights["结果产出"]
        + d2_avg * weights["专业过程"]
        + d3_score * weights["执行效率"]
        + d4_score * weights["业务鲁棒性"]
        + d5_score * weights["合规与风险"]
        + d6_score * weights["交付可复用"]
    )

    # 转换为百分制
    result.total_score = total * 100
    result.passed = result.total_score >= 60

    # 根据红线情况判定
    if result.hit_redlines:
        result.passed = False

    # 构建 feedback
    fb_lines = [f"### Rubric 评估报告（总分：{result.total_score:.1f}/100）"]
    grade = _grade(result.total_score)
    fb_lines.append(f"**评级：{grade['label']}**")
    fb_lines.append("")

    if result.hit_redlines:
        fb_lines.append("**⚠️ 命中红线（直接扣分）：**")
        for r in result.hit_redlines:
            fb_lines.append(f"  - 🔴 {r}")
        fb_lines.append("")

    for dim, failures in result.dimension_failures.items():
        if failures:
            fb_lines.append(f"**{dim} 问题：**")
            for f in failures:
                fb_lines.append(f"  - ❌ {f}")
            fb_lines.append("")

    if result.missing_items:
        fb_lines.append("**缺失项：**")
        for m in result.missing_items:
            fb_lines.append(f"  - 📋 {m}")
        fb_lines.append("")

    fb_lines.append(f"**判定：{'✅ 通过' if result.passed else '❌ 不通过'}**")
    if not result.passed:
        fb_lines.append("需要修正后重新提交。")

    result.feedback = "\n".join(fb_lines)
    result.score_breakdown = (
        f"结果产出: {d1_avg*100:.0f}/100（权40%）\n"
        f"专业过程: {d2_avg*100:.0f}/100（权28%）\n"
        f"执行效率: {d3_score*100:.0f}/100（权12%）\n"
        f"鲁棒性:   {d4_score*100:.0f}/100（权10%）\n"
        f"合规风险: {d5_score*100:.0f}/100（权7%）\n"
        f"交付复用: {d6_score*100:.0f}/100（权3%）"
    )

    return result


def _grade(score: float) -> dict:
    if score >= 90:
        return {"label": "🏆 优秀", "level": "优秀"}
    elif score >= 80:
        return {"label": "✅ 良好", "level": "良好"}
    elif score >= 70:
        return {"label": "⚠️ 合格", "level": "合格"}
    elif score >= 60:
        return {"label": "❌ 较差", "level": "较差"}
    else:
        return {"label": "🚫 不合格", "level": "不合格"}


def evaluate_task_output(
    store: Store,
    project_id: str,
    task_id: str,
    task_type: str,
    agent_id: str,
    deliverable_path: str,
    *,
    tool_logs: Optional[list[dict]] = None,
    execution_rounds: int = 1,
    attempt: int = 1,
) -> RubricResult:
    """从 Store 读取交付物并执行 Rubric 评估。

    这是集成到 task_pipeline 的主入口。
    """
    path = Path(deliverable_path)
    if not path.is_file():
        return RubricResult(
            passed=False,
            feedback=f"交付物文件不存在：{deliverable_path}",
        )

    content = path.read_text(encoding="utf-8", errors="replace")
    total_retries = max(0, attempt - 1)

    return evaluate_deliverable(
        content,
        task_type=task_type,
        tool_logs=tool_logs,
        execution_rounds=execution_rounds,
        total_retries=total_retries,
    )


def record_rubric_result(
    store: Store,
    project_id: str,
    task_id: str,
    task_type: str,
    agent_id: str,
    result: RubricResult,
) -> Optional[int]:
    """将 Rubric 评估结果写入 KB（供后续质量画像）。"""
    from execution_harness.post.quality import _QUALITY_TAG

    content_lines = [
        f"agent: {agent_id}",
        f"task_type: {task_type}",
        f"task_id: {task_id}",
        f"project_id: {project_id}",
        f"rubric_score: {result.total_score:.2f}",
        f"rubric_passed: {'yes' if result.passed else 'no'}",
    ]
    if result.hit_redlines:
        content_lines.append(f"红线条目：{'；'.join(result.hit_redlines)}")
    if result.dimension_failures:
        failures = []
        for dim, items in result.dimension_failures.items():
            failures.append(f"{dim}:{'、'.join(items[:3])}")
        content_lines.append(f"维度问题：{'；'.join(failures)}")
    content_lines.append(f"评分明细：\n{result.score_breakdown}")

    content = "\n".join(content_lines)
    title = f"rubric:{agent_id}/{task_type}:{task_id}"
    tags = [_QUALITY_TAG, "rubric", agent_id, task_type, project_id]
    return store.memory_write(project_id, title, content, tags=tags)