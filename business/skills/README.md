# Skill Pack Guidelines

`business/skills/` contains agent capability packs. A Skill teaches an agent how to perform a concrete task; it is not part of the runtime kernel.

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
business/skills/catalog.yaml # Agent 自选 means / router
business/experience/         # ledger schema
business/workspaces/         # AGENTS.md / SOUL.md 身份
```

Workflow **不得**写 `【Skill】`；自选记录在 `plan.md`。lint：`scripts/lint_workflows_no_skill.sh`。

### Workflow 共享包（仍可用）

```text
business/skills/product-operations/
business/skills/wps-deck/        # 待迁 means（Sprint 2+）
  SKILL.md
  scripts/
```

内核仍按 `business/skills/<task_type>/SKILL.md` 注入 router 路径。

If a proposed Skill needs to control scheduling, persistence, or validation, it is probably not a Skill. Move that concern to the System Kernel or Strategy Registry instead.
