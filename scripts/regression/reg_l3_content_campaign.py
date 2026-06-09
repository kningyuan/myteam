#!/usr/bin/env python3
"""REG-L3 content-campaign：Level-3 场景 CHECK_ONLY stub。

验证 content-campaign workflow 与 publish-post task_type 注册；
文档化 G4 evidence_url 验收标准（全量 E2E 留待 L3 实施）。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l3_content_campaign.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "regression"))
from regression_archive import append_run_record  # noqa: E402

WORKFLOW_ID = "content-campaign"
WORKFLOW_PATH = REPO / "business/workflows/content-campaign.yaml"
TEMPLATES_PATH = REPO / "business/templates/templates.yaml"
PUBLISH_TASK_TYPE = "publish-post"


def _load_yaml(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _templates_task_types(templates: dict) -> set[str]:
    skip = {"version", "meta"}
    return {k for k in templates if k not in skip and isinstance(templates.get(k), dict)}


def check_prerequisites() -> tuple[bool, list[str]]:
    issues: list[str] = []

    if not WORKFLOW_PATH.is_file():
        issues.append(f"缺少 workflow: {WORKFLOW_PATH.relative_to(REPO)}")
        return False, issues

    wf = _load_yaml(WORKFLOW_PATH)
    if not isinstance(wf, dict):
        issues.append("content-campaign workflow 无法解析")
        return False, issues

    if wf.get("id") != WORKFLOW_ID:
        issues.append(f"workflow id 期望 {WORKFLOW_ID!r}，实际 {wf.get('id')!r}")

    tasks = wf.get("tasks") or []
    publish_tasks = [
        t for t in tasks
        if isinstance(t, dict) and t.get("task_type") == PUBLISH_TASK_TYPE
    ]
    if not publish_tasks:
        issues.append(f"workflow 未含 {PUBLISH_TASK_TYPE!r} 任务")

    if not TEMPLATES_PATH.is_file():
        issues.append(f"缺少 templates.yaml: {TEMPLATES_PATH.relative_to(REPO)}")
        return False, issues

    templates = _load_yaml(TEMPLATES_PATH)
    if not isinstance(templates, dict):
        issues.append("templates.yaml 无法解析")
        return False, issues

    registered = _templates_task_types(templates)
    if PUBLISH_TASK_TYPE not in registered:
        issues.append(f"templates.yaml 缺少 task_type: {PUBLISH_TASK_TYPE}")

    return len(issues) == 0, issues


def _print_g4_criteria() -> None:
    print("=== G4 evidence_url 验收标准（CHECK_ONLY 文档，未 E2E 验）===")
    print("  1. publish-post 交付物含「已发布URL」章节，URL 单独成行")
    print("  2. Gate 真实 HTTP 访问 URL，页面含帖子标题（非纸面链接）")
    print("  3. 交付物 evidence/ 目录含发布成功截图（.png/.jpg）")
    print("  4. 禁止伪造 URL；未登录/发布失败须重试而非编造")
    print("  详见 business/skills/publish-post/SKILL.md 与 templates publish-post Gate")
    print()


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    check_only = os.environ.get("REG_L3_CHECK_ONLY", "1").lower() in ("1", "true", "yes")

    print("=== REG-L3 content-campaign（CHECK_ONLY stub）===")
    print(f"  workflow: {WORKFLOW_ID}")
    print(f"  path:     {WORKFLOW_PATH.relative_to(REPO)}")
    _print_g4_criteria()

    if not check_only:
        print("REG-L3 content-campaign: 全量 E2E 尚未实现，请使用 REG_L3_CHECK_ONLY=1", file=sys.stderr)
        return 2

    ok, issues = check_prerequisites()
    if ok:
        print("=== prerequisites ===")
        print(f"  workflow:              OK")
        print(f"  task_type {PUBLISH_TASK_TYPE}: OK")
        print("REG-L3 content-campaign: PASS")
        rec = append_run_record(
            reg_id="REG-L3-CC",
            project_id="content-campaign",
            pass_=True,
            kpis={"G4": "check_only_stub"},
            meta={"mode": "check_only"},
        )
        print(f"  I-06 archived: run_id={rec['run_id']}")
        return 0

    print("=== prerequisites ===")
    for msg in issues:
        print(f"  FAIL: {msg}")
    print("REG-L3 content-campaign: FAIL")
    append_run_record(
        reg_id="REG-L3-CC",
        project_id="content-campaign",
        pass_=False,
        kpis={"G4": "check_only_stub"},
        meta={"mode": "check_only", "issues": issues},
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
