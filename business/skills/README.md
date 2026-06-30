# Skill Pack Guidelines

`business/skills/` contains agent capability packs. A Skill teaches an agent how to perform a concrete task; it is not part of the runtime kernel.

## External / vendor skills

Third-party skill packs are **symlinks** under `business/skills/<id>/` pointing at the real upstream directory. Do not copy only `SKILL.md`. Register upstream paths in `backend/common/skill_link.py` (`VENDOR_SKILL_SOURCES`). Run skill sync so `.cursor/skills/` and agent workspaces link through the same anchor.

**展示分类**（方法论 / 代码工程 / OfficeCLI 等）写在 `business/skills/categories.yaml`，**不**再使用 `business/skills/<category>/<id>/` 物理嵌套；改分类只更新 yaml，skill 目录始终在顶层 `<id>/`。

## SKILL.md frontmatter（Agent 选型必填）

每个 `SKILL.md` **文件最顶部**必须有 YAML frontmatter，`description` 用于 Agent 判断何时挂载/读取该 skill：

```yaml
---
name: 展示名（可选，UI 用）
description: 一句话说明做什么、何时用（必填；Agent 选型依据）
---
```

- 系统读取链：`SKILL.md` frontmatter → `skill_catalog` → `build_skill_context` 注入 system prompt 简介列表。
- 完整用法不在 prompt 里；Agent 须 `Read` 完整 `SKILL.md` 再执行。
- vendor skill 可在 `backend/common/skill_display_names.py` 覆盖中文展示名/简介。

| Vendor | Local clone | Example ids |
|--------|-------------|-------------|
| gstack | `~/.claude/skills/gstack/` | `browse` |
| [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI/tree/main/skills) | `~/skill/OfficeCLI/skills/` | `officecli`, `officecli-pptx`, `morph-ppt`, … |

## What Belongs in a Skill

- Domain execution steps, such as publishing a post, running a platform-specific script, or gathering evidence.
- Tool usage instructions that an agent needs while executing a task.
- Red lines and quality expectations for a concrete action.
- Examples of valid outputs, screenshots, URLs, or evidence records.
- Idempotency guidance for external side effects, such as checking whether a post already exists before publishing.

## What Does Not Belong in a Skill

- Process scheduling, DAG traversal, queues, or retry policy.
- Interaction schema definitions or response validation rules.
- Watchdog, heartbeat, cancellation, token accounting, persistence, or recovery.
- Gate implementation logic or hidden bypasses for deterministic checks.
- New task types that are not registered in `business/templates/templates.yaml`.
- Instructions to mutate `business/tasks/state.db` or system config directly.

## Authoring Checklist

Before adding or changing a Skill:

0. **Check external sources first** — official docs, GitHub repos, or community skills. Decide **direct adopt**, **adapt**, or **self-implement** (see `docs/DESIGN-SKILL-SYSTEM.md` §3.2). Record URL, license, and adoption path in frontmatter or `references/UPSTREAM.md`.
1. Confirm the task type already exists in `business/templates/templates.yaml`, or add it there first.
2. Keep `SKILL.md` focused on how the agent should execute the task.
3. Make evidence requirements concrete and falsifiable: URL, screenshot, external id, or file path.
4. If the task has external side effects, document how the agent avoids duplicate actions on retry.
5. Do not duplicate required sections or Gate rules unless the text is needed as an execution example.
6. Keep the Skill reusable across projects; project-specific state belongs in `business/tasks/` or agent workspace memory.

## Relationship to the System

```text
A · myteam (Kernel + workflows)     — when/who/Gate
B · Agent Delivery (playbooks)    — ALL / catalog / experience
B · Means (business/means/)       — scripts & templates (diagram-build, …)
B · Skills (business/skills/)     — task_type router SKILL.md + catalog.yaml
```

### B 层目录

```text
business/playbooks/          # ALL.md + 通用过程模板 + scaffold_process.sh
business/means/              # 可插拔小工具（diagram-build …）
business/skills/catalog.yaml # Agent 自选 means / router（扁平 business/skills/<id>/）
business/skills/categories.yaml # UI 展示分类与成员列表（元数据）
business/experience/         # ledger schema
business/workspaces/         # IDENTITY.md / SOUL.md 身份；能力与 task_type 见 agents_registry.json
```

Workflow **不得**写 `【Skill】`；自选记录在 `plan.md`。lint：`scripts/lint_workflows_no_skill.sh`。

### Workflow 共享包（仍可用）

```text
business/skills/product-operations/   # 待建：独立 task router
business/skills/wps-deck/             # 待迁 means（Sprint 2+）
```

内核与 catalog 均按 **`business/skills/<skill_id>/SKILL.md`** 扁平路径注入 router；展示分类见 `categories.yaml`。校验：`scripts/audit_skill_matrix.py` 或 `GET /api/skills/matrix` 的 `catalog_missing_routers`。

If a proposed Skill needs to control scheduling, persistence, or validation, it is probably not a Skill. Move that concern to the System Kernel or Strategy Registry instead.
