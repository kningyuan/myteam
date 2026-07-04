#!/usr/bin/env python3
"""质量约束检查测试（A 类结构性，绑交付模板 check_rules）。

验证 4 条约束能机器判并拦住 r1 曾暴露的缺陷：
- require_comparison_matrix：缺矩阵 → 拦
- dimension_coverage：缺维度 → 拦
- source_inline_required：量化数据无来源 → 拦
- no_unsourced_in_findings：关键发现内推断未标注 → 拦
- 合规产出 → 放行
详见 docs/quality-constraint-design.md。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.gate.gate import check_format  # noqa: E402
from common.gate.registry import FormatSpec  # noqa: E402


def _spec(**kw) -> FormatSpec:
    base = dict(
        task_type="research",
        display_name="调研",
        required_sections=["调研背景", "信息来源", "关键发现", "结论"],
        stub_floor=50,
    )
    base.update(kw)
    return FormatSpec(**base)


def _failure_codes(res) -> set[str]:
    return {f.get("rule") for f in res.failures}


# ── require_comparison_matrix ────────────────────────────────


def test_missing_matrix_blocked():
    """关键发现章节无 markdown 表格 → 拦。"""
    content = (
        "## 调研背景\n调研知乎/小红书/B站。\n\n"
        "## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n这里是纯文字描述，没有任何表格。\n\n"
        "## 结论\n建议 A。\n"
    )
    res = check_format(_spec(require_comparison_matrix=True), content)
    assert not res.passed
    assert "require_comparison_matrix" in _failure_codes(res)


def test_matrix_present_passes():
    """关键发现章节含 markdown 表格 → 放行（矩阵约束本身）。"""
    content = (
        "## 调研背景\n调研三平台。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n\n| 平台 | MAU | 变现 |\n|---|---|---|\n| 知乎 | 8100万 | 付费 |\n| 小红书 | 3亿 | 广告 |\n\n"
        "## 结论\n建议。\n"
    )
    res = check_format(_spec(require_comparison_matrix=True), content)
    assert "require_comparison_matrix" not in _failure_codes(res)


def test_matrix_min_rows_blocked():
    """矩阵数据行数不足 → 拦。"""
    content = (
        "## 关键发现\n\n| 平台 | MAU |\n|---|---|\n| 知乎 | 8100万 |\n\n"
    )
    res = check_format(_spec(require_comparison_matrix=True, matrix_min_rows=3), content)
    assert "matrix_min_rows" in _failure_codes(res)


def test_matrix_empty_cell_blocked():
    """矩阵格子为空或占位 → 拦。"""
    content = (
        "## 关键发现\n\n| 平台 | 评价 | 画像 |\n|---|---|---|\n| 知乎 | 好 | - |\n| 小红书 |  | 女 |\n\n"
    )
    res = check_format(_spec(require_comparison_matrix=True, matrix_no_empty_cell=True), content)
    assert "matrix_no_empty_cell" in _failure_codes(res)


# ── dimension_coverage ───────────────────────────────────────


def test_missing_dimension_blocked():
    """维度词（核心功能）在全文未出现 → 拦。"""
    content = (
        "## 调研背景\n调研三平台。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n用户画像与变现模式对比。\n\n## 结论\n建议。\n"
    )
    res = check_format(
        _spec(dimension_coverage=["核心功能", "用户画像", "变现模式"]), content
    )
    codes = _failure_codes(res)
    assert "dimension_coverage" in codes


def test_dimensions_present_passes():
    """所有维度词在正文出现且有上下文 → 放行。"""
    content = (
        "## 调研背景\n调研三平台核心功能与用户画像。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n核心功能方面三平台差异显著；用户画像各有侧重；变现模式分化。\n\n"
        "## 结论\n建议。\n"
    )
    res = check_format(
        _spec(dimension_coverage=["核心功能", "用户画像", "变现模式"]), content
    )
    assert "dimension_coverage" not in _failure_codes(res)


# ── source_inline_required ───────────────────────────────────


def test_unsourced_number_blocked():
    """量化数字后无来源编号 → 拦。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n知乎月活8100万，B站3.33亿。\n\n## 结论\n建议。\n"
    )
    res = check_format(_spec(source_inline_required=True), content)
    assert "source_inline_required" in _failure_codes(res)


