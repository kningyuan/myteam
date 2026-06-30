#!/usr/bin/env python3
"""Frontend lib/api REST paths must match Hub FastAPI routes (parity contract).

Scans ``frontend/src/lib/api/*.ts`` for ``/api/`` path templates consumed via
``hubFetch``, ``fetch``, or ``EventSource``, then introspects the Hub app route
table. Each FE (method, path) pair must match a registered Hub route unless
listed in ``ALLOWED_FE_HUB_MISMATCHES`` with an inline comment explaining why.

Architecture v4 · task ``integration-test``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

MYTEAM_ROOT = Path(__file__).resolve().parents[3]
FE_API_DIR = MYTEAM_ROOT / "frontend" / "src" / "lib" / "api"

sys_path_backend = str(MYTEAM_ROOT / "backend")
import sys

if sys_path_backend not in sys.path:
    sys.path.insert(0, sys_path_backend)

pytest.importorskip("fastapi")

from hub.api.server import app  # noqa: E402

PRIORITY_MODULES = frozenset({"projects.ts", "chat.ts", "groups.ts", "config.ts"})

# (METHOD, normalized_path) pairs the FE calls but Hub registers elsewhere or
# are verified by dedicated tests — keep empty unless a documented exception exists.
ALLOWED_FE_HUB_MISMATCHES: frozenset[tuple[str, str]] = frozenset()

_CALL_RE = re.compile(
    r"(?:hubFetch|fetch|EventSource)\s*(?:<[^>]*>)?\s*\(\s*"
    r"(?:`([^`]+)`|\"([^\"]+)\")",
    re.MULTILINE,
)
_URL_ASSIGN_FETCH_RE = re.compile(
    r"const\s+url\s*=\s*(?:`([^`]+)`|\"([^\"]+)\").*?\bfetch\s*\(\s*url\b",
    re.DOTALL,
)
_METHOD_RE = re.compile(r"method:\s*[\"'](\w+)[\"']", re.IGNORECASE)


@dataclass(frozen=True)
class FeRoute:
    method: str
    path: str
    source: str

    def key(self) -> tuple[str, str]:
        return (self.method, self.path)


def _normalize_path(raw: str) -> str:
    path = raw.split("?")[0].strip()
    path = re.sub(r"\$\{encodeURIComponent\([^)]+\)\}", "{param}", path)
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") if path != "/api" else path


def _call_kind(text: str, call_start: int) -> str:
    prefix = text[max(0, call_start - 12) : call_start]
    if "EventSource" in prefix:
        return "eventsource"
    if "hubFetch" in prefix:
        return "hubfetch"
    if "fetch" in prefix:
        return "fetch"
    return "unknown"


def _options_blob(text: str, path_end: int) -> str:
    """Text after the path literal until the hubFetch/fetch call closes."""
    rest = text[path_end:]
    depth = 0
    started = False
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
            started = True
        elif ch == ")":
            depth -= 1
            if started and depth <= 0:
                return rest[: i + 1]
    return rest[:400]


def _infer_method(text: str, call_start: int, path_end: int) -> str:
    kind = _call_kind(text, call_start)
    if kind == "eventsource":
        return "GET"
    options = _options_blob(text, path_end)
    m = _METHOD_RE.search(options)
    if m:
        return m.group(1).upper()
    return "GET"


def _extract_fe_routes(ts_path: Path) -> list[FeRoute]:
    text = ts_path.read_text(encoding="utf-8")
    routes: list[FeRoute] = []
    seen: set[tuple[str, str]] = set()

    for match in _CALL_RE.finditer(text):
        raw = match.group(1) or match.group(2) or ""
        if "/api/" not in raw and not raw.startswith("/api"):
            continue
        path_end = match.end()
        method = _infer_method(text, match.start(), path_end)
        path = _normalize_path(raw)
        key = (method, path)
        if key not in seen:
            seen.add(key)
            routes.append(FeRoute(method=method, path=path, source=ts_path.name))

    for match in _URL_ASSIGN_FETCH_RE.finditer(text):
        raw = match.group(1) or match.group(2) or ""
        if "/api/" not in raw:
            continue
        path_end = match.end()
        method = _infer_method(text, match.start(), path_end)
        path = _normalize_path(raw)
        key = (method, path)
        if key not in seen:
            seen.add(key)
            routes.append(FeRoute(method=method, path=path, source=ts_path.name))

    return routes


def _path_to_regex(path: str) -> re.Pattern[str]:
    escaped = re.escape(path)
    pattern = re.sub(r"\\\{param\\\}", r"[^/]+", escaped)
    pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", pattern)
    return re.compile(f"^{pattern}$")


def _collect_hub_routes() -> list[tuple[str, str]]:
    hub: list[tuple[str, str]] = []

    def _walk(routes):
        """递归遍历路由表，处理 FastAPI _IncludedRouter 包装层。"""
        for route in routes:
            # FastAPI 较新版本用 _IncludedRouter 包装 include_router 的路由
            orig = getattr(route, "original_router", None)
            if orig is not None and hasattr(orig, "routes"):
                _walk(orig.routes)
                continue
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", None)
            if not methods or not path:
                continue
            if not path.startswith("/api"):
                continue
            # 统一去掉尾部斜杠，与 FE 侧 _normalize_path 对齐
            path = path.rstrip("/") if path != "/api" else path
            for method in methods:
                if method in {"HEAD", "OPTIONS"}:
                    continue
                hub.append((method.upper(), path))

    _walk(app.routes)
    return hub


def _hub_matches(fe: FeRoute, hub_routes: list[tuple[str, str]]) -> bool:
    fe_regex = _path_to_regex(fe.path)
    for method, path in hub_routes:
        if method != fe.method:
            continue
        if fe_regex.match(path) or _path_to_regex(path).match(fe.path):
            return True
    return False


def _scan_all_fe_routes() -> list[FeRoute]:
    routes: list[FeRoute] = []
    for ts_file in sorted(FE_API_DIR.glob("*.ts")):
        if ts_file.name in {"index.ts", "client.ts", "client.test.ts"}:
            continue
        routes.extend(_extract_fe_routes(ts_file))
    return routes


@pytest.fixture(scope="module")
def fe_routes() -> list[FeRoute]:
    return _scan_all_fe_routes()


@pytest.fixture(scope="module")
def hub_routes() -> list[tuple[str, str]]:
    return _collect_hub_routes()


def test_priority_modules_contribute_routes(fe_routes: list[FeRoute]) -> None:
    sources = {r.source for r in fe_routes}
    missing = PRIORITY_MODULES - sources
    assert not missing, f"priority api modules produced no routes: {sorted(missing)}"


def test_fe_hub_route_parity(fe_routes: list[FeRoute], hub_routes: list[tuple[str, str]]) -> None:
    assert fe_routes, "expected at least one FE /api/ route from lib/api/*.ts"
    missing: list[str] = []
    for fe in fe_routes:
        if fe.key() in ALLOWED_FE_HUB_MISMATCHES:
            continue
        if not _hub_matches(fe, hub_routes):
            missing.append(f"{fe.method} {fe.path} ({fe.source})")
    assert not missing, (
        "FE lib/api routes without matching Hub endpoint:\n  "
        + "\n  ".join(sorted(missing))
        + "\nAdd Hub route or document exception in ALLOWED_FE_HUB_MISMATCHES."
    )


def test_priority_module_paths_registered(
    fe_routes: list[FeRoute], hub_routes: list[tuple[str, str]]
) -> None:
    priority = [r for r in fe_routes if r.source in PRIORITY_MODULES]
    assert len(priority) >= 20, f"expected rich coverage from priority modules, got {len(priority)}"
    gaps = [
        f"{r.method} {r.path} ({r.source})"
        for r in priority
        if r.key() not in ALLOWED_FE_HUB_MISMATCHES and not _hub_matches(r, hub_routes)
    ]
    assert not gaps, "priority module parity gaps:\n  " + "\n  ".join(sorted(gaps))
