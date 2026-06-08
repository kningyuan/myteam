# 交付评审方案：对话并发 / DAG·时间线 / Token 计量

> **版本**：v1.1（评审修订）  
> **日期**：2026-06-08  
> **状态**：修改后通过 — 待 D1–D5 拍板签字  
> **基线分支**：`upgrade/continued`（commit `33684ca`）  
> **上游需求**：[三问题诊断与升级方案.md](./三问题诊断与升级方案.md)（根因诊断与代码引用）  
> **目标读者**：产品专家、测试专家、研发实施者  

---

## 0. 方案摘要（给评审 3 分钟版）

### 我们要解决什么

| ID | 用户可见问题 | 用户影响 | 优先级 |
|----|-------------|----------|--------|
| **FIX-②** | 项目详情页 DAG / 时间线空白 | 无法观测编排进度与历史，信任感下降 | **P0** |
| **FIX-③** | 项目成本恒显示 0 Token | 预算与成本不可见，治理失效 | **P1** |
| **FIX-①** | 切换 Agent 会停掉其它 Agent 对话 | 多 Agent 并行协作不可用，体验最痛 | **P1** |

### 我们不做什麼

- 不重写前端框架 / 不引入新状态管理库  
- 不改动 kernel 调度、Gate、contracts、Store schema  
- 不改动后端 chat API 契约  
- 不做 Token 单价配置、告警策略等产品扩展（仅修复计量为 0 的 bug）  

### 交付形态

**一个聚焦的小版本（patch release）**，分 3 个可独立合入、独立验收的 PR：

```
PR-1（P0）FIX-② DAG/时间线
PR-2（P1）FIX-③ Token 计量
PR-3（P1）FIX-① 多 Agent 并发对话 — 分两阶段
```

### 建议排期

| 阶段 | 内容 | 预估工时 | 依赖 |
|------|------|----------|------|
| Sprint-0 | PR-1 合入 + 冒烟 | 0.5d | 无 |
| Sprint-1 | PR-2 合入 + 单测 | 1d | 无 |
| Sprint-2a | PR-3 Phase 1（不杀流） | 1d | 无 |
| Sprint-2b | PR-3 Phase 2（跨 Agent 实时渲染） | **2–2.5d** | Phase 1 |

### 评审结论摘要（v1.1 纳入）

| 维度 | 评分 | 说明 |
|------|------|------|
| 根因诊断 | ⭐⭐⭐⭐⭐ | 全链路闭环，活库证据充分 |
| 方案收敛性 | ⭐⭐⭐⭐⭐ | 改动面小，不波及 kernel |
| 分期合理性 | ⭐⭐⭐⭐ | Phase 1/2 拆分合理；**Phase 2 估时已上调** |
| 测试覆盖 | ⭐⭐⭐⭐ | 矩阵完整；**测试数据准备已补充 §4.1.1** |
| 风险控制 | ⭐⭐⭐⭐ | **PR-2/PR-3 增加 feature flag 灰度** |

**总体**：方案基本通过；按下方 **§10 决策点 D1–D5** 拍板后即可启动。PR-1（DAG）可立即开工。

---

## 1. 背景与目标

### 1.1 背景

myteam 在「多 Agent 对话」「项目可观测性」「成本治理」三条用户路径上存在已定位的缺陷。根因分析已完成（见上游需求文档），本方案将其转化为**可评审、可测试、可分期交付**的升级计划。

### 1.2 成功标准（Release 级）

| # | 标准 | 验证方式 |
|---|------|----------|
| R1 | 任意已完成项目的 DAG 与时间线可正常展示 | 手工 + 自动化冒烟 |
| R2 | Claude 后端编排交互后 `interaction.tokens > 0`，成本面板非 0 | 单测 + 一次真实 kernel run |
| R3 | ≥2 个 Agent 同时执行任务时，切换不中断彼此 | 手工并发场景 |
| R4 | 「停止」仅影响当前 Agent，不影响其它后台流 | 手工 |
| R5 | Opencode 路径 Token 计量无回归 | 现有单测 + 对照 run |

