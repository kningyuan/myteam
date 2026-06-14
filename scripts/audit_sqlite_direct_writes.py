#!/usr/bin/env python3
"""Audit direct SQLite writes outside the Store layer.

Greps ``backend/`` for ``_conn.execute`` and ``sqlite3.connect`` outside
``backend/common/store.py`` and ``backend/store/``. Writes
``docs/assessments/sqlite-direct-write-audit.md``.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
OUT = REPO / "docs/assessments/sqlite-direct-write-audit.md"

STORE_PY = BACKEND / "common" / "store.py"
STORE_PKG = BACKEND / "store"

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"_conn\.execute"), "_conn.execute"),
    (re.compile(r"sqlite3\.connect\s*\("), "sqlite3.connect"),
)


def _allowed(path: Path) -> bool:
    if path.resolve() == STORE_PY.resolve():
        return True
    try:
        path.resolve().relative_to(STORE_PKG.resolve())
        return True
    except ValueError:
        return False


def scan() -> dict[str, list[tuple[int, str, str]]]:
    hits: dict[str, list[tuple[int, str, str]]] = {label: [] for _, label in PATTERNS}
    for path in sorted(BACKEND.rglob("*.py")):
        if _allowed(path):
            continue
        rel = path.relative_to(REPO)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for pattern, label in PATTERNS:
                if pattern.search(line):
                    hits[label].append((lineno, str(rel), line.strip()))
    return hits


def render(hits: dict[str, list[tuple[int, str, str]]]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = sum(len(v) for v in hits.values())
    lines = [
        "# SQLite 直写审计\n",
        "\n",
        f"> **生成时间**：{ts}\n",
        "> **范围**：`backend/` 内 `_conn.execute` / `sqlite3.connect`\n",
        "> **排除**：`backend/common/store.py`、`backend/store/`\n",
        "\n",
        f"共 **{total}** 处直写（供 2.4 PG 迁移 / 2.5 group_manager 收拢输入）。\n",
        "\n",
    ]
    for label in ("_conn.execute", "sqlite3.connect"):
        rows = hits.get(label, [])
        lines.append(f"## {label}（{len(rows)}）\n\n")
        if not rows:
            lines.append("_无匹配_\n\n")
            continue
        for lineno, rel, snippet in rows:
            lines.append(f"- `{rel}:{lineno}` — `{snippet[:120]}`\n")
        lines.append("\n")
    return "".join(lines)


def main() -> int:
    hits = scan()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(hits), encoding="utf-8")
    total = sum(len(v) for v in hits.values())
    print(f"Wrote {OUT.relative_to(REPO)} ({total} hits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
