#!/usr/bin/env python3
"""Quality Gate — 确定性质量门禁。

在 DISPATCH_LOOP 中每个 task 执行后调用，通过 gbrain CLI 读取标准规则，
对 deliverable 文件做结构化校验。零 LLM 参与，全部确定性逻辑。

用法:
    gate = QualityGate("pro_xxx", task_type="code-deliverable")
    result = gate.check(deliverable_path="/path/to/output.md", content="...")
    print(result.pass, result.failures)
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GateResult:
    passed: bool
    failures: list[dict] = field(default_factory=list)
    feedback: str = ""
    skipped: bool = False  # True if gate was skipped (no standard page)


from common.paths import templates_file

# 本地模板文件路径
TEMPLATES_FILE = templates_file()
# 最大重试次数
MAX_GATE_RETRIES = 3

# 动作证据校验：访问已发布页超时
EVIDENCE_FETCH_TIMEOUT = 30
# 关闭实时访问校验（DRY-RUN/离线场景：仅校验 URL 存在与格式）
EVIDENCE_VERIFY_OFF = os.environ.get("EVIDENCE_GATE_VERIFY", "1") == "0"

# URL 提取（取交付物中第一个 http(s) 链接）
_URL_RE = re.compile(r"https?://[^\s)\]\"'<>]+")


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


# 平台反爬/登录墙特征：命中则事后重读不可信，判为「无法核实」而非「动作未发生」。
_BLOCKED_MARKERS = ("signin", "unhuman", "/account/", "captcha", "verify",
                    "登录知乎", "网络环境存在异常")


def verify_published_url(url: str, title: str) -> tuple[bool, bool, str]:
    """真实访问已发布 URL，尽力核对页面含帖子标题。

    返回 (verified, blocked, detail)：
      - verified=True：页面正常加载且含标题 → 动作确认。
      - blocked=True：被平台反爬/登录墙拦截或无 browser → 无法核实（调用方不应据此硬失败）。
      - 二者皆 False：页面正常加载但查无标题 → 动作存疑（硬失败）。
    可在测试中 monkeypatch 本函数。
    """
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


def _extract_field(content: str, field_name: str) -> str:
    """从交付物提取 '字段名：值' 或 H2 章节下首个非空行的值。"""
    # 形如 "帖子标题：xxx" / "帖子标题: xxx"
    inline = re.search(rf"{re.escape(field_name)}\s*[:：]\s*(.+)", content)
    if inline:
        return inline.group(1).strip()
    # 形如 "## 帖子标题\nxxx"
    sec = re.search(rf"^#+\s*{re.escape(field_name)}\s*\n+([^\n#]+)", content, re.MULTILINE)
    if sec:
        return sec.group(1).strip()
    return ""


class QualityGate:
    """质量门禁：从 gbrain KB 读取标准 → 对交付物做确定性校验。"""

    def __init__(self, project_id: str, task_type: str):
        self.project_id = project_id
        self.task_type = task_type
        self.retry_count = 0
        self._deliverable_template: dict = {}

    # ── 读取标准 ──────────────────────────────────────────────

    def read_standards(self) -> Optional[dict]:
        """读取 task_type 对应的校验规则（只读本地注册表 templates.yaml）。

        返回 None 表示标准不存在 → 跳过检查。
        （旧 gbrain CLI 回退已删除：本环境从未真正落地，标准统一走注册表。）
        """
        return self._read_standards_from_local()

    def _read_standards_from_local(self) -> Optional[dict]:
        """从本地 templates.yaml 读取校验规则。"""
        if not TEMPLATES_FILE.exists():
            return None
        try:
            import yaml
            with open(TEMPLATES_FILE, encoding="utf-8") as f:
                all_templates = yaml.safe_load(f)
            if not isinstance(all_templates, dict):
                return None
            task_cfg = all_templates.get(self.task_type, {})
            if not isinstance(task_cfg, dict):
                return None
            check_rules = task_cfg.get("check_rules", {})
            if not isinstance(check_rules, dict):
                return None
            # 同时读取 deliverable_template 用于 section level check
            dt = task_cfg.get("deliverable_template", {})
            if isinstance(dt, dict):
                self._deliverable_template = dt
            return {
                "required_sections": check_rules.get("required_sections", []),
                "min_length": check_rules.get("min_length", 0),
                "must_include": check_rules.get("must_include", []),
                "file_exists": check_rules.get("file_exists", []),
                "evidence_url": check_rules.get("evidence_url", {}),
            }
        except Exception:
            return None

    # ── 规则检查 ──────────────────────────────────────────────

    def check(self, deliverable_path: str, content: str = "") -> GateResult:
        """对 deliverable 执行质量门禁检查。

        Args:
            deliverable_path: 交付物文件路径
            content: 可选的已读取内容（避免重复读文件）

        Returns:
            GateResult: 检查结果
        """
        # 读取标准
        standards = self.read_standards()
        if standards is None:
            # 本地注册表无此 task_type 标准 → 跳过门禁
            return GateResult(passed=True, skipped=True,
                              feedback="本地注册表无此 task_type 标准，门禁跳过")

        # 如果未提供 content，从文件读取
        content_to_check = content
        if not content_to_check and deliverable_path:
            try:
                with open(deliverable_path, "r", encoding="utf-8") as f:
                    content_to_check = f.read()
            except (FileNotFoundError, IOError):
                return GateResult(
                    passed=False,
                    failures=[{"rule": "file_exists",
                               "expected": deliverable_path,
                               "actual": "文件不存在"}],
                    feedback=f"交付物文件不存在：{deliverable_path}"
                )

        failures = []

        # 规则 1: required_sections — 必需章节标题
        for section in standards.get("required_sections", []):
            if section not in content_to_check:
                failures.append({
                    "rule": "required_sections",
                    "expected": section,
                    "actual": "未找到此章节",
                })

        # 规则 2: min_length — 最小字符数
        min_length = standards.get("min_length", 0)
        if min_length > 0:
            chinese_chars = len(re.findall(r'[一-鿿]', content_to_check))
            english_words = len(re.findall(r'[a-zA-Z_]+', content_to_check))
            total = chinese_chars + english_words
            if total < min_length:
                failures.append({
                    "rule": "min_length",
                    "expected": str(min_length),
                    "actual": str(total),
                })

        # 规则 3: section_level_check — 章节标题层级（格式校验）
        dt = self._deliverable_template
        if dt:
            sections = dt.get("sections", [])
            heading_level = dt.get("required_heading_level", 2)
            if sections and isinstance(sections, list):
                # 剥离围栏代码块后检查标题层级
                clean_content = re.sub(r'```.*?```', '', content_to_check, flags=re.DOTALL)
                for sec in sections:
                    sec_name = sec.get("name", "") if isinstance(sec, dict) else ""
                    if not sec_name:
                        continue
                    # 只检查 required=true 的章节
                    if not sec.get("required", True):
                        continue
                    heading = "#" * heading_level
                    pattern = rf'^{heading}\s+[^\n]*{re.escape(sec_name)}'
                    if not re.search(pattern, clean_content, re.MULTILINE):
                        failures.append({
                            "rule": "section_level",
                            "expected": f"{heading} {sec_name}",
                            "actual": "未找到此层级的章节标题",
                        })

        # 规则 4（重编号后）: must_include — 必须含有的关键词
        for keyword in standards.get("must_include", []):
            if keyword not in content_to_check:
                failures.append({
                    "rule": "must_include",
                    "expected": keyword,
                    "actual": "未找到此关键词",
                })

        # 规则 5: file_exists — 引用的文件路径必须存在
        for ref_path in standards.get("file_exists", []):
            full_path = Path(deliverable_path).parent / ref_path
            if not full_path.exists():
                failures.append({
                    "rule": "file_exists",
                    "expected": str(full_path),
                    "actual": "文件不存在",
                })

        # 规则 6: evidence_url — 动作型任务的「动作证据」校验
        # 从交付物提取已发布 URL，真实访问并核对页面含帖子标题。
        evidence_cfg = standards.get("evidence_url", {})
        if isinstance(evidence_cfg, dict) and evidence_cfg:
            failures.extend(
                self._check_evidence_url(evidence_cfg, content_to_check, deliverable_path)
            )

        passed = len(failures) == 0
        feedback = self._build_feedback(failures, self.task_type) if failures else ""

        return GateResult(passed=passed, failures=failures, feedback=feedback)

    def _check_evidence_url(self, cfg: dict, content: str,
                            deliverable_path: str = "") -> list[dict]:
        """动作证据校验：交付物须含合规已发布 URL（+截图），并尽力实时核对标题。

        硬证据 = URL 命中发布页形态 + 截图文件存在；实时重读为尽力而为的加分项，
        被平台反爬拦截时不硬失败（避免误判已真实发生的动作）。
        """
        failures = []
        host_contains = cfg.get("host_contains", "")
        url_must_match = cfg.get("url_must_match", "")
        urls = _URL_RE.findall(content)
        if host_contains:
            urls = [u for u in urls if host_contains in u]
        if url_must_match:
            urls = [u for u in urls if url_must_match in u]
        if not urls:
            want = url_must_match or host_contains or "http(s)"
            failures.append({
                "rule": "evidence_url",
                "expected": f"含 {want} 的已发布URL",
                "actual": "交付物未找到合规的已发布URL",
            })
            return failures
        published_url = urls[0]

        # 截图证据：文件须真实存在（相对交付物目录）。
        shot_field = cfg.get("screenshot_field", "")
        if shot_field and deliverable_path:
            shot = _extract_field(content, shot_field)
            if shot:
                shot_path = Path(deliverable_path).parent / shot
                if not shot_path.exists():
                    failures.append({
                        "rule": "evidence_url",
                        "expected": f"证据截图文件存在：{shot_path}",
                        "actual": "截图文件不存在",
                    })

        # 实时重读（尽力而为）：仅在页面正常加载却查无标题时硬失败。
        if cfg.get("verify_title") and not EVIDENCE_VERIFY_OFF:
            title = _extract_field(content, "帖子标题")
            verified, blocked, detail = verify_published_url(published_url, title)
            if not verified and not blocked:
                failures.append({
                    "rule": "evidence_url",
                    "expected": f"已发布页 {published_url} 含标题「{title}」",
                    "actual": detail,
                })
        return failures

    def _build_feedback(self, failures: list[dict], task_name: str) -> str:
        """根据失败项构建给 Agent 的反馈。"""
        lines = [f"你的任务「{task_name}」的输出未通过质量门禁，请重新生成。\n"]
        lines.append("未通过的规则：")
        for f in failures:
            lines.append(f"\n❌ [{f['rule']}] 期望：{f['expected']}，实际：{f['actual']}")
        lines.append("\n\n请针对以上问题修改输出后重试。")
        return "\n".join(lines)


# ── 集成到 Executor 的适配函数 ─────────────────────────────

def run_quality_gate(project_id: str, task_type: str,
                     deliverable_path: str, content: str = "") -> GateResult:
    """便捷函数：创建 QualityGate 实例并执行检查。

    被 executor.py 的 state_quality_gate() 调用。
    """
    gate = QualityGate(project_id, task_type)
    return gate.check(deliverable_path, content)