### 1.3 非目标（Out of Scope）

- 群聊内部的完全独立多并发流（本期保证**单聊↔群聊切换不互杀**，群聊路径与单聊同样做 stream 注册表镜像）  
- 时间线事件类型的语义丰富化（`project.event` 兜底标签优化为独立项）  
- Hub 私聊路径的 Token 展示（本期仅修复 **kernel 编排 → `interaction.tokens` → `cost()`** 链路）  

---

## 2. 产品视角（供产品专家评审）

### 2.1 用户故事与验收口径

#### FIX-② DAG / 时间线

| 角色 | 故事 | 验收 |
|------|------|------|
| 项目负责人 | 我想在项目详情看到任务依赖图，以便判断阻塞点 | DAG 节点按状态着色、可点击跳转交付物 |
| 项目负责人 | 我想看项目事件时间线，以便复盘执行过程 | 时间线有事件行，非空白 |
| 任意用户 | 我不应看到「加载失败：Cannot read properties of undefined」 | `project-meta` 无此类错误 |

**产品关注点**：修复后无需用户操作或数据迁移；历史项目即时生效。

#### FIX-③ Token 计量

| 角色 | 故事 | 验收 |
|------|------|------|
| 项目负责人 | 我想看到项目真实 Token 消耗，以便控制预算 | 成本卡片 `total > 0`（有 Claude 交互的项目） |
| 项目负责人 | 我想按 Agent / Task 维度看成本分布 | `by_agent` / `by_task` 非全 0 |

**产品关注点**：

- Claude 计价为**近似值**（per-message usage 累加），非账单级精确；需在 UI 或文档中保持现有 hint 语义（「若 CLI 无 step_finish 则保持为 0」文案可在修复后调整为更准确描述）。  
- Opencode 项目行为不变。  
- 未配置单价时仍只显示 Token，不显示人民币——**不扩 scope**。

#### FIX-① 多 Agent 并发对话

| 角色 | 故事 | 验收 |
|------|------|------|
| 用户 | 我让 main 跑长任务时，可以切到产品 Agent 继续工作，main 不被打断 | 切回 main 时任务仍在进行或已完成 |
| 用户 | 我点「停止」只停当前 Agent | 其它 Agent 后台流继续 |
| 用户 | 切回某 Agent 能看到其在后台的产出 | Phase 2 完整验收；Phase 1 至少看到完成态快照 |

**产品关注点 — 分期体验差异（需产品确认是否接受）**：

| 阶段 | 用户可感知行为 | 缺口 |
|------|----------------|------|
| **Phase 1** | 切换不再杀流；切回看到**完成态快照**（非实时滚动） | 在 Agent B 界面时，Agent A 的气泡**不实时更新** |
| **Phase 2** | 切回 Agent A 可看到进行中实时更新 | 聊天气泡全链路 DOM 双模式改造，**2–2.5d** |

> **评审建议（D1）**：**接受 Phase 1 先行**。理由：Phase 1 解决「任务被杀」功能性 bug，改动收敛、风险低；Phase 2 为体验增强，紧随其后。**Release note 须写明**：「切回 Agent 时看到完整快照；后台实时滚动将在下一版本支持。」

### 2.2 体验边界与已知限制

| 限制 | 说明 | 本期处理 |
|------|------|----------|
| 群聊与单聊共用全局 `isStreaming` | Agent ↔ 群聊切换会互杀流（与 FIX-① 同根） | **PR-3 Phase 1 必做**：`group.js` 镜像 stream 注册表（D3） |
| Hub 私聊无 Token 卡片 | 计量链路在 kernel，不在 DM chat | 不修；产品文案勿误导 |
| Claude Token 为估算 | 累加语义与 Anthropic 账单可能有偏差 | 测试用对照 transcript 验证「非零且量级合理」 |
| `agentEventSource` 单例 | 切换 Agent 会断开上一 Agent 的 SSE | **纳入 PR-3 必做**，否则后台 thinking 事件丢失 |

### 2.3 产品评审清单

