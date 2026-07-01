# execution_harness — Agent 任务执行质量层

Hermes 模式 · CLI 适配。与 Layer A（Process / Gate）隔离。

## 定位

提升 **单 Agent execute** 的质量：Skill 指针、Context 注入、有界 identity、任务后 review。

**不是** Workflow / Gate / 交卷校验。

## 目录

```text
execution_harness/
  facade.py           Layer A 唯一入口
  config.py           skill_config.json → execution_harness 段
  pre/                CLI 派发前（identity + prompt inject）
  post/               任务后（promote + skill_review + _pending/）
  skill/              task_type → umbrella skill、references/
  identity/           bounded USER.md / MEMORY.md
  backends/           KB / L1 / 偏好（复用 memstack adapter）
  injection/          prompt 块格式
```

## 配置

`config/skill_config.json` → `execution_harness`：

| 键 | 默认 | 说明 |
|----|------|------|
| `enabled` | true | 总开关 |
| `execute_harness_enabled` | true | PRE inject |
| `skill_review_enabled` | true | POST background review |
| `l1_on_execute` | true | execute 注入 L1 |
| `skills_write_approval` | true | review 写 `_pending/` 待审批 |

## Hook

| 时机 | 调用 |
|------|------|
| execute prompt | `prepare_execute_harness` + `inject_for_execute` |
| task 成功 | `on_task_complete`（promote + 异步 skill_review） |
| skill_review prompt | `kind=skill_review` in `build_worker_prompt` |

## 与 memstack

- **execution_harness**：执行质量编排（主路径）
- **memstack**：KB / L1 / 偏好 **存储 adapter**；`memstack.facade` 的 execute 钩子委托到 harness

##  smoke

```bash
cd myteam && .venv/bin/python backend/execution_harness/smoke.py
```

## 单 Agent 任务（无 Workflow）

```bash
cd myteam
PYTHONPATH=backend python backend/execution_harness/single_execute.py prepare \
  --project sa-q1 --task t1 --agent product --task-type research \
  --intent "你的任务意图"

# Agent 编辑 deliverables + ledger 后：
PYTHONPATH=backend python backend/execution_harness/single_execute.py finish \
  --project sa-q1 --task t1 --agent product --task-type research
```

产物：`business/tasks/single_agent/<project>/<task>/worker.prompt.txt`、全局 KB 复利、
`business/skills/<umbrella>/references/`。

## 文档

[docs/AGENT_EXECUTION_HARNESS_UPGRADE.md](../../docs/AGENT_EXECUTION_HARNESS_UPGRADE.md) ·
[docs/AGENT_CAPABILITY_ITERATION_LOG.md](../../docs/AGENT_CAPABILITY_ITERATION_LOG.md)
