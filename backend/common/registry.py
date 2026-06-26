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
from common.delivery_profiles import merge_file_exists, resolve_profile_name
from store.system_config import system_config

# 防 stub 下限：低于此（去空白后字符数）或命中占位符 = stub（D14）。
DEFAULT_STUB_FLOOR = 20
_DEFAULT_PLACEHOLDER_MARKERS = ("待补充", "待填写", "todo", "tbd", "tbd", "xxx", "lorem ipsum", "占位")
_PLACEHOLDER_MARKERS = tuple(
    system_config.get("system", "placeholder_markers", default=_DEFAULT_PLACEHOLDER_MARKERS)
)

@dataclass
class FormatSpec:
    task_type: str
    display_name: str = ""
    outcome_kind: str = "artifact"
    required_sections: list[str] = field(default_factory=list)
    required_heading_level: int = 2
    sections: list[dict] = field(default_factory=list)
    file_exists: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    stub_floor: int = DEFAULT_STUB_FLOOR
    must_include: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    strict_must_include: bool = False        # P0 边界澄清：PGD 严格 must_include 校验（0.3）
    min_project_files: int = 1
    require_code_file: bool = False
    required_extensions: list[str] = field(default_factory=list)
    structure: list[str] = field(default_factory=list)
    delivery_profile: str = "none"
    template_id: str = ""
    template_display_name: str = ""


def _spec_from_delivery_template(task_type: str, base: "FormatSpec", tpl) -> FormatSpec:
    """用交付模板覆盖 Gate / scaffold / Review 字段；profile 来自 task_type。"""
    from common.delivery_templates import DeliveryTemplate

    assert isinstance(tpl, DeliveryTemplate)
    dt = tpl.deliverable_template or {}
    check_rules = dict(tpl.check_rules or {})
    by_tt = check_rules.pop("check_rules_by_task_type", None) or check_rules.pop(
        "by_task_type", None,
    )
    if isinstance(by_tt, dict) and task_type in by_tt and isinstance(by_tt[task_type], dict):
        overrides = dict(by_tt[task_type])
        check_rules = {**check_rules, **overrides}
    required_sections = list(check_rules.get("required_sections") or [])
    if not required_sections and dt.get("sections"):
        required_sections = [
            str(s.get("name", "")).strip()
            for s in dt.get("sections", [])
            if isinstance(s, dict) and s.get("required", True) and s.get("name")
        ]
    min_len = int(check_rules.get("min_length") or 0)
    stub_floor = int(check_rules.get("stub_floor") or DEFAULT_STUB_FLOOR)
    if min_len > stub_floor:
        stub_floor = min_len
    business_files = list(check_rules.get("file_exists") or [])
    profile_name = base.delivery_profile
    criteria = list(tpl.acceptance_criteria) if tpl.acceptance_criteria else _derive_acceptance_criteria(
        {"acceptance_criteria": []}, required_sections,
    )
    evidence_cfg = dict(check_rules.get("evidence_url") or base.evidence or {})
    return FormatSpec(
        task_type=task_type,
        display_name=tpl.display_name or base.display_name,
        outcome_kind=base.outcome_kind,
        required_sections=required_sections,
        required_heading_level=int(dt.get("required_heading_level", base.required_heading_level or 2)),
        sections=list(dt.get("sections") or []),
        file_exists=business_files,
        evidence=evidence_cfg,
        stub_floor=stub_floor,
        must_include=list(check_rules.get("must_include") or []),
        acceptance_criteria=criteria,
        strict_must_include=bool(check_rules.get("strict_must_include", base.strict_must_include)),
        min_project_files=int(check_rules.get("min_project_files", base.min_project_files) or base.min_project_files),
        require_code_file=bool(check_rules.get("require_code_file", base.require_code_file)),
        required_extensions=list(check_rules.get("required_extensions") or base.required_extensions or []),
        structure=list(dt.get("structure") or []),
        delivery_profile=profile_name,
        template_id=tpl.id,
        template_display_name=tpl.display_name or tpl.id,
    )


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
    if explicit in ("artifact", "action", "code_project"):
        return explicit
    return "action" if check_rules.get("evidence_url") else "artifact"


def _derive_acceptance_criteria(task_cfg: dict, required_sections: list[str]) -> list[str]:
    """显式 acceptance_criteria 优先；否则由必需章节派生一份最小验收标准。"""
    explicit = task_cfg.get("acceptance_criteria")
    if isinstance(explicit, list) and explicit:
        return [str(x) for x in explicit]
    return [f"完整覆盖「{s}」章节且内容具体可执行" for s in required_sections]