- [ ] 同意 P0/P1 优先级排序（② → ③ → ①）  
- [ ] 确认 FIX-① Phase 1 / Phase 2 分期策略  
- [ ] 确认 Claude Token「近似计费」可接受  
- [ ] 确认群聊路径纳入 PR-3 Phase 1（**评审建议：是**）  
- [ ] 确认 Phase 1 release note 文案（快照 vs 实时滚动）  
- [ ] 确认 Token 近似计费文案调整（见 D2）  

**产品专家签字**：____________  日期：____________

---

## 3. 技术方案（供研发与测试理解上下文）

> 详细根因与代码行号见 [三问题诊断与升级方案.md](./三问题诊断与升级方案.md)。

### 3.1 FIX-② DAG / 时间线（P0）

**改动文件**：`frontend/dag-renderer.js`（必须）、`frontend/project.js`（建议）

| 项 | 内容 |
|----|------|
| 主修 | `dag-renderer.js:37` 改为 `const tid = t.id \|\| t.task_id`，与 `:21` 一致 |
| 加固 | `project.js` DAG / 时间线分独立 `try`，避免连坐 |
| 加固 | `dag-renderer.js:57` 对 `byId[id]` 空值守卫 |
| 后端 | **不改**（`task_id → id` 为既定契约） |

### 3.2 FIX-③ Token 计量（P1）

**改动文件**：`backend/adapters/claude/parser.py`（必须）、`backend/common/agent_port.py`（聚合分支）、可选 `backend/common/store.py`

| 项 | 内容 |
|----|------|
| 主方案 A | `assistant` 分支读取 `message.usage`，emit `step_finish`（`cumulative: false`） |
| 聚合 | `_drain` 识别 `cumulative` 标志：true → MAX（opencode）；false → 累加（claude per-message） |
| 可选方案 B | `.response` 落盘后 grace 延长至 8–10s 或等到 `result` 行，作兜底 |
| 单测 | 喂入含 N 条 `assistant.usage` + 1 条 `result.usage` 的 transcript fixture |
| 回归 | opencode 路径仍取 MAX，现有 `test_agent_transport` 通过 |

**计费近似公式（单测择优，见 D2）**：

| 算式 | 公式 | 特点 |
|------|------|------|
| A | `max(input_i) + Σ output_i` | 可能少算（上下文重复 input 被折叠） |
| **B（倾向）** | `Σ input_i + Σ output_i` | 可能略高于账单，但不系统性少算 |

PR-2 首日采集 transcript fixture，对比 A/B 与 `result.usage` 后定稿；UI 标注「近似值」。

**灰度（D4）**：`system_config.json` 增加 `features.claude_token_metering_v2`（默认 `false`），发布后观察 1–2 天再默认开启。

### 3.3 FIX-① 多 Agent 并发（P1）

**改动文件**：`frontend/ui-core.js`、`frontend/chat.js`、**`frontend/group.js`（Phase 1 必做）**

#### Phase 1 — 不再杀流（最小可用）

| # | 改动 |
|---|------|
| 1 | `S.streams[agentId] = { abortCtrl, reader, ctx, busy }` 替代全局单槽 |
| 2 | `sendAgentMsg` 绑定 `const aid = S.currentAgentId`，busy 守卫与清理 scoped 到 `aid` |
| 3 | **删除** `selectAgent:84` 的 `if (S.isStreaming) stopStream()` |
| 4 | `setStatus` / `updateSendBtn` / `cancelActiveStream` 读 `S.streams[S.currentAgentId]` |
| 5 | `rollbackAgentTurn` 绑定发送时 `aid`，防错 agent 回滚 |
| 6 | `loadDmHistory` 守卫改为 `!S.streams[id]?.busy` |
| 7 | `agentEventSource` 改为 per-agent 或切换时不断开非当前连接 |
| 8 | **`group.js` 镜像**：`sendGroupMsg` / 切换群聊 同样用 `S.streams`，去掉切换即 abort |

**灰度（D4）**：`system_config.json` 增加 `features.multi_agent_streams`（默认 `false`），可快速回退旧单槽行为。

#### Phase 2 — 跨 Agent 实时渲染（估时 2–2.5d）

