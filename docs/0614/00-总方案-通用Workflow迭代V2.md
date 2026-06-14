# 通用 Workflow 迭代 v2 — 总方案

> **版本**：2026-06-14  
> **状态**：已批准执行（方案包 `docs/0614`）  
> **Owner**：平台 / 编排内核  
> **读者**：产品、架构、后端、前端、QA、运维

---

## 1. 背景与目标

### 1.1 业务诉求

myteam 需要 **通用的 workflow 编排能力**，用同一套内核协议覆盖大部分现实场景（产品规划、GEO、媒体运营、系统升级、缺陷闭环等）。**场景差异只体现在配置**（`business/workflows/*.yaml`、交付模板、Skill、Hook），不为每个场景改 `process.py`。

用户期望的迭代模型：

1. **Workflow 声明迭代壳** — 允许/强制进入下一轮（`max_rounds` / `min_rounds`），不必硬绑定「读完上一轮 deliverable 才能继续」。
2. **可配置 assess 步** — 任意 work agent 按场景声明的输入评估当前情况（有效 / 无效 / 无法判断）。
3. **Agent 写结论、内核解析** — 继续 / 停止 / 换分支；**不在 Process 内调用 LLM 做调度决策**。
4. **每轮 task 组可以不同** — 通过 `bodies` 分支 + `transition.next_body`，而非每轮复制同一 body 模板。

### 1.2 与现状差距

| 能力 | 现状 | 差距 |
|------|------|------|
| R-Loop v1 | `loops[]` + 固定 `body` + `until` OR | 无多 body 分支；assess 非一等公民 |
| Recurring | `mode=recurring` + `task_plan` + `prior_summary` | 整图重规划，非 loop 内 assess/branch |
| v2 UI | 已恢复 loop 编辑 + recurring `max_cycles` | 缺 assess/transition/bodies 编辑与运行监控 |
| 采用面 | 仅 `产品规划方案.yaml` 使用 loops | GEO/媒体等多为静态 DAG |

### 1.3 North Star

```text
Kernel（确定性调度）
  iteration shell → pick body(branch) → run phases → assess → transition
       ↑
Business（场景配置）
  bodies / assess / transition / templates / hooks
```

**原则**：内核只懂 DAG、轮次、marker 解析、run_event；业务语义不进 `loop_runtime` 核心逻辑。

---

## 2. 通用原语目录

| 原语 | YAML / 参数 | 用户可见行为 |
|------|-------------|--------------|
| **静态 DAG** | `tasks[]` | 一次性流水线 |
| **Iteration 壳** | `loops[]` / `tasks[].loop` | DAG 占位节点，多轮执行 |
| **Bodies** | `loops[].bodies{key}` | 命名 task 组；每轮可切换 |
| **Assess** | `loops[].assess` | 评估步：agent + inputs + 交付 marker |
| **Transition** | `loops[].transition[]` | stop / continue + `next_body` |
| **Fallback until** | `loops[].until` 或 `fallback_until` | v1 兼容；agent 无 marker 时兜底 |
| **Recurring** | 启动 `mode=recurring`, `max_cycles` | 跨 tick 整 workflow 再跑 |
| **Loop discussion** | `loop_discussion_profile` | FAIL 后群对齐 + PATCH（可选） |
| **Gate retry** | `max_gate_retries` | 单 task 内格式修正（非 iteration round） |

**Recurring 与 Iteration 正交**：前者项目级周期；后者单 loop 占位节点内轮次。UI 文案严格区分「周期」与「轮次」。

---

## 3. YAML Schema（LoopSpec v2）

### 3.1 兼容策略

- **保留** `loops[]` 字段名（Hub / v2 编辑器已用）。
- v1：`body` + `until` 必填 → 行为 **100% 不变**。
- v2：定义 `bodies` + `assess` + `transition`；与 `body` **互斥**。

### 3.2 v2 结构示例

