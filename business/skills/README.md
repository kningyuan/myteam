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

1. Confirm the task type already exists in `business/templates/templates.yaml`, or add it there first.
2. Keep `SKILL.md` focused on how the agent should execute the task.
3. Make evidence requirements concrete and falsifiable: URL, screenshot, external id, or file path.
4. If the task has external side effects, document how the agent avoids duplicate actions on retry.
5. Do not duplicate required sections or Gate rules unless the text is needed as an execution example.
6. Keep the Skill reusable across projects; project-specific state belongs in `business/tasks/` or agent workspace memory.

## Relationship to the System

```text
System Kernel decides when and what to run.
Strategy Registry defines what a valid task result looks like.
Skill Pack teaches the agent how to produce that result.
```

If a proposed Skill needs to control scheduling, persistence, or validation, it is probably not a Skill. Move that concern to the System Kernel or Strategy Registry instead.