| # | 改动 |
|---|------|
| 9 | 流事件先写 `S.agentMessages[aid]`，仅当 `aid === S.currentAgentId` 时写 DOM |
| 10 | **聊天气泡路径**（`renderAgentMsg` / `handleChatEvent` / `updateThinkingHeader`）改为「写数据 + 条件写 DOM」双模式；**不复用** `ensureAgentTaskBlock`（该函数仅服务后台任务面板） |
| 11 | 切回 Agent 时重渲染整个可见消息区 + 保持滚动位置 |

**后端**：零改动（每请求独立 `cancel_event`，行为正确）。

---

## 4. 测试方案（供测试专家评审）

### 4.1 测试环境与前置

```bash
# 仓库根
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend" NO_PROXY="localhost,127.0.0.1,::1"

# 启动 Hub（观测 DAG/时间线/成本）
./run.sh start

# Kernel 跑项目（Token 验收）
venv/bin/python3 backend/common/run_kernel.py <project_id> \
  --goal "..." --backend claude --budget 150000

# 单测
PYTHONPATH="$PWD/backend" venv/bin/python3 -m pytest backend -q
```

**测试数据（概要）**：

- 已完成项目：`critique-myteam-v3`（或任意 `status=completed` 且 `task≥1`）  
- 活库：`business/tasks/state.db`（修复前 `step_finish=0` 可作为对照）  

### 4.1.1 测试数据准备（负责人与产出物）

| TC / 用途 | 谁准备 | 怎么准备 | 产出物 |
|-----------|--------|----------|--------|
| TC-③-05 transcript fixture | **研发采集，QA 归档** | PR-2 首日：跑一次 `run_kernel.py --backend claude`，重定向 stdout；或在 `parser.py` 临时 log 原始 JSON 行 | `backend/adapters/claude/tests/fixtures/*.jsonl` |
| TC-③-05 场景覆盖 | 研发 + QA | 场景 1：单轮 Q&A；场景 2：≥3 轮含 tool_use | 两份 fixture + 算式 A/B 偏差表 |
| TC-②-07 坏数据 | **QA** | 在测试库 INSERT 一条 `deps` 含不存在 id 的 task；或前端单测直接构造数组 | 单测 fixture / 临时 SQL 脚本 |
| TC-① 并发 | QA | 准备 ≥2 个已配置 agent（如 `main` + 产品 agent），各能触发长任务 | 手工场景说明 1 页 |
| Opencode 回归基线 | QA | 修复前记录一次 `interaction.tokens` 作为对照 | `docs/0608/fixtures/token-baseline-opencode.txt`（可选） |

### 4.2 测试用例矩阵

#### PR-1：FIX-② DAG / 时间线

| TC-ID | 场景 | 步骤 | 预期 | 优先级 |
|-------|------|------|------|--------|
| TC-②-01 | DAG 正常渲染 | 打开已完成项目 → DAG 子页 | 节点可见、状态色正确、无 JS 错误 | P0 |
| TC-②-02 | 时间线正常渲染 | 同上 → 时间线子页 | 事件列表非空 | P0 |
| TC-②-03 | 概览无加载失败 | 打开项目详情概览 | `project-meta` 无「加载失败」 | P0 |
| TC-②-04 | SSE 刷新不抛错 | 项目运行中停留详情页 | `refreshProjectDetail` 不反复报错 | P1 |
| TC-②-05 | 节点点击 | 点击 DAG 节点 | 跳转对应交付物（若已实现） | P2 |
| TC-②-06 | 空项目 | 打开无 task 的新项目 | 空态提示，非异常 | P2 |
| TC-②-07 | 坏数据韧性 | 构造 deps 指向不存在 id 的 task 列表 | 不白屏（加固项） | P2 |

#### PR-2：FIX-③ Token 计量

