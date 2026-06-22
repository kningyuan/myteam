#!/usr/bin/env python3
"""AnySearch 编排桩 — Phase 1 对接 CLI。"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("memstack.orchestration.anysearch")

_DEFAULT_SKILL = Path.home() / "skill" / "anysearch-skill"


def anysearch_cli() -> Optional[Path]:
    from memstack.config import anysearch_home

    conf = anysearch_home()
    if conf:
        for name in ("anysearch", "anysearch.js"):
            p = Path(conf) / "bin" / name
            if p.is_file():
                return p
        p = Path(conf) / "anysearch"
        if p.is_file():
            return p
    for candidate in (
        _DEFAULT_SKILL / "bin" / "anysearch",
        Path.home() / ".local" / "bin" / "anysearch",
    ):
        if candidate.is_file():
            return candidate
    found = shutil.which("anysearch")
    return Path(found) if found else None


def search_and_extract(query: str, *, url: str = "") -> dict:
    """调用 AnySearch CLI；不可用时返回空结果不 raise。"""
    cli = anysearch_cli()
    if cli is None:
        logger.debug("AnySearch CLI not found")
        return {"ok": False, "query": query, "results": []}
    try:
        if url:
            cmd = [str(cli), "extract", url]
        else:
            cmd = [str(cli), "search", query]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "query": query,
            "stdout": proc.stdout[:8000],
            "stderr": proc.stderr[:2000],
        }
    except Exception as e:
        logger.warning("AnySearch failed: %s", e)
        return {"ok": False, "query": query, "error": str(e)}
