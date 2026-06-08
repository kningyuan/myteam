#!/usr/bin/env python3
"""一次性：按 agents_registry.json 创建缺失 workspace 并写入 agents_config 默认项。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hub.paths import AGENTS_CONFIG_FILE, AGENTS_REGISTRY_FILE, WORKSPACES_DIR, WORKSPACE_PREFIX
from base.agent_factory import generate_agent

ROLE_AGENTS = {
    "main": """## 职责边界
- 协调者：team_config/task_plan/triage 由框架触发；DAG 中仅 strategy 类文档。
- 禁止承担 research/code/content/test/publish 等 execute 交付。
""",
    "researcher": """## 职责边界
- 仅 task_type=research：深度调研报告。
- 禁止 code-*、content、seo-plan、publish-post。
""",
    "developer": """## 职责边界
- code-writing、code-deliverable：可运行工程与代码交付。
- 禁止 test-plan/code-testing、content、publish-post。
""",
    "tester": """## 职责边界
- test-plan、code-testing：测试计划与测试工程。
- 禁止编写业务功能代码、禁止部署。
""",
    "test_dev": """## 职责边界
- 仅 code-writing：小脚本与补丁，完整工程交给 developer。
""",
    "deputy": """## 职责边界
- 仅承担 strategy、review 类任务；recurring 项目做轮次复盘。
- 不编写代码、不做调研报告、不发布社媒。
""",
    "product": """## 职责边界
- strategy：方案对比、产品决策文档。
- research：需求向轻量调研；深度行业调研交给 researcher。
- 禁止 code-*、test-*、publish-post、seo-plan。
""",
    "content": """## 职责边界
- 仅 task_type=content：长文、教程、读者向文档。
- 不做 SEO 方案、不写代码、不发布外链。
""",
    "seo": """## 职责边界
- 仅 task_type=seo-plan：关键词、技术 SEO、内容集群规划。
- 不写完整正文（交给 content）、不写代码。
""",
    "ops": """## 职责边界
- 仅 task_type=code-deployment：部署步骤、验证、回滚记录。
- 依赖 developer 产出；不做功能开发与测试计划。
""",
    "social": """## 职责边界
- 仅 task_type=publish-post：真实发布 + URL/截图证据。
- 不写长文、不做 SEO 方案。
""",
    "docs": """## 职责边界
- task_type=content，侧重技术文档整理与交付物汇总。
- 不做 SEO、发布、代码实现。
""",
}

DEFAULT_BACKEND = {
    "main": ("claude", "claude-haiku-4-5"),
    "deputy": ("claude", "claude-haiku-4-5"),
    "researcher": ("claude", "claude-sonnet-4-6"),
    "product": ("claude", "claude-sonnet-4-6"),
    "developer": ("claude", "claude-sonnet-4-6"),
    "test_dev": ("claude", "claude-haiku-4-5"),
    "tester": ("claude", "claude-sonnet-4-6"),
    "content": ("claude", "claude-sonnet-4-6"),
    "seo": ("claude", "claude-haiku-4-5"),
    "ops": ("claude", "claude-haiku-4-5"),
    "social": ("claude", "claude-haiku-4-5"),
    "docs": ("claude", "claude-haiku-4-5"),
}


def main() -> None:
    reg = json.loads(AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    agents = reg.get("agents") or {}
    cfg = {}
    if AGENTS_CONFIG_FILE.exists():
        cfg = json.loads(AGENTS_CONFIG_FILE.read_text(encoding="utf-8"))

    created = []
    for aid, meta in agents.items():
        ws = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{aid}"
        if not ws.exists():
            backend, model = DEFAULT_BACKEND.get(aid, ("claude", "claude-haiku-4-5"))
            r = generate_agent(
                aid,
                meta.get("description") or aid,
                backend_id=backend,
                model=model,
                chinese_name=meta.get("name") or aid,
                use_existing_agent_for_gen=False,
                role=meta.get("role") or "worker",
                task_types=list(meta.get("task_types") or []),
                capabilities=list(meta.get("capabilities") or []),
            )
            if not r.get("success"):
                print(f"skip {aid}: {r.get('error')}")
                continue
            extra = ROLE_AGENTS.get(aid)
            if extra:
                ag = ws / "AGENTS.md"
                if ag.exists():
                    ag.write_text(ag.read_text(encoding="utf-8").rstrip() + "\n\n" + extra, encoding="utf-8")
            created.append(aid)
        elif aid not in cfg:
            backend, model = DEFAULT_BACKEND.get(aid, ("claude", "claude-haiku-4-5"))
            cfg[aid] = {
                "backend": backend,
                "model": model,
                "extra": {},
                "name": meta.get("name") or aid,
                "workspace": f"business/workspaces/workspace-{aid}",
            }

    # 确保已有 agent 的 config 有 name
    for aid, meta in agents.items():
        entry = cfg.setdefault(aid, {})
        if not entry.get("name"):
            entry["name"] = meta.get("name") or aid
        if not entry.get("workspace"):
            entry["workspace"] = f"business/workspaces/workspace-{aid}"
        be, mo = DEFAULT_BACKEND.get(aid, ("claude", "claude-haiku-4-5"))
        entry.setdefault("backend", be)
        entry.setdefault("model", mo)
        entry.setdefault("extra", {})

    AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGENTS_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    patched = []
    for aid, extra in ROLE_AGENTS.items():
        ag = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{aid}" / "AGENTS.md"
        if not ag.exists():
            continue
        text = ag.read_text(encoding="utf-8")
        if "## 职责边界" not in text:
            ag.write_text(text.rstrip() + "\n\n" + extra, encoding="utf-8")
            patched.append(aid)

    print(f"created workspaces: {created or '(none)'}")
    print(f"patched AGENTS.md: {patched or '(none)'}")
    print(f"agents_config: {len(cfg)} agents")


if __name__ == "__main__":
    main()
