---
name: task-executor
description: "流程引擎，控制团队协作项目的标准执行流程。使用场景：1) 启动新项目，2) 自动调度任务，3) 验证执行结果，4) 推动流程到下一步。Agent 只负责执行具体任务和提供决策输入。"
metadata: '{"openclaw": {"emoji": "⚙️", "always": true}}'
allowed-tools: "exec"
---

# Task Executor Skill

流程引擎，控制团队协作项目的标准执行流程。

## 核心原则

- **流程由引擎控制**：固定状态机，100% 准确
- **Main Agent 是决策者**：提供团队配置、任务规划
- **Worker Agent 是执行者**：按模板生成内容
- **验证是固定逻辑**：代码检查，非 LLM 判断

## 使用方式

```bash
~/.openclaw/skills/team-ok/task-executor/scripts/executor.py "<项目名称>" "<项目描述>"
```

### 示例

```bash
# 启动一个标准项目
~/.openclaw/skills/team-ok/task-executor/scripts/executor.py "AI 团队协作工具开发" "开发一套 AI 驱动的团队协作系统"
```

## 状态机流程

```
INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP → COMPLETE
```

### 各状态说明

| 状态 | 引擎行为 | Agent 行为 |
|------|---------|-----------|
| **INIT** | 调用 project-init 创建项目 | - |
| **TEAM_CONFIG** | 通知 Main 配置团队，验证结果 | Main 返回 agent 列表 |
| **TASK_PLAN** | 通知 Main 规划任务，验证结果 | Main 返回任务列表和依赖 |
| **ADD_TASKS** | 调用 project-data 添加任务并确认 | - |
| **DISPATCH_LOOP** | 循环调度任务，验证结果，重试失败 | Worker 按模板执行 |
| **COMPLETE** | 更新项目状态，发送通知 | - |

## 验证规则

引擎使用固定逻辑验证所有输入和输出：

| 验证项 | 规则 |
|--------|------|
| 团队配置 | agent 是否合法、是否有重复 |
| 任务规划 | 依赖是否存在、是否有循环、agent 是否在团队中 |
| 执行结果 | 交付物是否存在、内容非空、字数达标、必需章节、必需元素 |

## 重试机制

- 验证失败 → 通知 Agent 重试（最多 3 次）
- 调度失败 → 自动重试（最多 3 次）
- 超过重试次数 → 标记失败，通知 Main Agent

## 依赖

- team-ok/common/validator.py
- team-ok/project-data/scripts/project_data.py
- team-ok/task-queue/scripts/task_queue.py
- team-ok/task-dispatch/scripts/dispatch.py
- team-ok/task-complete/scripts/complete.py
- team-ok/agent-notify/scripts/notify_agent.py