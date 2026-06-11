#!/usr/bin/env python3
"""delivery_profile — 交付过程套餐（Strategy Registry）。

task_type 在 templates.yaml 绑定 delivery_profile；
Gate 的 file_exists 由 check_rules 与 profile.process_artifacts 合并得出。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from common.paths import delivery_profiles_file


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


@dataclass
class DeliveryProfile:
    name: str
    description: str = ""
    process_artifacts: list[str] = None
    process_checks: dict = None
    scaffold: str = ""
    inject_catalog: bool = False

    def __post_init__(self):
        if self.process_artifacts is None:
            self.process_artifacts = []
        if self.process_checks is None:
            self.process_checks = {}


_NONE = DeliveryProfile(name="none")


@lru_cache(maxsize=1)
def _load_all(path_str: str) -> dict[str, DeliveryProfile]:
    raw = _load_yaml(Path(path_str))
    profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
    out: dict[str, DeliveryProfile] = {}
    for name, cfg in profiles.items():
        if not isinstance(cfg, dict):
            continue
        arts = cfg.get("process_artifacts")
        checks = cfg.get("process_checks")
        out[name] = DeliveryProfile(
            name=str(name),
            description=str(cfg.get("description") or ""),
            process_artifacts=[str(x) for x in arts] if isinstance(arts, list) else [],
            process_checks=dict(checks) if isinstance(checks, dict) else {},
            scaffold=str(cfg.get("scaffold") or ""),
            inject_catalog=bool(cfg.get("inject_catalog", False)),
        )
    return out


def invalidate_delivery_profiles_cache() -> None:
    _load_all.cache_clear()


def load_delivery_profiles(path: Optional[Path] = None) -> dict[str, DeliveryProfile]:
    if path is not None:
        raw = _load_yaml(path)
        profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
        return {
            str(name): DeliveryProfile(
                name=str(name),
                description=str((cfg or {}).get("description") or ""),
            process_artifacts=[
                str(x) for x in ((cfg or {}).get("process_artifacts") or [])
            ] if isinstance((cfg or {}).get("process_artifacts"), list) else [],
            process_checks=dict((cfg or {}).get("process_checks") or {})
            if isinstance((cfg or {}).get("process_checks"), dict) else {},
            scaffold=str((cfg or {}).get("scaffold") or ""),
                inject_catalog=bool((cfg or {}).get("inject_catalog", False)),
            )
            for name, cfg in profiles.items()
            if isinstance(cfg, dict)
        }
    return _load_all(str(delivery_profiles_file()))


def get_delivery_profile(name: Optional[str], path: Optional[Path] = None) -> DeliveryProfile:
    key = (name or "none").strip() or "none"
    if key == "none":
        return _NONE
    return load_delivery_profiles(path).get(key, _NONE)


def merge_file_exists(
    business_files: list[str],
    profile_name: Optional[str],
    path: Optional[Path] = None,
) -> list[str]:
    """业务 file_exists + profile 过程文件，去重保序。"""
    prof = get_delivery_profile(profile_name, path)
    seen: set[str] = set()
    merged: list[str] = []
    for f in list(business_files or []) + list(prof.process_artifacts or []):
        if f and f not in seen:
            seen.add(f)
            merged.append(f)
    return merged


def resolve_profile_name(task_cfg: dict) -> str:
    explicit = (task_cfg.get("delivery_profile") or "").strip()
    return explicit or "none"
