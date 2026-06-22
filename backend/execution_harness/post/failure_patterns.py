"""失败模式分类 — Path D：将 Gate 失败映射到 5 类可操作失败模式（文档约定）。"""

from __future__ import annotations

from typing import Any

# 5 类失败模式（文档约定）
PATTERN_SECTION_MISSING = "section_missing"     # 章节缺失
PATTERN_CONTENT_STUB = "content_stub"           # 内容空洞/占位
PATTERN_FORMAT_ERROR = "format_error"           # 格式/层级错误
PATTERN_TIMEOUT_INTERRUPT = "timeout_interrupt"  # 超时中断（非 Gate 来源，由端口状态设置）
PATTERN_PLAN_DRIFT = "plan_drift"               # 偏离计划/未遵循约束

# rule → 失败模式映射
_RULE_TO_PATTERN: dict[str, str] = {
    # 章节缺失
    "required_sections": PATTERN_SECTION_MISSING,

    # 内容空洞
    "stub": PATTERN_CONTENT_STUB,
    "must_include": PATTERN_CONTENT_STUB,

    # 格式/层级
    "section_level": PATTERN_FORMAT_ERROR,

    # 偏离计划 — 未按契约/结构/证据要求执行
    "file_exists": PATTERN_PLAN_DRIFT,
    "process_artifact": PATTERN_PLAN_DRIFT,
    "contract": PATTERN_PLAN_DRIFT,
    "evidence_url": PATTERN_PLAN_DRIFT,
    "evidence_screenshot": PATTERN_PLAN_DRIFT,
    "evidence_title": PATTERN_PLAN_DRIFT,
    "code_project": PATTERN_PLAN_DRIFT,
    "min_project_files": PATTERN_PLAN_DRIFT,
    "required_extensions": PATTERN_PLAN_DRIFT,
    "code_file": PATTERN_PLAN_DRIFT,
}

_PATTERN_LABEL: dict[str, str] = {
    PATTERN_SECTION_MISSING: "📋 章节缺失",
    PATTERN_CONTENT_STUB: "📝 内容空洞",
    PATTERN_FORMAT_ERROR: "🔧 格式错误",
    PATTERN_TIMEOUT_INTERRUPT: "⏱️ 超时中断",
    PATTERN_PLAN_DRIFT: "🧭 偏离计划",
}

_PATTERN_GUIDANCE: dict[str, str] = {
    PATTERN_SECTION_MISSING: (
        "请检查交付物是否完整包含了要求的全部章节。"
        "章节标题必须与模板逐字一致，按要求的标题层级（## 或 #）书写。"
        "遗漏的章节请补充完整正文，不要仅写标题。"
    ),
    PATTERN_CONTENT_STUB: (
        "内容过于简略或仍为模板占位。"
        "请用实质性内容替换占位文本，每个章节应有足够深度的论述。"
        "避免仅写标题或一两句概括。"
    ),
    PATTERN_FORMAT_ERROR: (
        "章节标题层级或格式不符合模板要求。"
        "请确保每个章节的标题层级（# 数）与模板一致，章节名逐字匹配。"
        "注意不要在代码块或引用中隐藏章节标题。"
    ),
    PATTERN_TIMEOUT_INTERRUPT: (
        "执行被超时或中断打断，产出可能不完整。"
        "请确认交付物已写完所有章节，不要有截断的内容。"
        "如有未完成的分析，请注明并提交已有成果。"
    ),
    PATTERN_PLAN_DRIFT: (
        "交付物结构或产出与任务要求不一致。"
        "请重新阅读任务约束，检查是否遗漏了要求的文件、证据或响应结构。"
        "确保交付物覆盖了全部验收标准。"
    ),
}


def classify_failure(rule: str) -> str:
    """将 Gate 规则名映射到失败模式类别。"""
    return _RULE_TO_PATTERN.get(rule, PATTERN_FORMAT_ERROR)


def pattern_label(pattern: str) -> str:
    return _PATTERN_LABEL.get(pattern, "❓ 其他错误")


def pattern_guidance(pattern: str) -> str:
    return _PATTERN_GUIDANCE.get(pattern, "请根据失败描述排查问题后重新提交。")


def classify_failures(failures: list[dict]) -> list[dict]:
    """批量分类失败项，每项附加 pattern/label/guidance。

    Input:  ``[{"rule": "required_sections", "expected": "...", "actual": "..."}, ...]``
    Output: 每项增加 ``pattern`` / ``label`` / ``guidance`` 字段。
    """
    out: list[dict[str, Any]] = []
    for f in failures:
        rule = f.get("rule", "")
        pattern = classify_failure(rule)
        out.append({
            **f,
            "pattern": pattern,
            "label": pattern_label(pattern),
            "guidance": pattern_guidance(pattern),
        })
    return out


def build_classified_summary(failures: list[dict]) -> str:
    """构建分类摘要（用于 retry 反馈中定位根因）。

    额外参数可通过 failure dict 的 ``skip_pattern`` 跳过特定分类。
    超时中断（timeout_interrupt）不来自 Gate，需调用方在 failures 中
    显式加入 ``{"rule": "", "pattern": "timeout_interrupt"}``。
    """
    if not failures:
        return ""
    by_pattern: dict[str, list[str]] = {}
    for f in failures:
        p = f.get("pattern") or classify_failure(f.get("rule", ""))
        by_pattern.setdefault(p, []).append(f.get("rule", ""))
    lines: list[str] = ["【失败根因分类】"]
    for p, rules in by_pattern.items():
        label = _PATTERN_LABEL.get(p, "其他")
        rule_names = "、".join(sorted(set(rules)))
        lines.append(f"  {label}：涉及 {rule_names}")
    lines.append("")
    return "\n".join(lines)