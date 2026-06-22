# Agent 能力提升路径评审

> **背景**：用户梳理了 5 条 Agent 能力提升路径，每条对应明确的 gap。本文档给出逐条评估和推荐执行顺序。
> **相关**：[AGENT_CAPABILITY_UPGRADE_PLAN.md](./AGENT_CAPABILITY_UPGRADE_PLAN.md)、[AGENT_CAPABILITY_ITERATION_LOG.md](./AGENT_CAPABILITY_ITERATION_LOG.md)
> **日期**：2026-06-22

---

## 总览

| 路径 | 主题 | 评估 | 优先级 | 改动量 |
|------|------|------|--------|--------|
| A | Plan-then-Execute 强制解耦 | 认同 | P0 | 中 |
| B | Failure -> Lesson -> Behavior Change | 认同 | P0 | 小->中 |
| C | Agent 质量画像 | 部分认同 | P1 | 小 |
| D | 重试策略升级 | 认同 | P0 | 小 |
| E | 动态实验引擎 | 暂不认同 | P2 | 大 |

---

## 路径 A：Plan-then-Execute -- 认同，P0

### 问题
当前 execute 是一个步骤：既计划又写交付物。Agent 容易不假思索直接开写，质量不稳定。

### 方案
在 execute 前插入 plan 交互，让 Agent 先输出结构化计划 (approach/steps/risks)，通过确认后再执行。

```
当前：   execute -> 写交付物 -> Gate
建议：   plan -> Gate(计划合理性) -> execute(参照计划) -> Gate -> POST
```

### 评估
这是目前质量波动的核心原因之一。Agent 同时做计划和执行时，交付物往往「写到哪算哪」。插入 plan 步骤后，Gate 可以先卡住计划质量（比如调研计划是否覆盖了足够多的信息源），避免 Agent 带着错误假设直接产出。

