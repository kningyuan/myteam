# MetaGPT 对比分析与借鉴建议

> 分析日期：2026-06-06
> 背景：MetaGPT 是最早开源的 LLM 多智能体框架之一（2023），采用「Team + Environment + Role」的进程内协作模式。myteam 采用「Process DAG + 外部 CLI Agent + Gate 确定性校验」的生产级架构。本文从架构设计角度做横向对比，提取可借鉴的思路。

---

## 一、架构模式总览

```
MetaGPT（进程内 · 轮次驱动）
  Team → Environment（消息总线）
         ├── Role A: _observe → _think → _act
         ├── Role B: _observe → _think → _act
         └── ...
         每轮 asyncio.gather 并行执行全体非空闲 Role

myteam（进程外 · DAG 驱动）
  Process → PlanExpander（拆 DAG）
          → TaskPipeline / DecisionPipeline
             → AgentPort → agent_transport → CLI subprocess
             → Gate（确定性校验）
          → 下一节点 / Triage / 完成
```

## 二、关键维度对比

### 2.1 编排模型

| | MetaGPT | myteam |
|---|---|---|
| 调度单位 | 轮次（round），每轮全部角色各跑一次 | DAG 节点，按依赖拓扑串行推进 |
| 完成语义 | 轮次耗尽或无角色活跃 | 全节点 `completed` 或不可恢复 `failed` |
| 确定性 | 低，角色自行决定反馈什么 | 高，Gate 同源校验（生成时用的 spec = 校验时用的 spec） |
| 并发粒度 | 角色级别并行 | 任务级别串行（D12 设计决策），Process 不处理并行冲突 |

MetaGPT 的轮次模型适合**开放探索**（场景不限量、质量不敏感），myteam 的 DAG 模型适合**有明确交付标准的任务**。

### 2.2 Agent 形态

| | MetaGPT | myteam |
|---|---|---|
| Agent 位置 | 进程内 Python 对象 | 外部 CLI 子进程 |
| 通信 | 直接方法调用 + 内存消息队列 | 文件交换（.trigger / .response）+ 轮询 |
| 隔离性 | 无——Agent 崩溃 = 框架崩溃 | 高——子进程崩溃，内核存活，可重试 |
| 扩展性 | 须安装 Python SDK、import 硬编码 | 任意 CLI（opencode / claude），适配器模式 |
| 内部状态 | `_observe → _think → _act` 结构化循环 | 纯提示词驱动，框架不介入黑盒 |

### 2.3 消息与通信

| | MetaGPT | myteam |
|---|---|---|
| 通信模式 | pub/sub 消息总线 | 一对一 Interaction 契约 |
| 路由机制 | 地址标签（`member_addrs`），支持点对点与广播 | DAG `dependencies` 显示指定上下游 |
| 消息结构 | Message（content + 路由标签 + cause_by） | InteractionRequest / Response（kind 辨识联合） |
| 协议约束 | 无，角色自行解析 | Pydantic 模型校验，不合规拒绝 |

MetaGPT 的地址路由对**自由协作**更灵活（brainstorm、多轮互评），myteam 的契约模式对**生产交付**更可靠。

### 2.4 校验与容错

| | MetaGPT | myteam |
|---|---|---|
| 输出校验 | 几乎无，`repair_llm_raw_output` 模糊修补 | Gate：格式 + 完整性 + 同源校验（D14） |
| 失败语义 | `NoMoneyException` → 项目终止 | 三级：重试 → failed → triage（D18） |
| 自动恢复 | 无，进程重启后从 JSON 反序列化恢复 Team | SQLite 持久终态，可断点续跑 |
| 质量评估 | 无内建机制 | Quality 自评（score 0..1 + known_gaps）+ review |

myteam 的校验和容错设计是 MetaGPT 的最大短板，也是借鉴价值**最低**的方向——这是架构级差异，不宜照搬。

### 2.5 持久化

| | MetaGPT | myteam |
|---|---|---|
| 存储方式 | 全量 JSON 序列化到 `storage/` | SQLite 增量持久化 |
| 恢复粒度 | 整个 Team 反序列化 | 按任务/项目精确恢复 |
| 一致性 | 弱，JSON dump 非事务 | ACID 事务保障 |

### 2.6 可观测性

| | MetaGPT | myteam |
|---|---|---|
| 日志 | Python logger | audit_log（结构化记录 + `compact` mode） |
| 外部观察 | 不暴露运行状态 | 同 DB 只读 obs API + run_event SSE |
| 计量 | cost_manager 仅跟踪 token 费用 | BudgetConfig + check_budget + 分任务 token 记账 |

---

## 三、值得借鉴的三个方向

### 3.1 方向 A：消息总线辅助 DAG

**MetaGPT 的做法**：`Environment` 作为全局消息总线，Role 注册后可以 pub/sub 消息。地址路由支持点对点、组播、广播，新角色加入不影响已有路由。

