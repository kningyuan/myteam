---
name: continuous-executor
description: "持续任务引擎，管理持续性项目（SEO 优化、社区运营、开源维护等）的标准执行流程。使用场景：1) 启动持续项目，2) 自动调度循环任务，3) 评估效果并继承上下文，4) 根据调整建议动态更新策略。Agent 负责评估、规划、执行等具体决策和产出。"
metadata: '{"openclaw": {"emoji": "🔁", "always": true}}'
allowed-tools: "exec"
---

# Continuous Executor Skill

持续任务引擎，管理持续性项目的标准执行流程。

## 核心原则

- **流程由引擎控制**：固定状态机，100% 准确
- **Main Agent 是决策者**：提供团队配置、任务规划、阶段设计
- **Worker Agent 是执行者**：按模板评估、规划、执行、发布
- **验证是固定逻辑**：代码检查，非 LLM 判断
- **轮次继承**：每轮执行携带项目总结和上轮效果，持续积累

## 使用方式

> **已切换至单内核**：recurring 模式现由 `skill/team/common/run_kernel.py --mode recurring`
> 承载（与 one_shot 同一内核，差异仅模式配置）。旧 `scripts/engine.py` 仅作回退保留。

```bash
# 从 myteam 根目录 —— 启动/推进一个持续项目（每次调用驱动一轮）
python skill/team/common/run_kernel.py "<项目ID>" --mode recurring \
  --title "<项目名称>" --goal "<项目描述>"
```

### 示例

```bash
cd ~/myteam
python skill/team/common/run_kernel.py "ddd_geo_continuous" --mode recurring \
  --title "DDD-super 发电机持续 GEO 优化" \
  --goal "针对 DDD-super 发电机进行持续 GEO 优化：基线审计、内容/技术优化、效果跟踪，按周期迭代"
```

首轮会自动：建项目 → Main 配团队 → Main 设计阶段 → 跑第一轮 dispatch。之后靠 cron + `--trigger-now` 按 `interval_days` 迭代。

## 状态机流程

```
CRASH_RECOVERY → INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP
                                                                    ↓
                                              （周期结束，等待 cron / --trigger-now 下一轮）

--stop → COMPLETE（仅显式停止时）
```

**recurring 每轮内部**（DISPATCH_LOOP 内）：

```
[若有 pending_review] CYCLE_REVIEW（Deputy）→ CYCLE_PLAN（Main）→ dispatch → CYCLE_CLOSE
```

## 配置（config.yaml，可选）

不传 `--config` 时使用 `continuous-executor/scripts/config.yaml` 默认值。

| 键 | 说明 | 默认 |
|----|------|------|
| `cycle.interval_days` | 循环阶段默认间隔（天） | 7 |
| `cycle.max_empty_before_backoff` | 空轮次退避阈值 | 10 |
| `cycle.backoff_factor` | 退避倍数 | 2 |
| `cycle.max_sleep_sec` | 最大休眠秒数 | 86400 |

## 路径与通知

- 项目数据：`tasks/{project_id}/`（含 `continuous_data.json`）
- Agent workspace：`workspaces/workspace-{agent_id}/`
- Agent 通知：同 task-executor，经 `bridge/myteam_notify.py`
- Telegram 群通报：`notify-telegram`（需 `config/telegram.json`）

## 依赖（均在 skill/team/ 下）

- `task-executor/scripts/executor.py`（剔除 dispatch_loop 后的流程）
- `common/logger.py`, `common/config.py`, `common/task_data_store.py`
- `common/quality_gate.py`, `common/cross_review.py`
- `task-dispatch/scripts/dispatch.py`, `task-queue/scripts/task_queue.py`
- `project-init/scripts/init.py`, `project-data/scripts/project_data.py`
- `agent-notify/scripts/notify_agent.py`, `notify-telegram/scripts/notify.py`
- `task-cleanup/scripts/cleanup.py`
