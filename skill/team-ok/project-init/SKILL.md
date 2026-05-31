---
name: project-init
description: "Initialize a new AI teamwork project with standardized directory structure. Use when: 1) User sends '项目协作:' command, 2) Need to create a new project with tasks and deliverables, 3) Starting a multi-agent collaboration project. Creates project at /Users/user/.openclaw/tasks/projects/{project_id}/ with task_data.json and deliverables/ folder."
metadata: '{"openclaw": {"emoji": "📁", "always": true}}'
allowed-tools: "exec"
---

# Project Init Skill

Initialize a standardized project structure for AI team collaboration.

## Usage

Call this skill when you need to create a new project:

```
skill: project-init
action: create
name: "Project Name"
description: "Project description"
```

## What it creates

- Project directory: `/Users/user/.openclaw/tasks/projects/{project_id}/`
- `task_data.json` - Project metadata and task list
- `deliverables/` - Directory for all deliverables
- `.task.lock` - File lock for concurrent access

## Output

Returns the `project_id` which should be used in subsequent skill calls.

## Script

Use the provided script:
```bash
{baseDir}/scripts/init.py "Project Name" "Description"
{baseDir}/scripts/init.py validate-graph <project_id>
```

**`validate-graph`**：对**已有**项目调用与 **`task-monitor validate-graph`**、**`common/graph_gate`** 同源的 **`project-data check-cycle`**；图非法时 **非 0 退出**（新建空 `tasks` 的项目校验为通过）。

## Example workflow

1. User: "项目协作:帮我做一个市场调研"
2. Agent: Call `project-init` to create project
3. Agent: Add tasks using `project-data` skill
4. Agent: Generate markdown and notify user
