# Workflow Loops — 条件循环编排 · 设计草案

> 版本：2026-06-11 · **RFC / 重大升级**  
> 状态：**草案**（未实现）  
> 关联：[DESIGN-AGENT-DELIVERY.md](./DESIGN-AGENT-DELIVERY.md) · [FRAMEWORK-FREEZE.md](./FRAMEWORK-FREEZE.md)

---

## 1. 背景与目标

### 1.1 问题

单兵交付的最小单元应为：

```text
Work → Gate → Review →（不通过则带 feedback 再 Work）→ … → 双过则完成
```

当前能力：

| 能力 | 位置 | 现状 |
|------|------|------|
| Gate 多轮 retry | `task_pipeline` | ✅ `max_gate_retries` |
| Review 一轮 | `task_pipeline.peer_review` | ⚠️ 仅 1 次，失败 → `needs_review` 停住 |
| 静态 DAG | `Process._dispatch` | ✅ 每 task 跑一次 |
| 循环 + 条件退出 | — | ❌ 无 |

用 **手写 N 轮 task**（`work-1 → review-1 → work-2 → …`）可近似，但：

- 无法「Review 通过即停」
- 步数爆炸、token 浪费
- 不可声明式维护

### 1.2 目标

在 **A 层 workflow** 声明 **loop + until**，由 **编排层（Process + workflow_loader）** 运行时调度：

- **不改** `task_pipeline` 内 Gate retry 语义（单轮内格式修正仍在内环）
- **不改** execute/review interaction 契约
- 支持 **Work–Review 多轮直到条件满足或达上限**
- 条件优先 **确定性**（Gate / 交付物标记 / run_event），少依赖 LLM 判「要不要继续」

### 1.3 与 FRAMEWORK-FREEZE 的关系

本升级 **显式解冻**：

- `backend/common/process.py` — `_dispatch` 循环状态机
- `backend/common/dag_dispatch.py` — ready/skip 语义
- `backend/common/workflow_loader.py` — schema 解析与校验

**不解冻**：`AgentPort`、`Gate` 核心规则、`submit_result` 契约。

---

## 2. 概念模型

```text
Project
  └── tasks[]           # 顶层静态 DAG（与 today 相同）
  └── loops[]           # 新增：具名循环块（可嵌入 DAG）

LoopInstance（运行时）
  ├── loop_id
  ├── round: 1..max_rounds
  ├── state: running | passed | exhausted | skipped
  └── body_tasks[]      # 每轮实例化的 task id
```

**顶层 DAG** 的节点可以是：

- 普通 `task`（与 today 相同）
- `loop_ref: <loop_id>` — 占位节点，调度时展开为 LoopInstance

Loop **body 内** task 每轮复制一份 id：`{loop_id}-r{round}-{body_id}`  
依赖在同一 round 内：`t-ch3-r2-review` 依赖 `t-ch3-r2-work`。

---

## 3. YAML Schema（v1 草案）

### 3.1 顶层结构

```yaml
id: 可信数据空间-产品规划完善
version: "2.0"
description: 带 Work–Review 循环的第三章完善

options:
  review_enabled: false          # loop 内自带 review 步时建议 false，避免双轨
  needs_review_blocks: true      # loop 未 passed 时阻塞下游

loops:
  - id: ch3_round
    description: 第三章 Work–Review 直到验收通过
    max_rounds: 5
    until:                         # 满足任一即退出（OR）；见 3.3
      - type: deliverable_marker
        task: review               # body 内相对 id
        marker: "REVIEW: PASS"
    on_pass: complete              # complete | continue_project
    on_exhaust: needs_review       # needs_review | failed | continue_project
    body:
      - id: work
        name: 第三章撰写/修订
        agent: product
        task_type: product-planning
        description: |
          【round】{round}/{max_rounds}
          【若 round>1】必读上一轮 review 交付物中的 FAIL 项并逐条修正
      - id: review
        name: 第三章审计
        agent: arch
        task_type: acceptance-report
        dependencies: [work]
        description: |
          通读 work 交付物；全文末尾须写 REVIEW: PASS 或 REVIEW: FAIL
          FAIL 时在表格中列须修正项

tasks:
  - id: t-gap
    agent: product
    task_type: product-research
    dependencies: []
    # ...

  - id: t-ch3
    loop: ch3_round              # 引用 loops[].id
    dependencies: [t-gap]

  - id: t-final
    agent: main
    task_type: decision-record
    dependencies: [t-ch3]
```

