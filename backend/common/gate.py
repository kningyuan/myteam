#!/usr/bin/env python3
"""Gate — 框架确定性门禁（D14 / D15）。

原则：框架门禁只判**契约 + 格式 + 完整性**（客观/确定性/可复现/阻塞）；
**质量（好坏）归 Agent**（自评 + 同行评审），框架不判。

三类（D14）：
  1. 契约门禁：响应符合 Interaction 契约（contracts.validate_response_dict）。
  2. 格式/完整性门禁：对照格式注册表——必需章节 / 标题层级 / file_exists / 防 stub；
     action 型校验证据（URL 形态 + 截图存在；实时核对标题为加分项，被反爬拦截不硬失败）。
  3. 质量：不在此（自评 D11 + cross_review）。

变化（相对旧 quality_gate）：
  - min_length → 防 stub 下限（registry.is_stub），不当质量指标。
  - must_include → 默认**关**（enforce_must_include=False），仅结构性契约 token 例外。
  - 按 outcome_kind 取规则（artifact / action）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.contracts import validate_response_dict
from common.registry import FormatSpec, get_spec, is_stub  # FormatSpec used by check_code_project

# 复用 quality_gate 的证据校验工具，避免重复实现
from common.quality_gate import (  # noqa: E402
    EVIDENCE_VERIFY_OFF,
    _URL_RE,
    _extract_field,
    verify_published_url,
)

# PGD 阶段闸门：决策/验收类交付物始终校验 must_include（阻塞项清零等）
_PGD_STRICT_TYPES = frozenset({"decision-record", "acceptance-report"})


@dataclass
class GateResult:
    passed: bool
    failures: list[dict] = field(default_factory=list)
    skipped: bool = False
    feedback: str = ""

    def add(self, rule: str, expected: str, actual: str):
        self.failures.append({"rule": rule, "expected": expected, "actual": actual})
        self.passed = False


def check_contract(response: dict) -> GateResult:
    """契约门禁：响应须符合 Interaction 契约。"""
    ok, _model, errors = validate_response_dict(response)
    res = GateResult(passed=ok)
    if not ok:
        for e in errors:
            res.add("contract", "符合 Interaction 契约", e)
    return res


def check_format(spec: FormatSpec, content: str, deliverable_path: Optional[str] = None,
                 *, enforce_must_include: bool = False) -> GateResult:
    """格式/完整性门禁：必需章节 / 标题层级 / file_exists / 防 stub（+可选 must_include）。"""
    res = GateResult(passed=True)

    # 防 stub（D14：取代 min_length 的质量代理）
    if is_stub(content, spec.stub_floor):
        res.add("stub", f"非空且非占位（≥{spec.stub_floor} 有效字符）", "内容疑似 stub/占位")

    # 必需章节（结构性契约）
    for section in spec.required_sections:
        if section not in content:
            res.add("required_sections", section, "未找到此章节")

    # 章节标题层级
    if spec.sections:
        clean = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        heading = "#" * spec.required_heading_level
        for sec in spec.sections:
            if not isinstance(sec, dict):
                continue
            name = sec.get("name", "")
            if not name or not sec.get("required", True):
                continue
            if not re.search(rf"^{heading}\s+[^\n]*{re.escape(name)}", clean, re.MULTILINE):
                res.add("section_level", f"{heading} {name}", "未找到此层级的章节标题")

    # 引用文件存在
    base = Path(deliverable_path).parent if deliverable_path else Path(".")
    for ref in spec.file_exists:
        if not (base / ref).exists():
            res.add("file_exists", str(base / ref), "文件不存在")

    # must_include：默认关（仅显式要求时）
    if enforce_must_include:
        for kw in spec.must_include:
            if kw not in content:
                res.add("must_include", kw, "未找到此关键词")

    if not res.passed:
        res.feedback = _feedback(spec.task_type, res.failures)
    return res


def check_action_evidence(spec: FormatSpec, content: str,
                          deliverable_path: Optional[str] = None) -> GateResult:
    """action 型证据校验（D15）：合规已发布 URL + 截图存在；实时核对标题为加分项。"""
    res = GateResult(passed=True)
    cfg = spec.evidence or {}
    if not cfg:
        return res

    host_contains = cfg.get("host_contains", "")
    url_must_match = cfg.get("url_must_match", "")
    urls = _URL_RE.findall(content)
    if host_contains:
        urls = [u for u in urls if host_contains in u]
    if url_must_match:
        urls = [u for u in urls if url_must_match in u]
    if not urls:
        want = url_must_match or host_contains or "http(s)"
        res.add("evidence_url", f"含 {want} 的已发布 URL", "未找到合规的已发布 URL")
        return res
    published_url = urls[0]

    shot_field = cfg.get("screenshot_field", "")
    if shot_field and deliverable_path:
        shot = _extract_field(content, shot_field)
        if shot:
            shot_path = Path(deliverable_path).parent / shot
            if not shot_path.exists():
                res.add("evidence_screenshot", f"截图文件存在：{shot_path}", "截图文件不存在")

    if cfg.get("verify_title") and not EVIDENCE_VERIFY_OFF:
        title = _extract_field(content, "帖子标题")
        verified, blocked, detail = verify_published_url(published_url, title)
        if not verified and not blocked:  # 被反爬拦截(blocked)不硬失败
            res.add("evidence_title", f"已发布页含标题「{title}」", detail)

    if not res.passed:
        res.feedback = _feedback(spec.task_type, res.failures)
    return res


_CODE_EXTS = {".py", ".sh", ".js", ".ts", ".go", ".rb", ".java", ".rs"}


def check_code_project(spec: FormatSpec, proj_dir: Path) -> GateResult:
    """代码工程型交付物：校验目录存在、最少文件数、必选文件、代码文件。"""
    res = GateResult(passed=True)
    if not proj_dir.is_dir():
        res.add("code_project", f"代码工程目录 {proj_dir}", "目录不存在")
        return res

    files = []
    for p in proj_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(proj_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(p)

    if len(files) < spec.min_project_files:
        res.add("min_project_files",
                f"至少 {spec.min_project_files} 个文件",
                f"仅 {len(files)} 个")

    for ref in spec.file_exists:
        if not (proj_dir / ref).exists():
            res.add("file_exists", ref, "文件不存在")

    if spec.require_code_file and not any(p.suffix in _CODE_EXTS for p in files):
        res.add("code_file", "至少一个代码/脚本文件", "未找到 .py/.sh 等")

    if not res.passed:
        res.feedback = _feedback(spec.task_type, res.failures)
    return res


def check_execute(response: dict, *, base_dir: Optional[str] = None,
                  enforce_must_include: bool = False) -> GateResult:
    """execute 串联门禁（D14）：契约 → 格式/完整性 →（action）证据。质量不在此。"""
    contract = check_contract(response)
    if not contract.passed:
        return contract
    if response.get("kind") != "execute":
        return contract  # 非 execute：仅契约门禁

    outcome = (response.get("result") or {}).get("outcome") or {}
    artifact = outcome.get("artifact") or {}
    rel_path = artifact.get("path", "")
    dv_path = str(Path(base_dir) / rel_path) if (base_dir and rel_path and not Path(rel_path).is_absolute()) else rel_path

    task_type = (response.get("meta") or {}).get("task_type") or response.get("task_type", "")
    spec = get_spec(task_type) if task_type else None
    if spec is None:
        # 无注册表条目：只能做契约 + 文件存在性
        res = GateResult(passed=True)
        if dv_path and not Path(dv_path).exists():
            res.add("file_exists", dv_path, "交付物文件不存在")
        return res

    if spec.outcome_kind == "code_project":
        proj = Path(dv_path) if dv_path else Path(".")
        if proj.is_file():
            proj = proj.parent
        if not proj.is_dir():
            tid = (rel_path.strip("/").split("/")[0] if rel_path else "") or \
                  (response.get("meta") or {}).get("task_id") or ""
            if tid and base_dir:
                proj = Path(base_dir) / tid
        return check_code_project(spec, proj)

    if not dv_path or not Path(dv_path).exists():
        res = GateResult(passed=True)
        res.add("file_exists", dv_path or "(空路径)", "交付物文件不存在")
        return res
    content = Path(dv_path).read_text(encoding="utf-8")

    strict_mi = enforce_must_include or task_type in _PGD_STRICT_TYPES
    fmt = check_format(spec, content, dv_path, enforce_must_include=strict_mi)
    if spec.outcome_kind == "action":
        ev = check_action_evidence(spec, content, dv_path)
        fmt.failures.extend(ev.failures)
        fmt.passed = fmt.passed and ev.passed
    if not fmt.passed:
        fmt.feedback = _feedback(spec.task_type, fmt.failures)
    return fmt


def _feedback(task_type: str, failures: list[dict]) -> str:
    lines = [f"任务类型「{task_type}」未通过格式/完整性门禁，请修正后重交：\n"]
    for f in failures:
        lines.append(f"❌ [{f['rule']}] 期望：{f['expected']}，实际：{f['actual']}")
    return "\n".join(lines)