def test_sourced_number_passes():
    """量化数字后跟 [S1] 来源编号 → 放行。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n知乎月活8100万[S1]，B站3.33亿[S1]。\n\n## 结论\n建议。\n"
    )
    res = check_format(_spec(source_inline_required=True), content)
    assert "source_inline_required" not in _failure_codes(res)


def test_sourced_number_with_paren_note_passes():
    """数字后跟括号注释再跟来源（常见形态）→ 放行，不误判。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n[S4] 维基\n\n"
        "## 关键发现\n小红书 MAU 超 3 亿（截至 2024 Q4，数据已过期）[S4]。\n\n## 结论\n建议。\n"
    )
    res = check_format(_spec(source_inline_required=True), content)
    assert "source_inline_required" not in _failure_codes(res)


def test_source_table_numbers_not_checked():
    """信息来源表内的数字不验来源位置（表格天然带 url/编号列）→ 放行。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n"
        "| 编号 | 来源 | URL | 采集时间 | 可信度 |\n|---|---|---|---|---|\n"
        "| S1 | 维基 | http://x | 2026-07 | L2 |\n\n"
        "## 关键发现\n知乎月活8100万[S1]。\n\n## 结论\n建议。\n"
    )
    res = check_format(_spec(source_inline_required=True), content)
    assert "source_inline_required" not in _failure_codes(res)


# ── no_unsourced_in_findings ─────────────────────────────────


def test_inference_without_label_blocked():
    """关键发现内「推断」后未标注「无公开来源」→ 拦。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n知乎用户以高学历群体为主（推断），内容深度高。\n\n"
        "## 结论\n建议。\n"
    )
    res = check_format(_spec(no_unsourced_in_findings=True), content)
    assert "no_unsourced_in_findings" in _failure_codes(res)


def test_inference_with_label_passes():
    """关键发现内「推断」后标注「无公开来源」→ 放行。"""
    content = (
        "## 调研背景\n调研。\n\n## 信息来源\n[S1] 维基\n\n"
        "## 关键发现\n知乎用户以高学历群体为主（推断，无公开来源），内容深度高。\n\n"
        "## 结论\n建议。\n"
    )
    res = check_format(_spec(no_unsourced_in_findings=True), content)
    assert "no_unsourced_in_findings" not in _failure_codes(res)


# ── 合规产出 ─────────────────────────────────────────────────


def test_fully_compliant_report_passes():
    """满足全部 4 条约束的合规报告 → 全放行。"""
    content = (
        "## 调研背景\n对知乎、小红书、B站三平台核心功能、用户画像、变现模式、用户评价对比调研。\n\n"
        "## 信息来源\n| 编号 | 来源 | URL | 采集时间 | 可信度 |\n|---|---|---|---|---|\n| S1 | 维基 | http://x | 2026-07 | L2 |\n\n"
        "## 关键发现\n"
        "三平台核心功能差异显著，用户画像各有侧重，变现模式分化。\n\n"
        "| 平台 | 核心功能 | 用户画像 | 变现 | 评价 |\n|---|---|---|---|---|\n"
        "| 知乎 | 问答 | 高学历（推断，无公开来源） | 付费 | 4.7分[S1] |\n"
        "| 小红书 | 种草 | 年轻女性 | 广告 | 4.9分[S1] |\n"
        "| B站 | 视频 | Z世代 | 游戏 | 暂无数据 |\n\n"
        "## 结论\nP0：差异化定位（输出：定位报告）。\n"
    )
    spec = _spec(
        require_comparison_matrix=True,
        dimension_coverage=["核心功能", "用户画像", "变现模式", "用户评价"],
        source_inline_required=True,
        no_unsourced_in_findings=True,
    )
    res = check_format(spec, content)
    # 矩阵有格子是「暂无数据」（非空占位），不触发 empty_cell（未开）
    # 推断已标注，不触发 no_unsourced
    # 4.7分[S1] 有来源，不触发 source_inline
    assert res.passed, f"合规报告应放行，失败项：{res.failures}"
