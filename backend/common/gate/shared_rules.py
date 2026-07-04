"""团队通用 rules — business/rules/*.md，全员共享。"""

from __future__ import annotations

from typing import Optional

from common.paths import RULES_DIR

_SHARED_LABELS: dict[str, str] = {
    "universal-rules.md": "团队协作通用规则",
    "ethos.md": "团队哲学",
    "interactive-guide.md": "交互场景专规",
    "brainstorming-guide.md": "讨论场景专规",
    "worker-template.md": "编排执行专规",
}


def _validate_filename(filename: str) -> str:
    name = (filename or "").strip()
    if not name or ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"非法文件名：{filename}")
    if not name.endswith(".md"):
        raise ValueError("仅支持 .md 文件")
    return name


def shared_rule_label(filename: str) -> str:
    return _SHARED_LABELS.get(filename, filename.removesuffix(".md"))


def list_shared_rule_files() -> list[dict]:
    if not RULES_DIR.is_dir():
        return []
    items: list[dict] = []
    for p in sorted(RULES_DIR.glob("*.md")):
        if not p.is_file():
            continue
        fname = p.name
        items.append({
            "filename": fname,
            "label": shared_rule_label(fname),
            "path": str(p.relative_to(RULES_DIR.parent.parent)),
            "size": p.stat().st_size,
        })
    return items


def read_shared_rule(filename: str) -> Optional[str]:
    fname = _validate_filename(filename)
    fp = RULES_DIR / fname
    if not fp.is_file():
        return None
    return fp.read_text(encoding="utf-8")


def write_shared_rule(filename: str, content: str) -> None:
    fname = _validate_filename(filename)
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    fp = RULES_DIR / fname
    if not isinstance(content, str):
        raise ValueError("content 须为字符串")
    fp.write_text(content, encoding="utf-8")


def read_all_shared_rules() -> dict[str, str]:
    out: dict[str, str] = {}
    for item in list_shared_rule_files():
        fname = item["filename"]
        out[fname] = read_shared_rule(fname) or ""
    return out