def resolve_display_name(task_type: str, task_cfg: Optional[dict] = None) -> str:
    """task_type 的 UI 展示名：yaml display_name > 注册键本身。"""
    cfg = task_cfg if isinstance(task_cfg, dict) else {}
    explicit = (cfg.get("display_name") or cfg.get("label") or "").strip()
    if explicit:
        return explicit
    return (task_type or "").strip()


def _build_spec(task_type: str, task_cfg: dict) -> FormatSpec:
    dt = task_cfg.get("deliverable_template", {}) or {}
    check_rules = task_cfg.get("check_rules", {}) or {}
    required_sections = list(check_rules.get("required_sections", []) or [])
    profile_name = resolve_profile_name(task_cfg)
    business_files = list(check_rules.get("file_exists", []) or [])
    return FormatSpec(
        task_type=task_type,
        display_name=resolve_display_name(task_type, task_cfg),
        outcome_kind=_derive_outcome_kind(task_cfg, check_rules),
        required_sections=required_sections,
        required_heading_level=int(dt.get("required_heading_level", 2)),
        sections=list(dt.get("sections", []) or []),
        file_exists=merge_file_exists(business_files, profile_name),
        evidence=dict(check_rules.get("evidence_url", {}) or {}),
        stub_floor=int(check_rules.get("stub_floor", DEFAULT_STUB_FLOOR)),
        must_include=list(check_rules.get("must_include", []) or []),
        acceptance_criteria=_derive_acceptance_criteria(task_cfg, required_sections),
        strict_must_include=bool(check_rules.get("strict_must_include", False)),
        min_project_files=int(check_rules.get("min_project_files", 1) or 1),
        require_code_file=bool(check_rules.get("require_code_file", False)),
        required_extensions=[str(x) for x in (check_rules.get("required_extensions") or []) if str(x).strip()],
        structure=list(dt.get("structure", []) or []),
        delivery_profile=profile_name,
    )


@lru_cache(maxsize=1)
def _load_all(path_str: str) -> dict[str, FormatSpec]:
    raw = _load_yaml(Path(path_str))
    return {tt: _build_spec(tt, cfg) for tt, cfg in raw.items() if isinstance(cfg, dict)}


def invalidate_registry_cache() -> None:
    """templates.yaml 写入后调用，使 load_registry / get_spec 读到最新配置。"""
    _load_all.cache_clear()
    from common.delivery_profiles import invalidate_delivery_profiles_cache
    from common.delivery_templates import invalidate_delivery_templates_cache
    invalidate_delivery_profiles_cache()
    invalidate_delivery_templates_cache()


def resolve_format_spec(
    task_type: str,
    template_id: Optional[str] = None,
    *,
    path: Optional[Path] = None,
) -> Optional[FormatSpec]:
    """task_type 默认 + 可选 template_id 覆盖 Gate/scaffold/Review 结构。"""
    base = get_spec(task_type, path)
    if not base:
        return None
    tid = (template_id or "").strip()
    if not tid:
        return base
    from common.delivery_templates import load_delivery_template
    tpl = load_delivery_template(tid)
    return _spec_from_delivery_template(task_type, base, tpl)


def spec_for_task(task: dict, *, path: Optional[Path] = None) -> Optional[FormatSpec]:
    tt = str(task.get("task_type") or "").strip()
    if not tt:
        return None
    tpl = str(task.get("template_id") or "").strip() or None
    return resolve_format_spec(tt, tpl, path=path)


def load_registry(path: Optional[Path] = None) -> dict[str, FormatSpec]:
    if path is not None:
        raw = _load_yaml(path)
        return {tt: _build_spec(tt, cfg) for tt, cfg in raw.items() if isinstance(cfg, dict)}
    return _load_all(str(templates_file()))


def get_spec(task_type: str, path: Optional[Path] = None) -> Optional[FormatSpec]:
    return load_registry(path).get(task_type)


def task_type_label(task_type: str, *, path: Optional[Path] = None) -> str:
    """已注册类型的展示名；未注册时返回 task_type id。"""
    tt = (task_type or "").strip()
    if not tt:
        return ""
    spec = get_spec(tt, path)
    if spec and (spec.display_name or "").strip():
        return spec.display_name.strip()
    return tt


def is_stub(content: str, floor: int = DEFAULT_STUB_FLOOR) -> bool:
    """防 stub 判定：去空白后过短，或整体只是占位符。"""
    stripped = (content or "").strip()
    if len(stripped) < max(1, floor):
        return True
    low = stripped.lower()
    return any(m in low for m in _PLACEHOLDER_MARKERS) and len(stripped) < floor * 3
