#!/usr/bin/env python3
"""diagram_brief.yaml → .drawio（mxGraphModel）。"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def build_mxfile(data: dict) -> str:
    page = data.get("page") or {}
    pw = int(page.get("width", 1169))
    ph = int(page.get("height", 827))
    title = data.get("title") or "Diagram"
    style = data.get("style") or {}
    title_size = int(style.get("title_size", 18))
    font_size = int(style.get("font_size", 12))

    cells: list[str] = [
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
        f'<mxCell id="title" value="{_esc(title)}" '
        f'style="text;html=1;strokeColor=none;fillColor=none;align=center;'
        f'verticalAlign=middle;fontSize={title_size};fontStyle=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="200" y="30" width="560" height="40" as="geometry"/></mxCell>',
    ]

    nodes = data.get("nodes") or []
    for n in nodes:
        nid = n["id"]
        label = _esc(n.get("label", nid))
        x, y = int(n.get("x", 80)), int(n.get("y", 120))
        w, h = int(n.get("w", 140)), int(n.get("h", 60))
        fill = n.get("fill", "#dae8fc")
        stroke = n.get("stroke", "#6c8ebf")
        cells.append(
            f'<mxCell id="{_esc(nid)}" value="{label}" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};'
            f'strokeColor={stroke};fontSize={font_size};" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )

    for i, e in enumerate(data.get("edges") or []):
        eid = f"e{i}"
        src, tgt = e["from"], e["to"]
        lbl = e.get("label")
        val = f' value="{_esc(lbl)}"' if lbl else ""
        cells.append(
            f'<mxCell id="{eid}"{val} '
            f'style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeWidth=2;" '
            f'edge="1" parent="1" source="{_esc(src)}" target="{_esc(tgt)}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>'
        )

    inner = "\n        ".join(cells)
    return f"""<mxfile host="app.diagrams.net" agent="myteam-diagram-build">
  <diagram name="{_esc(title)}" id="diagram-1">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" page="1"
      pageWidth="{pw}" pageHeight="{ph}">
      <root>
        {inner}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("brief", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    if yaml is None:
        print("ERROR: 需要 PyYAML (pip install pyyaml)", file=sys.stderr)
        return 1
    if not args.brief.is_file():
        print(f"ERROR: 找不到 {args.brief}", file=sys.stderr)
        return 1
    data = yaml.safe_load(args.brief.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("ERROR: brief 须为 YAML 对象", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_mxfile(data), encoding="utf-8")
    print(f"OK: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
