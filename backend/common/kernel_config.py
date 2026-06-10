#!/usr/bin/env python3
"""从 skill_config.process_defaults 构建内核 ProcessConfig / WatchdogConfig。"""
from __future__ import annotations

from typing import Any, Optional

from common.agent_port import WatchdogConfig
from common.process_types import ProcessConfig


def _int(val: Any, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _float(val: Any, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def watchdog_from_defaults(
    defaults: Optional[dict] = None,
    executor: Optional[dict] = None,
) -> WatchdogConfig:
    d = defaults or {}
    e = executor or {}
    soft = _float(d.get("soft_idle_sec"), 120.0)
    hard = _float(d.get("hard_idle_sec"), 300.0)
    poll = _float(e.get("poll_interval"), 0.5)
    max_attempts = _int(e.get("max_retries"), 3)

    def _kind_hard(key: str, fallback: float) -> float:
        return _float(e.get(key), fallback)

    kind_hard = {
        "team_config": _kind_hard("team_config_timeout", 600.0),
        "task_plan": _kind_hard("task_plan_timeout", 600.0),
        "execute": _kind_hard("task_timeout", 3600.0),
        "review": _kind_hard("task_timeout", 3600.0),
        "triage": _kind_hard("ack_timeout", 300.0),
    }
    kind_soft = {k: min(v * 0.4, max(v - 60.0, soft)) for k, v in kind_hard.items()}

    return WatchdogConfig(
        soft_idle_sec=soft,
        hard_idle_sec=hard,
        poll_interval=poll,
        max_attempts=max_attempts,
        kind_soft_idle=kind_soft,
        kind_hard_idle=kind_hard,
    )


def kernel_configs_for_run(
    defaults: dict | None = None,
    *,
    mode: str = "one_shot",
    token_budget: int | None = None,
    max_cycles: int | None = None,
    review: bool = False,
    split: bool = False,
    backend: str = "opencode",
) -> tuple[ProcessConfig, WatchdogConfig]:
    """Hub / CLI / resume 同源：从 process_defaults 构建 Process + Watchdog 配置。"""
    if defaults is None:
        from common.skill_settings import process_defaults, skill_config_all

        defaults = process_defaults()
        executor = (skill_config_all() or {}).get("executor") or {}
    else:
        from common.skill_settings import skill_config_all

        executor = (skill_config_all() or {}).get("executor") or {}
    proc = process_from_defaults(
        defaults,
        mode=mode,
        token_budget=token_budget,
        max_cycles=max_cycles,
        review=review,
        split=split,
        backend=backend,
    )
    return proc, watchdog_from_defaults(defaults, executor)


def process_from_defaults(
    defaults: Optional[dict] = None,
    *,
    mode: str = "one_shot",
    token_budget: Optional[int] = None,
    review: bool = False,
    split: bool = False,
    max_cycles: Optional[int] = None,
    backend: str = "opencode",
) -> ProcessConfig:
    d = defaults or {}
    split_enabled = split or bool(d.get("split_enabled"))
    cycles = max_cycles if max_cycles is not None else _int(d.get("max_cycles"), 3)
    _bg_backend = d.get("budget_degrade_backend")
    _bg_model = d.get("budget_degrade_model")
    return ProcessConfig(
        mode=mode,
        max_gate_retries=_int(d.get("max_gate_retries"), 5),
        split_enabled=split_enabled,
        max_cycles=cycles,
        review_enabled=review,
        token_budget=token_budget,
        budget_degrade_threshold=_float(d.get("budget_degrade_threshold"), 0.8),
        budget_degrade_backend=str(_bg_backend) if _bg_backend and str(_bg_backend).strip() else "",
        budget_degrade_model=str(_bg_model) if _bg_model and str(_bg_model).strip() else "",
        skill_extract_enabled=bool(d.get("skill_extract_enabled")),
        default_backend=backend,
        parallel_enabled=bool(d.get("parallel_enabled")),
        max_parallel=_int(d.get("max_parallel"), 4),
    )
