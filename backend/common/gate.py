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

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.contracts import validate_response_dict
from common.delivery_profiles import get_delivery_profile
from common.registry import FormatSpec, is_stub  # FormatSpec used by check_code_project

# 动作证据校验：访问已发布页超时；EVIDENCE_GATE_VERIFY=0 关闭实时访问
EVIDENCE_FETCH_TIMEOUT = 30
EVIDENCE_VERIFY_OFF = os.environ.get("EVIDENCE_GATE_VERIFY", "1") == "0"
_URL_RE = re.compile(r"https?://[^\s)\]\"'<>]+")

# 平台反爬/登录墙特征：命中则事后重读不可信，判为「无法核实」而非「动作未发生」。
try:
    from store.system_config import system_config
    _BLOCKED_MARKERS = system_config.get(
        "system", "blocked_markers",
        default=("signin", "unhuman", "/account/", "captcha", "verify",
                  "登录知乎", "网络环境存在异常"),
    )
except Exception:
    _BLOCKED_MARKERS = ("signin", "unhuman", "/account/", "captcha", "verify",
                        "登录知乎", "网络环境存在异常")


def _extract_field(content: str, field_name: str) -> str:
    """从交付物提取 '字段名：值' 或 H2 章节下首个非空行的值。"""
    inline = re.search(rf"{re.escape(field_name)}\s*[:：]\s*(.+)", content)
    if inline:
        return inline.group(1).strip()
    sec = re.search(rf"^#+\s*{re.escape(field_name)}\s*\n+([^\n#]+)", content, re.MULTILINE)
    if sec:
        return sec.group(1).strip()
    return ""


