#!/usr/bin/env python3
"""workflow-creator 自动验证脚本（P4a）。

Agent 生成 workflow YAML 后，自动跑 validate_workflow() 校验，
通过才允许写入 business/workflows/。

用法：
    PYTHONPATH=backend venv/bin/python3 business/scripts/validate_workflow.py <workflow_id>
    PYTHONPATH=backend venv/bin/python3 business/scripts/validate_workflow.py --file <path/to/workflow.yaml>

退出码：
    0 = 校验通过
    1 = 校验失败（含具体错误信息）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.workflow.workflow_loader import load_workflow, validate_workflow


def validate_workflow_id(workflow_id: str) -> tuple[bool, str]:
    """按 workflow id 校验：加载 + validate_workflow。"""
    try:
        profile = load_workflow(workflow_id)
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        return False, f"加载失败：{e}"
    try:
        validate_workflow(profile)
    except ValueError as e:
        return False, str(e)
    return True, f"✅ workflow「{profile.id}」校验通过（{len(profile.tasks)} tasks, {len(profile.loops)} loops）"


def validate_workflow_file(path: str) -> tuple[bool, str]:
    """按文件路径校验。"""
    fp = Path(path)
    if not fp.is_file():
        return False, f"文件不存在：{fp}"
    workflow_id = fp.stem
    try:
        profile = load_workflow(workflow_id, path=fp)
    except Exception as e:
        return False, f"加载失败：{e}"
    try:
        validate_workflow(profile)
    except ValueError as e:
        return False, str(e)
    return True, f"✅ workflow「{profile.id}」校验通过（{len(profile.tasks)} tasks, {len(profile.loops)} loops）"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="workflow 校验（P4a：通过才允许写入）")
    p.add_argument("workflow_id", nargs="?", help="workflow id（文件名不含扩展名）")
    p.add_argument("--file", metavar="PATH", help="workflow YAML 文件路径")
    args = p.parse_args(argv)

    if args.file:
        ok, msg = validate_workflow_file(args.file)
    elif args.workflow_id:
        ok, msg = validate_workflow_id(args.workflow_id)
    else:
        p.error("请指定 workflow_id 或 --file")
        return 2

    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
