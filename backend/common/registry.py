#!/usr/bin/env python3
"""格式注册表（D10-D / D14 / D15）—— task_type 约束的**单一出处**。

把分散的 task_type 约束（executor 硬编码提示、templates.yaml、validator 默认值、
quality_gate）收敛到这一处：由 Process 下发约束、Gate 据此校验，源出同一。

每个 task_type 暴露 FormatSpec：
  - outcome_kind：artifact | action（D15；含 evidence_url 配置者=action）
  - required_sections / required_heading_level / sections（格式/完整性，D14）
  - file_exists：必须存在的引用文件
  - evidence：action 证据规则（host_contains/url_must_match/screenshot_field/verify_title）
  - stub_floor：防 stub 下限（D14：min_length 降级为「非空非占位」，不当质量指标）
  - must_include：默认**不**强制（D14 移出确定性门禁），仅显式开启时校验
  - acceptance_criteria：自评 + 同行评审**共用**（取代 cross_review 硬编码 checklist）

数据仍存 templates.yaml（配置，非 skill）；本模块是其计算化的单一读取入口。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from common.paths import templates_file

# 防 stub 下限：低于此（去空白后字符数）或命中占位符 = stub（D14）。
DEFAULT_STUB_FLOOR = 20
_PLACEHOLDER_MARKERS = ("待补充", "待填写", "todo", "tbd", "tbd", "xxx", "lorem ipsum", "占位")


@dataclass
class FormatSpec:
    task_type: str
    outcome_kind: str = "artifact"
    required_sections: list[str] = field(default_factory=list)
    required_heading_level: int = 2
    sections: list[dict] = field(default_factory=list)
    file_exists: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    stub_floor: int = DEFAULT_STUB_FLOOR
    must_include: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _derive_outcome_kind(task_cfg: dict, check_rules: dict) -> str:
    """显式 outcome_kind 优先；否则有 evidence_url 配置者推断为 action（D15）。"""
    explicit = task_cfg.get("outcome_kind")
    if explicit in ("artifact", "action"):
        return explicit
    return "action" if check_rules.get("evidence_url") else "artifact"


def _derive_acceptance_criteria(task_cfg: dict, required_sections: list[str]) -> list[str]:
    """显式 acceptance_criteria 优先；否则由必需章节派生一份最小验收标准。"""
    explicit = task_cfg.get("acceptance_criteria")
    if isinstance(explicit, list) and explicit:
        return [str(x) for x in explicit]
    return [f"完整覆盖「{s}」章节且内容具体可执行" for s in required_sections]


def _build_spec(task_type: str, task_cfg: dict) -> FormatSpec:
    dt = task_cfg.get("deliverable_template", {}) or {}
    check_rules = task_cfg.get("check_rules", {}) or {}
    required_sections = list(check_rules.get("required_sections", []) or [])
    return FormatSpec(
        task_type=task_type,
        outcome_kind=_derive_outcome_kind(task_cfg, check_rules),
        required_sections=required_sections,
        required_heading_level=int(dt.get("required_heading_level", 2)),
        sections=list(dt.get("sections", []) or []),
        file_exists=list(check_rules.get("file_exists", []) or []),
        evidence=dict(check_rules.get("evidence_url", {}) or {}),
        stub_floor=int(check_rules.get("stub_floor", DEFAULT_STUB_FLOOR)),
        must_include=list(check_rules.get("must_include", []) or []),
        acceptance_criteria=_derive_acceptance_criteria(task_cfg, required_sections),
    )


@lru_cache(maxsize=1)
def _load_all(path_str: str) -> dict[str, FormatSpec]:
    raw = _load_yaml(Path(path_str))
    return {tt: _build_spec(tt, cfg) for tt, cfg in raw.items() if isinstance(cfg, dict)}


def load_registry(path: Optional[Path] = None) -> dict[str, FormatSpec]:
    return _load_all(str(path or templates_file()))


def get_spec(task_type: str, path: Optional[Path] = None) -> Optional[FormatSpec]:
    return load_registry(path).get(task_type)


def is_stub(content: str, floor: int = DEFAULT_STUB_FLOOR) -> bool:
    """防 stub 判定：去空白后过短，或整体只是占位符。"""
    stripped = (content or "").strip()
    if len(stripped) < max(1, floor):
        return True
    low = stripped.lower()
    return any(m in low for m in _PLACEHOLDER_MARKERS) and len(stripped) < floor * 3
