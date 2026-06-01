---
name: project-init
description: "Initialize a new AI teamwork project with standardized directory structure. Use when: 1) User sends '项目协作:' command, 2) Need to create a new project with tasks and deliverables, 3) Starting a multi-agent collaboration project. Creates project at myteam/tasks/{project_id}/ with task_data.json and deliverables/ folder."
metadata: '{"openclaw": {"emoji": "📁", "always": true}}'
allowed-tools: "exec"
---

# Project Init Skill

Initialize a standardized project structure for AI team collaboration (myteam 工程).

## Usage

```
skill: project-init
action: create
name: "Project Name"
description: "Project description"
```

## What it creates

- Project directory: `tasks/project/{project_id}/`（相对 myteam 根目录）
- `task_data.json` - Project metadata and task list
- `deliverables/` - Directory for all deliverables
- `.task.lock` - File lock for concurrent access
- `skill-logs/skills.log` - Skill execution log

## Output

Returns the `project_id` which should be used in subsequent skill calls.

## Script

```bash
# 从 myteam 根目录
python skill/team/project-init/scripts/init.py "Project Name" "Description"
python skill/team/project-init/scripts/init.py validate-graph <project_id>
```

**`validate-graph`**：对已有项目调用与 `task-monitor validate-graph`、`common/graph_gate` 同源的 `project-data check-cycle`；图非法时非 0 退出。

## 与 myteam 项目群绑定

创建项目后，可在 myteam UI 或通过 API 将群组绑定到项目：

```
POST /api/groups/{group_id}/bind-project
{ "project_id": "pro_xxx" }
```

绑定后，`task-dispatch` / `agent-notify` 的 dispatch 通知会发到 **myteam 项目群**（@Agent），而非 Telegram。

## Example workflow

1. User: "项目协作:帮我做一个市场调研"
2. Agent: Call `project-init` to create project
3. Agent: Add tasks using `project-data` skill
4. （可选）绑定 myteam 群组到 `project_id`
5. Agent: Run the single kernel `python skill/team/common/run_kernel.py <项目ID> --goal "..."`（旧 `task-executor` 仅回退保留）
