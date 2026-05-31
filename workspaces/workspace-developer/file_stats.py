#!/usr/bin/env python3
import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path


def get_file_extension(filename):
    name, ext = os.path.splitext(filename)
    if not ext:
        return "(no extension)"
    return ext.lower()


def scan_directory(root_path, max_depth=None):
    root = Path(root_path)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")
    files = []
    for entry in root.rglob("*"):
        if max_depth is not None:
            rel = entry.relative_to(root)
            if len(rel.parents) > max_depth or str(rel) == ".":
                continue
        try:
            if entry.is_file():
                files.append(entry)
        except PermissionError:
            print(f"[WARN] Permission denied: {entry}", file=sys.stderr)
    return files


def collect_stats(file_paths):
    stats = defaultdict(lambda: {"count": 0, "total_bytes": 0})
    for fp in file_paths:
        try:
            size = fp.stat().st_size
            ext = get_file_extension(fp.name)
            stats[ext]["count"] += 1
            stats[ext]["total_bytes"] += size
        except OSError:
            continue
    return dict(sorted(stats.items(), key=lambda x: -x[1]["count"]))


def format_report(stats, root_path, min_files=1):
    lines = [f"# File Statistics Report\n"]
    lines.append(f"**Target:** `{root_path}`")
    total_files = sum(v["count"] for v in stats.values())
    total_bytes = sum(v["total_bytes"] for v in stats.values())
    lines.append(f"**Total files:** {total_files}")
    lines.append(f"**Total size:** {_human_size(total_bytes)}\n")
    lines.append("| Extension | Count | Total Size | Avg Size |")
    lines.append("|-----------|-------|------------|----------|")
    for ext, data in stats.items():
        if data["count"] < min_files:
            continue
        avg = data["total_bytes"] / data["count"]
        lines.append(
            f"| {ext:<9} | {data['count']:>5} | {_human_size(data['total_bytes']):>10} | {_human_size(avg):>8} |"
        )
    lines.append("")
    return "\n".join(lines)


def _human_size(bytes_val):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(bytes_val) < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}PB"


def main():
    parser = argparse.ArgumentParser(description="Recursively count files by extension")
    parser.add_argument("--path", default=".", help="Root directory to scan")
    parser.add_argument("--depth", type=int, default=None, help="Max recursion depth")
    parser.add_argument("--min-files", type=int, default=1, help="Min file count to show")
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f"Error: '{args.path}' is not a valid directory", file=sys.stderr)
        sys.exit(1)

    files = scan_directory(args.path, max_depth=args.depth)
    if not files:
        print("No files found.")
        return
    stats = collect_stats(files)
    report = format_report(stats, args.path, min_files=args.min_files)
    print(report)


if __name__ == "__main__":
    main()
