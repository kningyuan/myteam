"""共用 YAML 工具 — distill.py 与 lesson.py 共享的轻量 YAML 解析。"""

from __future__ import annotations

import re
from typing import Any, Optional

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BLOCK_KEY_RE = re.compile(
    r"^(\w[\w_-]*)\s*:\s*\|\s*\n((?:[ \t]+[^\n]*\n?)*)",
    re.MULTILINE,
)


def parse_block_scalars(raw: str) -> dict[str, str]:
    """提取 key: | 多行块标量。"""
    out: dict[str, str] = {}
    for m in _BLOCK_KEY_RE.finditer(raw):
        key = m.group(1)
        block = m.group(2)
        lines = []
        for ln in block.splitlines():
            if ln.startswith(" ") or ln.startswith("\t"):
                lines.append(ln.strip())
            elif ln.strip():
                lines.append(ln.strip())
        out[key] = "\n".join(lines).strip()
    return out


def parse_simple_yaml(raw: str) -> dict[str, Any]:
    """轻量 YAML：支持 key: | 多行块 + 列表 + 单行 kv。"""
    data: dict[str, Any] = dict(parse_block_scalars(raw))
    current_key: Optional[str] = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^\w[\w_-]*\s*:\s*\|\s*$", stripped):
            continue
        if stripped.startswith("- ") and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(stripped[2:].strip())
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key, val = key.strip(), val.strip()
            if val == "|":
                continue
            current_key = key
            if key in data:
                continue
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                data[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            else:
                data[key] = val.strip("'\"")
    try:
        import yaml

        loaded = yaml.safe_load(raw)
        if isinstance(loaded, dict):
            for k, v in loaded.items():
                if k not in data or not data[k]:
                    data[k] = v
    except Exception:
        pass
    return data


def strip_comments(raw: str) -> str:
    """去掉 HTML 注释。"""
    return _COMMENT_RE.sub("", raw or "").strip()


def clip(text: str, n: int = 280) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def clip_lines(text: str, n: int = 280) -> str:
    """同上但保留换行以适应前缀提取场景。"""
    lines = []
    for ln in (text or "").splitlines():
        clipped = clip(ln, n)
        if clipped:
            lines.append(clipped)
    return "\n".join(lines)