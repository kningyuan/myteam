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


def watchdog_from_defaults(defaults: Optional[dict] = None) -> WatchdogConfig:
    d = defaults or {}
    return WatchdogConfig(
        soft_idle_sec=_float(d.get("soft_idle_sec"), 120.0),
        hard_idle_sec=_float(d.get("hard_idle_sec"), 300.0),
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
        from common.skill_settings import process_defaults

        defaults = process_defaults()
    proc = process_from_defaults(
        defaults,
        mode=mode,
        token_budget=token_budget,
        max_cycles=max_cycles,
        review=review,
        split=split,
        backend=backend,
    )
    return proc, watchdog_from_defaults(defaults)


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
    return ProcessConfig(
        mode=mode,
        max_gate_retries=_int(d.get("max_gate_retries"), 5),
        split_enabled=split_enabled,
        max_cycles=cycles,
        review_enabled=review,
        token_budget=token_budget,
        budget_degrade_threshold=_float(d.get("budget_degrade_threshold"), 0.8),
        budget_degrade_backend=str(d.get("budget_degrade_backend") or ""),
        budget_degrade_model=str(d.get("budget_degrade_model") or ""),
        skill_extract_enabled=bool(d.get("skill_extract_enabled")),
        default_backend=backend,
        parallel_enabled=bool(d.get("parallel_enabled")),
        max_parallel=_int(d.get("max_parallel"), 4),
    )
