#!/usr/bin/env python3
"""PromptComposer — 统一拼装 execute/review 等 prompt 注入层。

机制在此；文案在 prompt_injections.yaml + delivery_profiles.yaml。
"""
from __future__ import annotations

from typing import Any, Optional

from common.delivery_profiles import get_delivery_profile
from common.paths import MYTEAM_ROOT
from common.prompt_injections import append_prompt_injections, build_injection_variables


def compose_delivery_variables(delivery_profile: str, **extra: Any) -> dict[str, Any]:
    """按 profile 解析 scaffold 等路径变量。"""
    prof = get_delivery_profile(delivery_profile)
    root = MYTEAM_ROOT
    scaffold = prof.scaffold
    if scaffold and not scaffold.startswith("/"):
        scaffold = str(root / scaffold)
    return build_injection_variables(
        scaffold_script=scaffold or str(
            root / "business" / "playbooks" / "scripts" / "scaffold_light.sh"
        ),
        delivery_profile=delivery_profile,
        **extra,
    )


def compose_execute_layers(
    lines: list[str],
    task_type: str,
    delivery_profile: str,
    *,
    variables: Optional[dict[str, Any]] = None,
) -> None:
    """叠加 delivery_profile 与 task_type 配置的 prompt 块。"""
    profile = (delivery_profile or "none").strip() or "none"
    if profile == "none":
        return
    prof = get_delivery_profile(profile)
    if not prof.process_artifacts and profile != "none":
        return
    vars_ = compose_delivery_variables(profile, **(variables or {}))
    append_prompt_injections(
        lines,
        "execute",
        task_type,
        delivery_profile=profile,
        variables=vars_,
    )