### 关键设计约束
1. **plan 的 Gate 规则要轻** -- 只检查结构完整性（有步骤、有风险识别），不检查细节正确性。否则 token 消耗和延迟会显著增加。
2. **复用现有交互合同** -- `InteractionRequest/Response` 的 discriminated union 新增 `kind=plan`，不要新增一套协议。违反 FRAMEWORK-FREEZE 的风险在这里。
3. **Plan 交付物不写进 deliverables/** -- 只作为 Process 中间状态，避免污染项目产物。

### 风险
- Process 状态机需要插入新步骤，改动量可能比预估的大
- 需要确认 plan 步骤的 retry 策略（plan 被拒后，是直接重试还是走 triage？）

---

## 路径 B：Failure -> Lesson -> Behavior Change -- 认同，P0

### 问题
Gate 拒绝了不合格产出，Agent 重试时只拿到「上一轮问题列表」，没有结构化的「同样错误别再犯」引导。

### 方案
执行流完成后，POST 阶段自动从 ledger 提取 pitfalls+lesson，回写到 agent 的偏好/记忆，下次同类任务时以「你上次的教训」注入 prompt。

### 评估
I-10 的实测已经证明了这一点：`ledger -> KB` 蒸馏丢了 pitfalls，导致下次执行没有改进。这条路径和 I-03 的 ledger distill 是互补的 -- I-03 做了规则蒸馏，但没处理失败模式。

### 关键设计约束
1. **不要把 lesson 写死到 USER.md** -- 那是团队偏好，不该被单次失败污染。
2. **写入 agent_id + task_type 维度的经验缓存** -- 类似 `kb://sqlite/` 但带 tag 过滤。
3. **注入时机在 PRE 阶段** -- 格式要简洁（一行教训 + 一行反例），否则 prompt 太长会被 Agent 忽略。
4. **共享 `post/distill.py`** -- 和路径 D 可以一起做，减少重复改动。

---

## 路径 C：Agent 质量画像 -- 部分认同，P1

### 问题
没有跨项目的 agent 质量评级。一个 agent 连续交出低质量工作，框架不会降级或调低信任度。

### 方案
每次 Gate 通过/失败 + review 得分 -> 写入 agent 信誉表 -> team_config 做 agent 选择时参考。

### 评估
这个有价值，但要小心 **过早优化的陷阱**。当前阶段 Agent 数量少（developer、product、arch 等），质量差异主要来自 Skill 和 Prompt，而不是 Agent 自身「能力」。画像系统可能在 3-5 个 Agent 以上才有意义。

### 建议
**暂缓**，除非你能明确回答：画像数据会直接影响哪个决策？如果是影响 task 分配，那应该先做路径 A（plan 步骤），因为 plan 质量本身就是画像的一个维度。

---

## 路径 D：重试策略升级 -- 认同，P0

### 问题
当前的 Gate retry 反馈是固定的（章节缺失/格式错误），对 Agent 帮助有限。

### 方案
失败后在 retry_feedback 中加入根据失败模式分类的根因分析。

### 评估
这是投入产出比最高的。改动很小，主要涉及 `build_worker_prompt` 的 retry_feedback 段和 `execution_harness/post/distill.py` 的失败模式提取。

### 关键设计约束
1. **失败模式分类要有限** -- 建议 5 类以内：章节缺失、内容空洞、格式错误、超时中断、偏离计划。
2. **反馈要可操作** -- 不只是描述问题，要给出具体的修正方向（如「请在「关键发现」章节补充至少 3 条具体数据」）。
3. **和路径 B 共享 distill.py** -- 失败模式提取逻辑只需要写一次。

---

## 路径 E：动态实验引擎 -- 暂不认同，P2

### 问题
所有 agent 收到相同结构的 prompt，无法实验什么有效。

### 方案
按 task_type x agent_id 做 prompt 变体实验，记录哪个变体 Gate 通过率/retry 次数最优。

### 评估
在路径 A/B/D 都没有验证有效之前，引入实验框架是 **过度工程**。A/B 测试的前提是你已经有稳定的 baseline 和明确的优化目标。

### 建议
先把 A/B/D 落地，观察 Gate retry 率是否下降。如果下降了，再考虑「哪个 prompt 变体下降最多」-- 这时候实验框架才有意义。

---

## 推荐执行顺序

1. **D（重试策略升级）** -- 改动最小，立即见效
2. **B（经验回授闭环）** -- 和 D 共享 post/distill.py，可以一起做
3. **A（Plan-then-Execute）** -- 需要 Process 改动，但能从根本上改善交付质量
4. **C（质量画像）** -- 等 A 落地后，plan 质量可以作为画像的一个指标
5. **E（实验引擎）** -- 最后再做

### D+B 合并实施要点
- 共同改动文件：`execution_harness/post/distill.py`（失败模式提取 + lesson 蒸馏）
- 各自独立改动：
  - D：`build_worker_prompt` 的 retry_feedback 段
  - B：PRE 阶段的 lesson 注入逻辑（`execution_harness/pre/` 下新增模块）

### A 的实施要点
- 新增契约：`InteractionRequest.kind = plan`，`InteractionResponse` 含 approach/steps/risks
- Process 状态机插入 plan_step，plan 通过后才进入 execute_step
- templates.yaml 新增 plan 类型的 check_rules（轻量结构检查）

---

## 与现有迭代的衔接

| 现有迭代 | 与新路径的关系 |
|----------|----------------|
| I-03 ledger distill | 路径 B 的延续 -- I-03 做了规则蒸馏，路径 B 补充失败模式蒸馏 |
| I-04 preferences_on_execute | 路径 B 的注入通道 -- 已解耦，可直接用 |
| I-08 single_execute 实测 | 路径 A 的验证方式 -- 可以用 single_execute.py 跑 plan+execute 对比实验 |
| I-10 director_review | 路径 D 的失败模式来源 -- director_review 的结构化反馈可自动转为 retry_feedback |
| I-12 团队级偏好/KB | 路径 B 的经验缓存 -- 可复用 `__global__` 和项目级 KB 的注入机制 |

---

## 成功标准

| 路径 | 可验证指标 |
|------|-----------|
| D | 同一 task_type，retry 后 Gate 通过率提升 >= 20% |
| B | 同类任务第二次执行时，prompt 中出现「上次教训」且交付物质量提升 |
| A | 同一 task_type，用 plan 后用更少的 Gate retry 完成 |
| C | 暂缓 |
| E | 暂缓 |
