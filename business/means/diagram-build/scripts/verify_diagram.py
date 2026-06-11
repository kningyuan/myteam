#!/usr/bin/env python3
"""验收 diagram.drawio + diagram.png + 可选交付物。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def verify_drawio(path: Path, *, min_bytes: int = 200) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"drawio 不存在: {path}"]
    if path.stat().st_size < min_bytes:
        errs.append(f"drawio 过小 ({path.stat().st_size} bytes)")
    text = path.read_text(encoding="utf-8", errors="replace")
    if "<mxfile" not in text and "<mxGraphModel" not in text:
        errs.append("drawio 不是有效的 mxfile/mxGraphModel")
    return errs


def verify_png(path: Path, *, min_bytes: int = 1000) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"png 不存在: {path}"]
    if path.stat().st_size < min_bytes:
        errs.append(f"png 过小 ({path.stat().st_size} bytes)")
    if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        errs.append("png 文件头无效")
    return errs


def verify_deliverable(md: Path) -> list[str]:
    errs: list[str] = []
    if not md.is_file():
        return errs
    text = md.read_text(encoding="utf-8")
    for sec in ("图表目标", "结构说明", "产出文件"):
        if sec not in text:
            errs.append(f"交付物缺少章节: {sec}")
    if "diagram.drawio" not in text:
        errs.append("交付物未提及 diagram.drawio")
    if "diagram.png" not in text:
        errs.append("交付物未提及 diagram.png")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio", type=Path)
    ap.add_argument("--png", type=Path, required=True)
    ap.add_argument("--deliverable", type=Path, default=None)
    args = ap.parse_args()
    errs = verify_drawio(args.drawio) + verify_png(args.png)
    if args.deliverable:
        errs.extend(verify_deliverable(args.deliverable))
    if errs:
        for e in errs:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(f"verify_diagram: PASS ({args.drawio.name}, {args.png.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