**myteam 现状**：任务间通信全部走 DAG `dependencies`。灵活但有约束：
- DAG 依赖是静态的，执行中不能动态建立通信链路
- 多轮评审/讨论场景需要多条 interaction 串行，Message 传递隐含在任务链中

**借鉴思路**：在 DAG 主流程旁增加可选的消息总线层——不再是全局 pub/sub，而是作用域在**当前项目**内，任务可以向总线发消息，其他任务按 `agent_id` 或 `topic` 订阅。`agent_chat` 已有类似能力但目前仅限 Hub 侧，不与 Process 打通。

**改动范围**：新增 `common/message_bus.py`，DAG 节点可声明 `subscribes: [topic]`，总线消息在 Store 中持久化。Process 在执行节点前将相关消息注入 prompt。不影响现有 DAG 语义。

**风险**：消息总线让控制流更难推导，必须限定为「辅助通道」而非「执行路径」。DAG 仍为主干。

### 3.2 方向 B：Interaction 内部结构化阶段

**MetaGPT 的做法**：Role 内部有 `_observe → _think → _act` 三个阶段，每个阶段有明确的输入/输出，子类可通过重写定制行为。

**myteam 现状**：Agent 是黑盒，`build_worker_prompt` 拼一次提示词，Agent 输出一个 result。内部如何组织完全取决于 CLI/AI 模型。

**借鉴思路**：不需要改框架，在 `build_worker_prompt` 中对复杂 kind（`execute` / `review`）加入结构化阶段提示，引导 Agent 在**一次 interaction 内部**完成：
1. **收集**：整理上游交付物、项目上下文
2. **产出**：完成主任务输出
3. **自检**：对照品质标准自评（Score + known_gaps）

这些不是三次 interaction，而是通过提示词结构让 Agent 在单次输出中走完三个心智阶段。效果取决于 prompt 设计，不增加流程复杂度。

**改动范围**：只改 `agent_transport.py` 的 `build_worker_prompt` 函数。

### 3.3 方向 C：递归任务展开

**MetaGPT 的做法**：`Planner` 将目标递归分解为 `Task` 树，每个 Task 关联到具体 Action，执行中可按需再展开。

**myteam 现状**：`PlanExpander` + `plan_gate.py` 已有 plan/expand/gate 链路，但展开是在**执行前**完成的——DAG 一次性展开到叶子节点，不支持「执行中发现某任务太大，就地展开为子图」。

**借鉴思路**：`PlanExpander.expand_sub_tasks` 已经支持在 execute 阶段动态展开。可以进一步增强：当 Gate 判定 `needs_review` 且任务内容跨度过宽时，允许 PlanExpander 将其原地替换为多个子任务（作为新的 DAG 子图），而不是走 triage 回 Main。减少一次决策 round-trip。

**改动范围**：`TaskPipeline` 中增加 `on_needs_review` 分支，判断是「质量不够好」（触发重试）还是「范围太大」（触发递归展开）。`PlanExpander` 增加 `expand_at_runtime(parent_task_id, sub_tasks)`，替换 Store 中对应节点。

**风险**：运行时展开 DAG 增加了状态复杂度，必须确保 Gate 在新子图也执行校验。需要严格的展开深度上限防止栈溢出。

---

## 四、不应借鉴的方向

| 方向 | 理由 |
|------|------|
| 进程内 Agent（Role Python 对象） | 破坏隔离性，Agent 崩溃=框架崩溃，且绑定 Python LLM SDK，失去 CLI 无关性 |
| JSON 输出修补/抢救 | myteam D1/F1 已明确拒绝，模糊修补掩盖 prompt 问题 |
| 轮次（round）驱动 | 不适合生产级任务，没有完成语义；DAG 是更可预测的模型 |
| 全量 JSON 序列化 | 无事务保障，大项目不可恢复；myteam 的 SQLite + 增量持久化更可靠 |
| `NoMoneyException` 式容错 | 生产环境需要分级容错（retry → failed → triage），非二元破产 |

---

## 五、结论与建议优先级

| 优先级 | 方向 | 收益 | 改动量 | 建议 |
|--------|------|------|--------|------|
| P0 | 方向 B（Interaction 内部结构化） | 提升单次交付质量 | 极少（改 prompt 模板） | **立即试点**，在 execute 和 review 两 kind 上实验 |
| P1 | 方向 C（递归任务展开） | 减少 DAG 展开轮次，减少决策 round-trip | 中等（TaskPipeline + PlanExpander 改动） | 验证时间窗口，确定使用频率后决定 |
| P2 | 方向 A（消息总线） | 提升多轮协作灵活性 | 较大（新增模块 + DAG 改造） | 先评估 `agent_chat` 现有能力的复用可能性再做 |