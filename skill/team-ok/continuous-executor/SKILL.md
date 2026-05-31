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

与 `task-executor` 一样：**一条命令启动**，引擎走固定状态机；具体怎么优化、怎么量效果，由 Main 规划阶段/任务、Worker 按模板执行（能力可后续丰富）。

```bash
# 启动持续项目（与 task-executor 相同：项目名 + 可选描述）
~/.openclaw/skills/team-ok/continuous-executor/scripts/engine.py \
  "<项目名称>" "<项目描述>"

# 触发下一轮（cron 或手动）
~/.openclaw/skills/team-ok/continuous-executor/scripts/engine.py \
  --project-id <项目ID> --trigger-now

# 查看状态
~/.openclaw/skills/team-ok/continuous-executor/scripts/engine.py \
  --project-id <项目ID> --status

# 停止（仅此路径会进入 COMPLETE）
~/.openclaw/skills/team-ok/continuous-executor/scripts/engine.py \
  --project-id <项目ID> --stop
```

### 示例

```bash
# 针对 DDD-super 发电机持续 GEO 优化
~/.openclaw/skills/team-ok/continuous-executor/scripts/engine.py \
  "DDD-super 发电机持续 GEO 优化" \
  "针对 DDD-super 发电机进行持续 GEO 优化：基线审计、内容/技术优化、效果跟踪，按周期迭代"
```

首轮会自动：建项目 → Main 配团队 → Main 设计阶段（one_time 准备 + recurring 循环）→ 跑第一轮 dispatch。之后靠 **cron + `--trigger-now`** 按 `interval_days` 反复「优化 → 跟踪 → 再优化」。

## 状态机流程

```
CRASH_RECOVERY → INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP
                                                                    ↓
                                              （周期结束，等待 cron / --trigger-now 下一轮）

--stop → COMPLETE（仅显式停止时）
```

周期触发（`--trigger-now` 或 cron）只跑 `CRASH_RECOVERY → DISPATCH_LOOP`，**不会**在每轮结束后把项目标为 stopped。

**recurring 每轮内部**（DISPATCH_LOOP 内）：

```
[若有 pending_review] CYCLE_REVIEW（Deputy）→ CYCLE_PLAN（Main）→ dispatch → CYCLE_CLOSE（pending_review）
```

- 第 1 轮 recurring：Main 直接 cycle_plan（无 last_review）
- 第 2 轮起：必须先有 Deputy 的 `last_review`，Main 才能 cycle_plan
- 轮末不写 `effectiveness`；例行运维任务分配给 **ops**；领域 skill 用各 agent 工作区路径（`required_skills`）

### 各状态说明

| 状态 | 引擎行为 | Agent 行为 |
|------|---------|-----------|
| **CRASH_RECOVERY** | 检测 PID 锁；若另一实例仍在运行则**拒绝启动**（fail-closed） | - |
| **INIT** | 调用 project-init 创建项目 | - |
| **TEAM_CONFIG** | 通知 Main 配置团队，验证结果 | Main 返回 agent 列表 |
| **TASK_PLAN** | 通知 Main 规划阶段和任务模板，含循环策略 | Main 返回阶段列表（一次性/循环）和任务模板 |
| **ADD_TASKS** | 将阶段和任务模板写入项目 | - |
| **DISPATCH_LOOP** | 检查周期到期 → 生成本轮实例 → 调度执行 → **质量门禁 + 交叉审核** → 收集调整建议 → 更新项目总结 → 退出 | Worker 按模板执行 |
| **COMPLETE** | 仅 `--stop` 时：更新项目状态为 stopped，发送通知 | - |

## 配置（config.yaml，可选）

**一般不用管。** 文档里的 `/path/to/config.yaml` 只是占位符，表示「若你要自定义再传 `--config`」。

不传 `--config` 时，引擎自动使用同目录下的 `scripts/config.yaml`（主要是循环间隔、退避等调度参数，**不包含** GEO 具体怎么做——那由 Main 的 task_plan 决定）。

可通过 `--config` 指定自定义 YAML；未指定时使用 `scripts/config.yaml` 默认值。

| 键 | 说明 | 默认 |
|----|------|------|
| `cycle.interval_days` | 循环阶段默认间隔（天） | 7 |
| `cycle.max_empty_before_backoff` | 空轮次退避阈值 | 10 |
| `cycle.backoff_factor` | 退避倍数 | 2 |
| `cycle.max_sleep_sec` | 最大休眠秒数 | 86400 |

## 阶段类型

| 类型 | 说明 |
|------|------|
| **one_time** | 一次性阶段，所有任务完成后标记 completed |
| **recurring** | 循环阶段，按 interval_days 间隔反复触发，永不自动完成 |

## 依赖

- team-ok/task-executor/scripts/executor.py（剔除 dispatch_loop 后的流程）
- team-ok/common/logger.py
- team-ok/common/config.py
- team-ok/common/task_data_store.py
- team-ok/common/quality_gate.py
- team-ok/common/cross_review.py
- team-ok/task-dispatch/scripts/dispatch.py
- team-ok/task-queue/scripts/task_queue.py
- team-ok/project-init/scripts/init.py
- team-ok/project-data/scripts/project_data.py
- team-ok/agent-notify/scripts/notify_agent.py
- team-ok/notify-telegram/scripts/notify.py
- team-ok/task-cleanup/scripts/cleanup.py