### 3.2 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `loops[].id` | ✅ | 循环块标识，task 用 `loop:` 引用 |
| `loops[].max_rounds` | ✅ | 上限，默认 5 |
| `loops[].body` | ✅ | 单轮内 task 模板（同 tasks 项结构，id 在块内唯一） |
| `loops[].until` | ✅ | 退出条件列表（见 3.3） |
| `loops[].on_pass` | | 条件满足时 loop 节点终态，默认 `complete` |
| `loops[].on_exhaust` | | 轮次耗尽仍未 until，默认 `needs_review` |
| `tasks[].loop` | | 引用 `loops[].id`；与 `agent`/`task_type` 互斥 |

**变量注入**（`instantiate_tasks` / 运行时 prompt）：

- `{round}` `{max_rounds}` `{loop_id}` 写入 body task 的 description

### 3.3 `until` 条件类型（v1）

| type | 参数 | 判定时机 | 确定性 |
|------|------|----------|--------|
| `deliverable_marker` | `task`, `marker` | body 内指定 task 的 deliverable 含 marker | ✅ |
| `gate_passed` | `task` | 指定 task Gate 通过且 status completed | ✅ |
| `review_passed` | `task` | 读 `run_event` `review_done.passed==true`（若启用 peer_review） | ✅ |
| `task_status` | `task`, `status` | store 中 task status 等于 | ✅ |
| `all_sections` | `task`, `sections[]` | Gate 等价检查 | ✅ |

**v2 预留**：`script`（`business/playbooks/scripts/check_until.sh`）、`expression`（禁止优先，易非确定）

**组合语义**：

- `until` 数组内：**OR**（任一满足即退出 loop）
- 未来可选 `until_all`：**AND**

### 3.4 与 `peer_review` 的关系

两种方式二选一（workflow 级约定）：

| 模式 | 配置 | 适用 |
|------|------|------|
| **A · loop body 显式 review task** | `review_enabled: false`，body 内 `acceptance-report` | 可读交付物、写 REVIEW: PASS/FAIL，**推荐** |
| **B · kernel peer_review** | `review_enabled: true` + body 仅 work | until 用 `review_passed`；每轮 work 后自动 review |

本草案 **默认模式 A**，与「任意 agent 审计」一致，且不依赖改 `task_pipeline`。

---

## 4. workflow_loader 改法

### 4.1 数据结构

```python
@dataclass
class LoopSpec:
    id: str
    max_rounds: int
    body: list[dict]
    until: list[dict]
    on_pass: str = "complete"
    on_exhaust: str = "needs_review"

@dataclass
class WorkflowProfile:
    ...
    loops: list[LoopSpec] = field(default_factory=list)
```

### 4.2 校验（`validate_workflow`）

1. `loops[].id` 唯一；`tasks[].loop` 引用存在
2. `loop` 与 `agent`/`task_type` 互斥
3. 展开 **max_rounds 轮** 做 **plan_gate** 虚拟校验（无环、agent 能力）
4. body 内 `dependencies` 仅引用同 body 内 id
5. `until[].task` 必须是 body 内 id

### 4.3 实例化

**不**在 loader 阶段完全展开为静态 tasks（否则无法动态 until）。

loader 输出：

- 普通 tasks → 照旧 `instantiate_tasks(goal=...)`
- loop 占位 task → 保留 `{id, loop: ch3_round, dependencies}` 供 Process 消费

---

## 5. Process 改法（核心）

### 5.1 调度状态机

在 `_dispatch` 中识别 loop 占位 task：

```python
@dataclass
class LoopRuntime:
    loop_id: str
    spec: LoopSpec
    round: int = 0
    state: str = "pending"  # pending|running|passed|exhausted
    round_outcomes: dict[int, dict[str, TaskOutcome]] = field(default_factory=dict)
```

**调度 loop 节点 `t-ch3` 时**：

```text
round += 1
实例化 body → ch3_round-r{round}-work, ch3_round-r{round}-review
按 body 内 DAG 顺序调度（可复用 wave 逻辑，scope=当前 round）
round 结束后 evaluate_until():
  满足 until → loop.state=passed, t-ch3 outcome=completed
  不满足且 round < max_rounds → 下一轮
  不满足且 round >= max_rounds → loop.state=exhausted, t-ch3 outcome=on_exhaust
```

**下游依赖 `t-ch3`**：仅当 loop 节点 outcome 为 `completed`（passed）时 ready；`needs_review`/`failed` 按 `needs_review_blocks` 阻塞。

