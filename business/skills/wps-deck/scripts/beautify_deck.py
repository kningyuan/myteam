#!/usr/bin/env python3
"""对已有 deck.pptx 做视觉增强（配色/字号/背景），WPS 不可用时的美化兜底。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ACCENT = (0x1A, 0x56, 0xDB)
DARK = (0x1E, 0x29, 0x3B)
BODY = (0x33, 0x40, 0x55)
WHITE = (0xFF, 0xFF, 0xFF)
LIGHT_BG = (0xF0, 0xF4, 0xFF)


def _rgb(r, g, b):
    from pptx.dml.color import RGBColor
    return RGBColor(r, g, b)


def beautify(pptx_path: Path, out_path: Path | None = None) -> int:
    try:
        from pptx import Presentation
        from pptx.enum.dml import MSO_THEME_COLOR
        from pptx.util import Inches, Pt
    except ImportError:
        print("ERROR: pip install python-pptx", file=sys.stderr)
        return 1

    out = out_path or pptx_path
    prs = Presentation(str(pptx_path))

    for idx, slide in enumerate(prs.slides):
        # 浅色背景条（section/content 页）
        if idx > 0:
            try:
                shape = slide.shapes.add_shape(
                    1,  # MSO_SHAPE.RECTANGLE
                    Inches(0), Inches(0),
                    prs.slide_width, Inches(0.08),
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = _rgb(*ACCENT)
                shape.line.fill.background()
            except Exception:
                pass

        if slide.shapes.title and slide.shapes.title.text_frame:
            for p in slide.shapes.title.text_frame.paragraphs:
                p.font.bold = True
                p.font.size = Pt(34 if idx == 0 else 30)
                p.font.color.rgb = _rgb(*ACCENT if idx == 0 else DARK)

        for shape in slide.shapes:
            if not shape.has_text_frame or shape == slide.shapes.title:
                continue
            if shape.shape_type == 13:  # placeholder
                for p in shape.text_frame.paragraphs:
                    p.font.size = Pt(18 if idx == 0 else 20)
                    p.font.color.rgb = _rgb(*BODY)

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"OK: beautified → {out} ({len(prs.slides)} slides)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()
    if not args.pptx.is_file():
        print(f"ERROR: 不存在 {args.pptx}", file=sys.stderr)
        return 1
    return beautify(args.pptx, args.output)


if __name__ == "__main__":
    sys.exit(main())