```yaml
loops:
  - id: wave
    description: 通用迭代示例
    max_rounds: 5
    min_rounds: 1                    # P1
    default_body: default
    on_pass: complete
    on_exhaust: needs_review

    bodies:
      default:
        - id: work
          agent: product
          task_type: product-planning
          dependencies: []
        - id: assess
          agent: main
          task_type: iteration-assess
          dependencies: [work]
      patch:
        - id: work
          agent: product
          task_type: product-planning
          dependencies: []
        - id: assess
          agent: main
          task_type: iteration-assess
          dependencies: [work]

    assess:
      ref: assess                      # body 内相对 id
      inputs:                          # P1 声明式注入（内核只解析 kind）
        - kind: goal
        - kind: phase.deliverable
          phase: work
        - kind: ops_log
          table: publish_log
          optional: true

    transition:                        # 有序匹配，先匹配先赢
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: PASS"
        action: exit
        outcome: complete
      - when: deliverable_marker
        task: assess
        marker: "REVIEW: PASS"          # v1 兼容别名
        action: exit
        outcome: complete
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: CONTINUE"
        action: continue
        next_body: patch
      - when: deliverable_marker
        task: assess
        marker: "REVIEW: FAIL"
        action: continue
        next_body: patch
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: BRANCH patch"
        action: continue
        next_body: patch
      - when: exhausted
        action: exit
        outcome: needs_review

tasks:
  - id: t-wave
    loop: wave
    dependencies: [t-prep]
```

### 3.3 控制协议（全场景通用）

Assess 交付物末尾须含 **单行 marker**（Gate 校验存在性，内核解析语义）：

| Marker | 含义 | 内核动作 |
|--------|------|----------|
| `ITERATION: PASS` / `REVIEW: PASS` | 迭代成功 | `exit` + `on_pass` |
| `ITERATION: STOP` | 显式停止 | `exit` |
| `ITERATION: CONTINUE` / `REVIEW: FAIL` | 继续 | `continue`（可选 `next_body`） |
| `ITERATION: BRANCH <key>` | 换 body | `continue` + `bodies.<key>` |

**禁止**：内核根据自然语言「结论」段做 LLM 推理。Hook（P3）仅可返回预声明 `transition_id`，**禁止**返回 `tasks[]`。

### 3.4 新 task_type：`iteration-assess`

- 注册于 `business/templates/templates.yaml`
- 必填节：评估对象、评估结论、发现摘要、下一步建议
- 结论节末行：上述 marker 之一
- 场景可继续用 `section-review` + `REVIEW: PASS/FAIL`（transition 规则声明即可）

---

## 4. 架构决策（已拍板）

| ADR | 决策 |
|-----|------|
| ADR-001 | Marker 协议为主；JSON assess 结果仅作窄口扩展 |
| ADR-002 | 分支以 YAML `bodies` + `next_body` 为主；禁止 loop 内 full `task_plan` |
| ADR-003 | Assess = body 内一步或 `assess.ref` 指向 body 任务 |
| ADR-004 | `loop_discussion` 仍在 assess 之后、transition 之前；与 `assess.ref` 解耦 hardcoded `work`/`review` |
| ADR-005 | 状态机下沉 `loop_runtime.run_loop()`；`process._execute_loop` 薄委托（**须 Freeze Owner 批准**） |
| ADR-006 | Resume 靠确定性 task id + `run_event` 重建 `LoopRoundState` |

---

## 5. 分层职责

| 层 | 路径 | 职责 |
|----|------|------|
| Kernel | `loop_runtime.py`, `process._execute_loop` | 轮次、body 选择、transition、事件 |
| Loader | `workflow_loader.py`, `workflow_validate.py` | 解析 / 校验 / plan_gate 展开 |
| Business | `business/workflows/`, `templates/`, `hooks/` | 场景 YAML、assess 模板、marker 文案 |
| Hub | `observability.py`, `project_launch.py` | overview / SSE / launch `max_cycles` |
| frontend-v2 | `IterationEditorPanel`, `ProjectDetailPanel` | 编辑 + 运行监控 |

---

## 6. 分阶段实施

### P0 — Schema + 可观测 + 模板（2 周，无运行时行为变化）

**Backend**

- `LoopSpec` 扩展字段；`parse_loop_specs` 归一化 v1→内部表示
- `validate_loop_specs` 校验 `bodies` / `transition` 引用
- Hub：`loop_round_done` / `loop_finished` 进 `_FEED_KINDS`；overview 增加 `iterations[]`
- 文档：更新 `DESIGN-WORKFLOW-LOOPS.md` 状态

**Business**

- 新增 `iteration-assess` 模板
- 示例 workflow：`business/workflows/_examples/iteration-v2-fixture.yaml`

**Frontend**（已完成部分 v2 loop/recurring；P0 增量）

- `IterationProgressCard`；Exec 树展示 loop 事件
- dirty / description 缓存（对齐 v1）

**验收**

- 全量 `pytest backend` 绿
- v1 `产品规划方案.yaml` 加载与行为不变
- `reg_discuss_loop.py` CHECK_ONLY 绿

---

### P1 — Assess + Transition 运行时（2 周）

**Backend**

- `evaluate_transition()`；`resolve_assess_task_id()`
- `_execute_loop` 状态机：`LoopRoundState`（round, body_key, next_body_key）
- 事件：`loop_round_assess`、`loop_transition`
- `loop_discussion_dispatch` 支持 `assess_task_id`