### 5.2 Task id 与 deliverable 路径

```text
task_id:   {loop_ref}-r{round}-{body_id}     # 例 ch3_round-r2-review
deliverable: {task_id}_deliverable.md
```

与 today `artifact_rel_path` 兼容，**无需**改 `task_deliverable_base`（每 task 独立目录建议作为 follow-up）。

### 5.3 `evaluate_until` 实现

```python
def evaluate_until(until: list[dict], round_outcomes: dict, store, project_id) -> bool:
    for cond in until:
        if cond["type"] == "deliverable_marker":
            tid = resolve_task_id(cond["task"], round)
            path = deliverable_path(project_id, tid)
            if marker in read(path): return True
        elif cond["type"] == "review_passed":
            ...
    return False
```

优先读 **磁盘交付物** 与 **store run_event**，不调用 LLM。

### 5.4 跳过未执行轮次

round 2 通过 until 后，**不**调度 r3..rN；loop 节点记 `rounds_used=2`。

### 5.5 Store / 可观测

```text
run_event: {project_id}:loop:{loop_id}  type=loop_round_done  {round, passed: bool}
run_event: {project_id}:loop:{loop_id}  type=loop_finished     {state, rounds_used}
```

Hub 进度条：loop 节点显示 `round 2/5 · passed`。

---

## 6. dag_dispatch 改法

新增：

```python
def loop_node_ready(loop_runtime: LoopRuntime) -> bool: ...
def skip_remaining_rounds(loop_runtime: LoopRuntime) -> None: ...
```

`ready_tasks` 扩展：

- loop 占位 task 在 `loop_runtime.state==passed|exhausted` 时视为已有 outcome
- body task 不对全局 order 暴露，仅 loop 内部调度

---

## 7. 示例：可信数据空间第三章（v2 workflow）

见 `business/workflows/可信数据空间-产品规划完善.yaml` — 升级时增加 `loops` 段，将 `t-ch3` 改为 `loop: ch3_round`，删除手写 `t-accept` 或改为 loop 外最终 `decision-record`。

---

## 8. 迁移与兼容

| 项 | 策略 |
|----|------|
| 无 `loops` 的 workflow | **零变更**，行为与 today 一致 |
| 手写 N 轮 task | 继续可用；文档标记 deprecated |
| `review_enabled` + loop | validate 警告：建议二选一 |
| Hub workflow 编辑器 | Phase 2 支持 loops UI |

---

## 9. 测试计划

| 用例 | 断言 |
|------|------|
| until 第 1 轮 PASS | 只跑 r1，loop completed，下游启动 |
| until 第 3 轮 PASS | r1 r2 失败标记，r3 pass，rounds_used=3 |
| 耗尽 | max_rounds 后 on_exhaust=needs_review |
| body 内 Gate fail retry | 仍走 task_pipeline max_gate_retries，不消耗 round |
| plan_gate | loop body 非法 agent/task_type 加载失败 |
| 无 loops 旧 workflow | 回归 353+ tests |

---

## 10. 实施分期

| Phase | 内容 | 风险 |
|-------|------|------|
| **R-Loop-1** | schema + loader 校验 + 单元测试（不跑 Process） | 低 |
| **R-Loop-2** | Process loop 调度 + deliverable_marker until | 中 |
| **R-Loop-3** | Hub 展示 + 可信数据空间 workflow 迁移 | 中 |
| **R-Loop-4** | review_passed / script until | 低 |

**预估改动面**：`workflow_loader.py`、`process.py`、`dag_dispatch.py`、新 `loop_runtime.py`、测试 ~15 个；**不动** `task_pipeline.py`（Phase 1）。

---

## 11. 风险与未决问题

1. **token 预算**：多轮 loop 消耗需 `ProcessConfig` 级告警（已有 budget）
2. **并行**：loop body 内默认串行；body 多 task 无依赖可 wave
3. **session 延续**：同 round 内 work retry 沿用 today session_id；跨 round 是否续 session — 建议 **round 间新 session**，description 注入上轮 review 路径
4. **FRAMEWORK-FREEZE 文档**：合并后更新 §2.1「DAG 波次 + **条件 loop**」

---

## 12. 附录：until 与 Gate 分工

```text
单轮内：task_pipeline  Gate retry（格式/stub/过程产物）
轮次间：Process loop    until（业务 PASS/FAIL、review 结论）
项目间：workflow DAG  dependencies（上游 loop passed 才下游）
```

此三分法保持内核职责清晰。
