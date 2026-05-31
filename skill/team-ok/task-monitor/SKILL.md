---
name: task-monitor
description: "任务监控。使用场景：1) 检查任务队列状态，2) 监控 Agent 存活情况，3) 检测卡住的任务，4) 生成项目健康报告。实时监控项目执行状态。"
metadata: '{"openclaw": {"emoji": "📊", "always": true}}'
allowed-tools: "exec"
---

# Task Monitor Skill

实时监控任务队列和 Agent 状态。

## 与「定时监控 Agent」编排的关系（原设计 vs 现能力）

- **原设计（编排层）**：由 **Main 或专职监控 Agent** 按 **cron / heartbeat** 定期 `exec` 本 skill 的脚本（如 `health`、`status`），根据 JSON / 退出码决定：调用 **`task-resume`**、补 **`dispatch`**、或升级为人工作业。  
- **本 skill 自身**：提供 **可调用脚本与参数契约**，**不包含**长期驻留的定时循环；是否「定期」完全由 **OpenCode / 外部调度器** 实现。  
- **加固后的变化**：在既有启发式检测之外，强化了 **`validate-graph` / `health.graph_validation`**（与 **`project-data check-cycle`** 同源）——**整图合法性**为硬信号；其它 `issues` 仍为**线索**。  
- **`health` 输出（round11+）**：根字段 **`paths`** 给出 **`project_dir`、`task_data_json`、`skill_logs`** 绝对路径，便于监控 Agent **稳定读取 `skills.log`**，无需推断目录。

## 使用方式

```
skill: task-monitor
action: status
project_id: "pro_xxx"
```

## 动作类型

### status
检查所有项目任务状态。

```
skill: task-monitor
action: status
```

返回所有项目的任务执行状态概览。

### check
检查特定项目任务状态。

```
skill: task-monitor
action: check
project_id: "pro_xxx"
```

返回指定项目的详细状态信息。

### health
生成项目健康报告。

```
skill: task-monitor
action: health
project_id: "pro_xxx"
```

JSON 中始终包含 **`graph_validation`**（委托 `project-data check-cycle`）：`ok: false` 时 **`healthy` 为 false**，与启发式子检测并列，便于 LLM 优先处理**形式化图错误**。**`health` 不再单独输出与整图环重复的启发式「circular」告警**（与 **`graph_invalid_count` / `graph_validation`** 同源，避免同一问题双报）。

### alert
设置监控告警。

```
skill: task-monitor
action: alert
project_id: "pro_xxx"
threshold: 3600
```

当任务执行超过阈值时间时发送告警。

## 脚本

- `{baseDir}/scripts/task_monitor.py status` - 检查所有项目
- `{baseDir}/scripts/task_monitor.py check <project_id>` - 检查特定项目
- `{baseDir}/scripts/task_monitor.py health <project_id>` - 健康报告
- `{baseDir}/scripts/task_monitor.py validate-graph <project_id>` - **硬性图校验**（委托 `project-data check-cycle`，与 confirm/add 后校验同源；失败时 **非 0 退出**）
- `{baseDir}/scripts/task_monitor.py alert <project_id> <threshold>` - 设置告警

## 降低 LLM 不确定性的用法（推荐）

1. **派发 / 改依赖 / 人工改 `task_data.json` 之后**：先跑 **`validate-graph`**，再让 LLM 继续编排或 dispatch。
2. **健康检查 `health`** 仍含大量基于 **日志启发式** 的推断（如僵尸任务、通知缺失），结论应作为**线索**；**图是否合法**以 **`validate-graph` / `project-data check-cycle`** 为准。根字段 **`paths`**（`skill_logs` 等）仅用于**定位文件**，不包含内容真伪判断。

## 监控指标

- 任务执行时间
- Agent 响应延迟
- 队列等待任务数
- 错误率和重试次数