| TC-ID | 场景 | 步骤 | 预期 | 优先级 |
|-------|------|------|------|--------|
| TC-③-01 | Claude kernel run | `--backend claude` 跑完 1 次交互 | `interaction.tokens > 0` | P0 |
| TC-③-02 | 成本面板 | 打开对应项目成本区 | total / by_agent / by_task 非全 0 | P0 |
| TC-③-03 | run_event 有 step_finish | 查 `run_event` 表 | 存在 `step_finish` 行 | P1 |
| TC-③-04 | Opencode 回归 | `--backend opencode` 跑 1 次 | tokens 与修复前同量级，单测全绿 | P0 |
| TC-③-05 | 单测 fixture | `pytest` claude parser / agent_port 新测 | 累加结果与预期一致 | P0 |
| TC-③-06 | 早杀时序 | `.response` 落盘后 <2.5s 结束 | tokens 仍 > 0（不依赖 result 行） | P1 |
| TC-③-07 | 无单价配置 | 设置中单价为空 | 只显示 Token，不崩 | P2 |
| TC-③-08 | feature flag 回退 | 关闭 `claude_token_metering_v2` | 恢复旧计量逻辑 | P1 |
| TC-③-09 | 算式偏差 | 用 fixture 对比 A/B 算式 | 选定算式与 `result.usage` 偏差在可接受范围 | P1 |

**SQL 验收参考**：

```sql
SELECT interaction_id, tokens FROM interaction WHERE project_id = '<id>';
SELECT kind, COUNT(*) FROM run_event WHERE interaction_id = '<iid>' GROUP BY kind;
```

#### PR-3：FIX-① 多 Agent 并发

| TC-ID | 场景 | 步骤 | 预期 | 优先级 |
|-------|------|------|------|--------|
| TC-①-01 | 双 Agent 并发 | main 发长任务 → 切产品发任务 → 切回 main | 两任务均未完成前仍 running | P0 |
| TC-①-02 | 停止隔离 | A、B 同时跑 → 在 B 点停止 | 仅 B 停止，A 继续 | P0 |
| TC-①-03 | 切回见完成内容 | A 后台跑完 → 切回 A | 看到完整 agent 回复（Phase 1） | P0 |
| TC-①-04 | 实时渲染 | A 后台跑时切到 B 再切回 A（Phase 2） | A 气泡持续更新 | P1 |
| TC-①-05 | 无误回滚 | 切换不 abort | 不出现 AbortError 导致消息被撤回 | P0 |
| TC-①-06 | 发送按钮状态 | A 忙、B 空闲，当前在 B | B 显示「就绪/发送」，非误显「停止」 | P1 |
| TC-①-07 | 历史加载 | A 忙时切到 C 加载历史 | C 的历史正常显示 | P1 |
| TC-①-08 | 后台 thinking | A 跑时切走再切回 | thinking 块正确（EventSource） | P1 |
| TC-①-09 | 单聊↔群聊不互杀 | 单聊 A 跑着 → 进群聊发消息 → 切回 A | A 流继续；群聊流独立（PR-3 Phase 1） | P0 |
| TC-①-10 | feature flag 回退 | 关闭 `multi_agent_streams` | 恢复旧单槽行为，无 JS 错误 | P1 |

### 4.3 回归范围

| 区域 | 回归点 |
|------|--------|
| 单聊 | 发送、停止、thinking 展示、错误气泡 |
| 群聊 | 发送、清空（`clearGroupChat` 仍只停当前上下文的流） |
| 项目详情 | 概览、交付物、事件 feed、成本卡片 |
| Kernel | `run_kernel.py` exit 0、Gate 通过、重试逻辑 |
| Opencode | Token 计量、多 step_finish |

### 4.4 自动化建议

| 项 | 类型 | 说明 |
|----|------|------|
| `dag-renderer` 字段兼容 | 单元 | 传入 `{id:...}` 与 `{task_id:...}` 均能布局 |
| claude parser usage | 单元 | transcript fixture → step_finish 事件 |
| agent_port 累加语义 | 单元 | cumulative true/false 分支 |
| observability API | 已有 | `test_observability_api.py` 保持绿 |

### 4.5 测试评审清单

- [ ] 用例矩阵覆盖 P0 路径  
- [ ] 明确 Phase 1 / Phase 2 验收分界  
- [ ] 确认 Claude / Opencode 双后端均需过  
- [ ] 确认不需要性能压测（本期无）  
- [ ] 补充必要的测试数据准备脚本（可选）  