**Business**

- `产品规划方案.yaml` v2 等价迁移（`bodies` 显式化，行为不变）

**Frontend**

- `AssessStepEditor`；transition 基础 UI（stop/continue markers）

**验收**

- `test_process_loops.py` v1 三用例仍绿
- 新增：assess STOP 首轮 exit；CONTINUE 多轮
- `reg_iteration_assess.py` CHECK_ONLY

---

### P2 — Bodies 分支 + 试点（2 周）

**Backend**

- `instantiate_round_body_tasks(spec, round, body_key=)`
- `branch_selected` 事件；`expand_loop_body_for_validation` 展开所有 branch × rounds

**Business**

- 新建 `GEO持续优化-迭代.yaml`（audit→revise→verify + branch）
- 可选：`bugfix-loop` 三分支示例

**Frontend**

- `BodyTemplateManager` + `TransitionEditor` + DAG 轮次分组

**验收**

- r1 FAIL→patch body；r2 PASS→completed
- `reg_geo_iteration.py` CHECK_ONLY

---

### P3 — Hook 窄口（可选）

- `assess.kind: hook` → `business/hooks/*.assess_loop_round()` 返回 `{passed, transition_id}`
- **禁止** 返回 `tasks[]`

---

## 7. 试点 Workflow

| 试点 | 文件 | 目的 | 阶段 |
|------|------|------|------|
| **A** | `产品规划方案.yaml` | v1→v2 等价迁移 + REG-DISCUSS | P1 |
| **B** | `GEO持续优化-迭代.yaml` | 证明多 body 分支通用性 | P2 |

---

## 8. 测试与 REG 矩阵

| 脚本 / 套件 | 阶段 | 说明 |
|-------------|------|------|
| `pytest backend/common/tests/test_loop_runtime.py` | P0+ | 解析、transition 单测 |
| `pytest backend/common/tests/test_process_loops.py` | P1+ | 集成 |
| `reg_discuss_loop.py` | P1 | 产品规划 discuss 回归 |
| `reg_iteration_assess.py` | P1 | 新增；fixture workflow |
| `reg_geo_iteration.py` | P2 | 新增；GEO 分支 |
| `run_regression.sh --suite unit` | 每 PR | 全量单元 |
| LIVE 试跑 | P1 末 / P2 | 见 `04-真实环境验证方案.md` |

---

## 9. 真实环境验证 KPI（概要）

| KPI | 标准 |
|-----|------|
| Pilot A | 3 轮内 `REVIEW: PASS`；群讨论 FAIL 路径仍可 PATCH |
| Pilot B | 至少 1 次 `branch_selected`；最终 placeholder `completed` |
| Hub v2 | ProjectDetail 可见 round/body/assess marker |
| Token | 单 loop 不超过项目 budget 80% 告警 |
| 7-day recurring | 与 iteration 独立；不回归破坏 |

详细步骤见 subagent 产出 `04-真实环境验证方案.md`。

---

## 10. 风险与反目标

**风险**

- 非确定性 assess → 仅允许 marker 协议 + 日志
- `process.py` diff → 委托 `run_loop()` 最小化
- frontend/schema 漂移 → Hub validate 为唯一真源

**反目标**

- loop 内 LLM `task_plan` 重规划 DAG
- 合并 recurring 与 iteration 概念
- 内核写业务 agent 名 / 中文节名
- 运行时改 YAML

---

## 11. PR 拆分（Backend）

| PR | 内容 | 约 LOC |
|----|------|--------|
| PR1 | Schema + parse + validate | ~285 |
| PR2 | `iteration-assess` + `evaluate_transition` | ~225 |
| PR3 | `_execute_loop` v2 + events + tests + reg | ~360 |
| PR4 | 试点 YAML + 文档 | yaml |

---

## 12. 开放问题（实施中关闭）

1. `min_rounds` 与 assess 首轮 STOP 冲突时 → **强制 continue 至 min_rounds**（P1 实现）
2. Branch 完成后占位节点 → **auto-complete**，meta `loop_state=branched`（P2）
3. Recurring 项目内嵌 iteration → P2 支持，P0 不测

---

## 13. 子方案文档

本总方案由以下 subagent 基于具体可执行细节扩写：

- `01-架构实施方案.md`
- `02-研发实施方案.md`
- `03-测试与回归方案.md`
- `04-真实环境验证方案.md`

---

*本文档为 `docs/0614` 方案包主真源；实施过程中变更须回写本节并 bump 版本号。*