def verify_published_url(url: str, title: str) -> tuple[bool, bool, str]:
    """真实访问已发布 URL，尽力核对页面含帖子标题。

    返回 (verified, blocked, detail)：
      - verified=True：页面正常加载且含标题 → 动作确认。
      - blocked=True：被平台反爬/登录墙拦截或无 browser → 无法核实（调用方不应据此硬失败）。
      - 二者皆 False：页面正常加载但查无标题 → 动作存疑（硬失败）。
    """
    import subprocess

    browse = _resolve_browse_bin()
    if not browse:
        return False, True, "browse 二进制不可用，无法实时核实（不作硬失败）"
    try:
        subprocess.run([browse, "goto", url], capture_output=True, text=True,
                       timeout=EVIDENCE_FETCH_TIMEOUT)
        final = subprocess.run([browse, "url"], capture_output=True, text=True,
                               timeout=EVIDENCE_FETCH_TIMEOUT)
        res = subprocess.run([browse, "text"], capture_output=True, text=True,
                             timeout=EVIDENCE_FETCH_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, True, f"访问已发布页异常，无法实时核实（不作硬失败）：{e}"
    final_url = (final.stdout or "").strip()
    page_text = res.stdout or ""
    blob = f"{final_url}\n{page_text}"
    if any(m in blob for m in _BLOCKED_MARKERS):
        return False, True, f"事后重读被平台反爬/登录墙拦截，无法核实（不作硬失败）：{final_url}"
    if title and title in page_text:
        return True, False, "已发布页含帖子标题，动作确认"
    return False, False, "已发布页正常加载但未找到帖子标题，动作存疑"


def _resolve_browse_bin() -> Optional[str]:
    """定位 gstack browse 二进制（动作证据实时访问用）。"""
    env = os.environ.get("GSTACK_BROWSE")
    candidates = [env] if env else []
    candidates += [
        str(Path.home() / "skill" / "gstack" / "browse" / "dist" / "browse"),
        str(Path.home() / ".claude" / "skills" / "gstack" / "browse" / "dist" / "browse"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


# P0 边界澄清：feature flag 控制 strict_must_include 从 FormatSpec 读取
try:
    from store.system_config import system_config
    USE_STRICT_MUST_INCLUDE = bool(system_config.get("system", "use_strict_must_include_config", default=False))
except Exception:
    USE_STRICT_MUST_INCLUDE = False


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


try:
    from store.system_config import system_config
    _CODE_EXTS = set(system_config.get("system", "code_extensions",
        default=[".py", ".sh", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h", ".c", ".rb", ".php", ".swift"]))
except Exception:
    _CODE_EXTS = {".py", ".sh", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h", ".c", ".rb", ".php", ".swift"}
_PACKAGE_EXTS = {".yaml", ".yml", ".json", ".toml", ".env", ".cfg", ".ini"}


def check_code_project(spec: FormatSpec, proj_dir: Path) -> GateResult:
    """包态交付物：校验目录、文件清单、扩展名约束。"""
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

    exts = set(spec.required_extensions or [])
    if exts:
        if not any(p.suffix in exts for p in files):
            res.add("required_extensions", f"须含 {', '.join(sorted(exts))}", "未找到匹配扩展名")
    elif spec.require_code_file and not any(p.suffix in _CODE_EXTS for p in files):
        res.add("code_file", "至少一个代码/脚本文件", "未找到 .py/.sh 等")

    if not res.passed:
        res.feedback = _feedback(spec.task_type, res.failures)
    return res


def _effective_process_content(content: str) -> str:
    """去掉 HTML 注释后再判过程产物是否已填写。"""
    return re.sub(r"<!--.*?-->", "", content or "", flags=re.DOTALL).strip()


def check_process_artifacts(spec: FormatSpec, base_dir: Path) -> GateResult:
    """过程产物质量门禁：align/plan 非模板、verify.log 有自检记录。"""
    prof = get_delivery_profile(spec.delivery_profile)
    if not prof.process_checks:
        return GateResult(passed=True)

    res = GateResult(passed=True)
    for fname, rules in prof.process_checks.items():
        path = base_dir / fname
        if not path.is_file():
            res.add("process_artifact", fname, "文件不存在")
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        eff = _effective_process_content(raw) if fname.endswith(".md") else raw.strip()
        min_len = int(rules.get("min_length") or 0)
        if min_len and len(eff) < min_len:
            res.add(
                "process_artifact",
                f"{fname} 有效内容 ≥{min_len} 字符",
                f"仅 {len(eff)} 字符",
            )
        if rules.get("not_stub"):
            if fname.endswith(".md") and "<!--" in raw:
                res.add(
                    "process_artifact",
                    f"{fname} 须填写实质内容",
                    "仍含模板 HTML 注释",
                )
            elif is_stub(eff, max(8, min_len // 2)):
                res.add("process_artifact", f"{fname} 须填写实质内容", "内容疑似模板/占位")

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
    template_id = str((response.get("meta") or {}).get("template_id") or "").strip() or None
    from common.registry import resolve_format_spec
    spec = resolve_format_spec(task_type, template_id) if task_type else None
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
        fmt = check_code_project(spec, proj)
        root = Path(base_dir) if base_dir else proj.parent
        if spec.delivery_profile and spec.delivery_profile != "none":
            proc = check_process_artifacts(spec, root)
            fmt.failures.extend(proc.failures)
            fmt.passed = fmt.passed and proc.passed
            if not fmt.passed:
                fmt.feedback = _feedback(spec.task_type, fmt.failures)
        return fmt

    if not dv_path or not Path(dv_path).exists():
        res = GateResult(passed=True)
        res.add("file_exists", dv_path or "(空路径)", "交付物文件不存在")
        return res
    content = Path(dv_path).read_text(encoding="utf-8")

    strict_mi = enforce_must_include
    if not strict_mi:
        if USE_STRICT_MUST_INCLUDE:
            strict_mi = spec.strict_must_include
        else:
            strict_mi = task_type in {"decision-record", "acceptance-report"}
    fmt = check_format(spec, content, dv_path, enforce_must_include=strict_mi)
    if spec.outcome_kind == "action":
        ev = check_action_evidence(spec, content, dv_path)
        fmt.failures.extend(ev.failures)
        fmt.passed = fmt.passed and ev.passed
    root = Path(base_dir) if base_dir else Path(dv_path).parent
    if spec.delivery_profile and spec.delivery_profile != "none":
        proc = check_process_artifacts(spec, root)
        fmt.failures.extend(proc.failures)
        fmt.passed = fmt.passed and proc.passed
    if not fmt.passed:
        fmt.feedback = _feedback(spec.task_type, fmt.failures)
    return fmt


def check_plan(response: dict) -> GateResult:
    """plan 门禁（路径 A）：从契约到结构完整性（轻量）。不判好不好，只判有没有。"""
    contract = check_contract(response)
    if not contract.passed:
        return contract
    if response.get("kind") != "plan":
        return contract

    result = (response.get("result") or {})
    res = GateResult(passed=True)

    approach = (result.get("approach") or "").strip()
    if len(approach) < 10:
        res.add("plan_approach", "approach 至少 10 个字符描述总体思路", f"仅 {len(approach)} 字符")

    steps = result.get("steps") or []
    if not isinstance(steps, list) or len(steps) == 0:
        res.add("plan_steps", "至少 1 个执行步骤", "steps 为空")
    else:
        non_trivial = [s for s in steps if len(s.strip()) >= 2]
        if len(non_trivial) < 1:
            res.add("plan_steps", "步骤须有实质性描述（≥2 字符）", "所有步骤过于简短")

    risks = result.get("risks") or []
    if isinstance(risks, list) and len(risks) > 0:
        non_trivial_risks = [r for r in risks if len(r.strip()) >= 4]
        if not non_trivial_risks:
            res.add("plan_risks", "风险须有实质性描述（≥2 字符）", "所有风险过于简短")

    confidence = result.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            res.add("plan_confidence", "confidence 须在 0..1 之间", str(confidence))

    if not res.passed:
        res.feedback = _feedback("plan", res.failures)
    return res


def _feedback(task_type: str, failures: list[dict]) -> str:
    lines = [f"任务类型「{task_type}」未通过格式/完整性门禁，请修正后重交：\n"]
    for f in failures:
        lines.append(f"❌ [{f['rule']}] 期望：{f['expected']}，实际：{f['actual']}")
    return "\n".join(lines)