**测试专家签字**：____________  日期：____________

---

## 5. 发布与回滚

### 5.1 合入顺序

```
PR-1（FIX-②）→ 冒烟 → PR-2（FIX-③）→ 单测 + 一次 claude run → PR-3a（FIX-① P1）→ PR-3b（FIX-① P2，可选）
```

每 PR 独立可回滚，不强依赖顺序（仅推荐顺序降低风险）。

### 5.2 回滚策略

| PR | 回滚影响 |
|----|----------|
| PR-1 | DAG/时间线恢复空白（纯前端） |
| PR-2 | Token 回 0（adapter + agent_port 局部） |
| PR-3 | 恢复切换杀流行为（前端） |

### 5.3 灰度与监控（PR-2 / PR-3）

| 开关 | 配置路径 | 默认 | 作用 |
|------|----------|------|------|
| `features.claude_token_metering_v2` | `config/system_config.json` | `false` | 新 claude usage 累加逻辑；异常时可秒级回退 |
| `features.multi_agent_streams` | `config/system_config.json` | `false` | 新 per-agent 流模型；竞态时可回退单槽 |

**发布后观察（1–2 天）**：

- PR-2：抽查 3 个 claude 项目的 `interaction.tokens` 是否非零、量级是否合理  
- PR-3：双 Agent 并发无竞态投诉；`AbortError` 误回滚为 0  

确认无异常后将两开关默认改为 `true`（或移除开关，视实现复杂度定）。

### 5.4 发布后验证（Smoke checklist）

- [ ] Hub 可访问 `http://localhost:8765`  
- [ ] 打开 1 个已完成项目：DAG + 时间线 OK  
- [ ] 成本非 0（claude 项目，flag 开启后）  
- [ ] 双 Agent 切换不杀流（flag 开启后）  
- [ ] 单聊 A 跑着进群聊，A 不被杀  

---

## 6. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Claude `usage` 字段与假设不符 | 中 | Token 仍偏差 | §4.1.1 fixture 首日采集 + TC-③-09 |
| FIX-① Phase 1 体验不完整 | 高 | 用户以为仍 bug | D1 拍板 + release note 明确「快照非实时」 |
| Phase 2 工作量超预期 | 中 | 延期 | 估时已上调 2–2.5d；聊天气泡路径单独排期 |
| Opencode 累加语义误改 | 低 | 计费偏大/小 | `cumulative` 标志 + 回归单测 |
| EventSource 多连接资源 | 低 | 浏览器连接数 | idle 断开非当前 agent 连接 |
| 计量/并发逻辑线上异常 | 低 | 用户感知错误 | **feature flag 秒级回退**（§5.3） |

---

## 7. 任务拆解（研发 WBS）

| 任务 | 负责人 | 估时 | PR |
|------|--------|------|-----|
| T1 dag-renderer 主修 + 守卫 | dev | 2h | PR-1 |
| T2 project.js 拆 try | dev | 1h | PR-1 |
| T3 claude parser assistant.usage | dev | 3h | PR-2 |
| T4 agent_port 累加语义 + 单测 | dev | 4h | PR-2 |
| T5 transcript fixture 采集（§4.1.1） | dev/qa | 2h | PR-2 |
| T5b feature flag `claude_token_metering_v2` | dev | 2h | PR-2 |
| T6 streams 注册表 + 去掉 abort | dev | 4h | PR-3a |
| T7 per-agent EventSource | dev | 3h | PR-3a |
| T7b group.js stream 镜像 | dev | 3h | PR-3a |
| T7c feature flag `multi_agent_streams` | dev | 2h | PR-3a |
| T8 聊天气泡 DOM 双模式 + 实时渲染 | dev | **12–16h** | PR-3b |
| T9 全量回归（含 TC-①-09 单聊↔群聊） | qa | 5h | all |
| T10 release note + Token 文案 | pm/dev | 1h | release |

---

## 8. 文档与沟通

