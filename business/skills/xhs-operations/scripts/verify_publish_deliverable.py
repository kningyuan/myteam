#!/usr/bin/env python3
"""静态校验小红书 publish-post 交付物（publish-xhs 模板）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s<>\"']+")
XHS_HOST = "xiaohongshu.com"
REQUIRED_SECTIONS = ("发布平台", "帖子标题", "已发布URL", "证据截图", "话题标签")


def _extract_section(text: str, name: str) -> str:
    pattern = rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s+|\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: verify_publish_deliverable.py <deliverable.md>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"ERROR: 文件不存在 {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    issues: list[str] = []

    for sec in REQUIRED_SECTIONS:
        if not _extract_section(text, sec):
            issues.append(f"缺少章节: ## {sec}")

    platform = _extract_section(text, "发布平台")
    if platform and "小红书" not in platform:
        issues.append("发布平台应含「小红书」")

    url_block = _extract_section(text, "已发布URL")
    urls = [u.rstrip(").,;") for u in URL_RE.findall(url_block or text)]
    xhs_urls = [u for u in urls if XHS_HOST in u]
    if not xhs_urls:
        issues.append(f"未找到合规 URL（须含 {XHS_HOST}）")

    title = _extract_section(text, "帖子标题")
    if not title or title.startswith("<"):
        issues.append("帖子标题为空或为占位符")

    tags = _extract_section(text, "话题标签")
    if not tags or "#" not in tags:
        issues.append("话题标签须含 # 标签")

    shot = _extract_section(text, "证据截图")
    if shot:
        shot_path = path.parent / shot.splitlines()[0].strip()
        if not shot_path.is_file():
            issues.append(f"证据截图不存在: {shot_path}")
    else:
        issues.append("证据截图章节为空")

    if len(text) < 20:
        issues.append("交付物过短")

    if issues:
        print("FAIL: 小红书 publish-post 交付物校验未通过", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
        return 1

    print(f"OK: {path.name} 静态校验通过")
    print(f"  URL: {xhs_urls[0]}")
    print(f"  标题: {title.splitlines()[0][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