| 产物 | 路径 | 受众 |
|------|------|------|
| 需求诊断（上游） | `docs/0608/三问题诊断与升级方案.md` | 研发 / 全员 |
| 本交付评审方案 | `docs/0608/交付评审方案-chat-dag-token.md` | 产品 / 测试 / 研发 |
| Release note（发布后） | `docs/0608/RELEASE-NOTE-chat-dag-token.md`（待写） | 全员 |

---

## 9. 评审结论栏

### 产品专家评审

| 项 | 结论（通过 / 修改后通过 / 驳回） | 意见 |
|----|----------------------------------|------|
| 优先级与范围 | | |
| FIX-① 分期策略（D1） | | |
| Token 近似计费（D2） | | |
| 群聊同期修复（D3） | | |

### 测试专家评审

| 项 | 结论（通过 / 修改后通过 / 驳回） | 意见 |
|----|----------------------------------|------|
| 用例覆盖度 | | |
| 测试数据准备（§4.1.1） | | |
| feature flag 灰度（D4） | | |
| Phase 验收分界（D5） | | |

### 综合结论

- [ ] **批准实施** — 按 §5 合入顺序执行  
- [x] **修改后实施** — v1.1 已纳入评审意见，待 D1–D5 拍板  
- [ ] **驳回** — 需重新方案  

**批准人**：____________  **日期**：____________

---

## 10. 决策拍板栏（D1–D5）

| ID | 决策项 | 评审建议 | 产品 | 测试 | 最终 |
|----|--------|----------|------|------|------|
| **D1** | FIX-① 分期：Phase 1 先行 vs 一次性 Phase 2 | **Phase 1 先行**；release note 说明快照非实时 | ☐ | ☐ | ☐ |
| **D2** | Claude Token 近似计费：算式 A vs B | **倾向算式 B**（Σ input + Σ output）；UI 标「近似值」 | ☐ | ☐ | ☐ |
| **D3** | 群聊/单聊互斥：文档化 vs 同期修复 | **PR-3 Phase 1 同期修 group.js** | ☐ | ☐ | ☐ |
| **D4** | PR-2/PR-3 是否引入 feature flag | **引入**（各 +2h）；默认关，观察 1–2 天后开 | ☐ | ☐ | ☐ |
| **D5** | Phase 2 估时：1.5d vs 2.5d | **接受 2–2.5d**（聊天气泡 DOM 全链路改造） | ☐ | ☐ | ☐ |

---

## 附录 A：关键文件索引

| 文件 | FIX |
|------|-----|
| `frontend/dag-renderer.js` | ② |
| `frontend/project.js` | ② |
| `backend/adapters/claude/parser.py` | ③ |
| `backend/common/agent_port.py` | ③ |
| `frontend/ui-core.js` | ① |
| `frontend/chat.js` | ① |
| `frontend/group.js` | ①（Phase 1 必做镜像） |
| `config/system_config.json` | ③①（feature flags） |

## 附录 B：评审问题速查（FAQ）

**Q：为什么 FIX-② 比 FIX-① 优先？**  
A：② 一行修复、零风险、立刻恢复可观测性；① 涉及并发状态，需更多测试。

**Q：修完后 Token 数字是否等于 Anthropic 账单？**  
A：不保证。目标是「非零且量级合理」，供项目内治理；精确对账需后续对接账单 API。

**Q：Hub 私聊为什么可能仍看不到 Token？**  
A：本期只修 kernel 编排写入 `interaction.tokens` 的链路，Hub DM 未纳入。

**Q：两个 Agent 同时跑会加倍耗资源吗？**  
A：会。这是预期行为——用户诉求是「不被误杀」，不是限制并发。

**Q：Phase 1 切回为什么不是实时滚动？**  
A：Phase 1 只修「不杀流」+「切回见快照」；实时滚动需 Phase 2 改造聊天气泡 DOM 全链路，估时 2–2.5d。

**Q：feature flag 什么时候默认开启？**  
A：全量发布并观察 1–2 天无异常后，将 `claude_token_metering_v2` / `multi_agent_streams` 默认改为 `true`。
