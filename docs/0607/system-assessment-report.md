# myteam 系统专业评估报告

> **文档类型**：系统评估 / 架构评审  
> **评估日期**：2026-06-06  
> **评估视角**：项目负责人 · 产品专家 · 系统架构师  
> **代码基线**：分支 `upgrade/continued`（内核重构与 Hub 增量阶段）  
> **状态**：初版

---

## 1. 执行摘要

myteam 已完成从「重型 OpenClaw/Telegram 栈」到「轻量 Web Hub + 确定性编排内核」的核心迁移。**System Kernel（Process / AgentPort / Gate / Store / Observability）设计成熟、边界清晰、可测试性强**，在多 Agent 协作领域具备差异化优势：Interaction 契约、确定性门禁、SQLite 真相库、Strategy/Skill 三层分离。

当前主要短板不在「能不能跑」，而在 **产品闭环、工程保障、安全边界、Hub 一体化体验** 四个方向：

| 维度 | 成熟度（1–5） | 一句话 |
|------|:-------------:|--------|
| 编排内核架构 | **4.5** | 工业级抽象已闭合，refactor 成效显著 |
| 测试与质量保障 | **3.0** | 用例覆盖广，但全量回归不可靠、Hub 测试薄弱 |
| 产品体验（新用户 → 跑通 → 可观测） | **2.5** | 文档与 `--init`/`--demo` 已有，但 UI/错误体验仍断层 |
| Hub / 前端工程 | **2.5** | 功能堆叠快，`app.js` 单文件 3.5k 行，缺模块化与测试 |
| 安全与运维 | **2.0** | 本地工具合理，但无鉴权、广域绑定、无 CI |
| 演进路线清晰度 | **4.0** | D1–D19 决策日志完整，OpenAgents 对标清单明确 |

**总体判断**：系统处于 **「内核已工业化，产品化与工程化待补齐」** 阶段。建议接下来 1–2 个迭代优先：**测试回归可信 + 交付物 API/前端闭环 + 统一 Workspace 事件模型（P0）**，再推进 OpenAgents 式 Hub 升级。

---

## 2. 评估范围与方法

### 2.1 范围

- **编排内核**：`backend/common/`（Process、AgentPort、Gate、Store、run_kernel 等）
- **Hub 与服务**：`backend/hub/`、`backend/base/`、`frontend/`
- **适配器层**：`backend/adapter/`、`backend/adapters/{opencode,claude}/`
- **策略与 Skill**：`business/templates/`、`business/config/`、`business/skills/`
- **文档与决策**：`docs/`、`CLAUDE.md`、`README.md`

### 2.2 方法

- 架构与决策文档对照（`ARCHITECTURE.md`、`framework-decisions.md` D1–D19）
- 关键模块规模与 refactor 基线对比（`refactor-baseline.md`）
- 测试执行：205 个用例采集；逐文件运行验证（2026-06-06）
- 与既有规划交叉引用（`product-improvement-plan.md`、`OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md`）

### 2.3 指标快照

| 指标 | 当前值 | 参考基线 |
|------|--------|----------|
| `process.py` 行数 | 282 | 重构前 979；Phase 2 目标 <300 ✓ |
| `store.py` 行数 | 748 | 未拆，复杂度仍集中 |
| `hub/api/server.py` 行数 | 829 | 路由与业务混杂 |
| `frontend/app.js` 行数 | 3,488 | 无前端测试 |
| 测试用例总数 | 205 | framework-decisions 记载 94→140，现继续增长 |
| 逐文件回归（排除 hanging 套件） | 23/24 文件通过 | 见 §5.2 |
| CI/CD | 无 | — |
| 用户向文档 | 6 篇+ | quick-start / user-guide / troubleshooting 等 |

---

## 3. 系统优势（应保留并强化）

### 3.1 架构：正确的分层与 invariant

**System Kernel / Strategy Registry / Skill Pack** 三层边界在代码与文档中一致落地（D19），避免了「一个大 Skill 包打天下」的常见反模式。

核心 invariant 执行良好：

- **Interaction 契约**（D11/D15）：`submit_result` 本地校验 + 原子写，无 JSON 抢救路径
- **Adapter 隔离**：UI/服务层不感知 opencode 字段；新增 CLI 只需 adapter 目录
- **确定性 Gate**（D14）：down-link（registry spec）与 check-link 同源
- **SQLite 真相库**（D13）：Process、Observability、Hub 只读视图共享同一数据源
- **失败语义**（D18）：failed / needs_review / triage 阶梯清晰

### 3.2 内核 refactor 成效显著

`process.py` 从 979 行降至 282 行，抽出 `plan_gate`、`task_pipeline`、`decision_pipeline`、`dag_dispatch`、`plan_expansion` 等模块，**Pipeline + Functional Core** 模式使纯函数路径可零 mock 单测——这是可维护性的实质性提升。

### 3.3 可观测性基础扎实

`observability_api.py` 提供 project overview、cost、fleet、timeline、SSE stream 等只读 API；内核 token 计量、预算暂停（D17）已接入 Process。Hub 重启后可自动续跑中断项目（D8 恢复），体现「运行态可恢复」设计。

### 3.4 新用户路径已有雏形

- `run_kernel.py --init`：幂等创建 12 个 agent workspace
- `run_kernel.py --demo`：内置 goal，一键跑通编排
- 用户文档：`quick-start.md`、`user-guide.md`、`troubleshooting.md`、`glossary.md`

### 3.5 决策可追溯

`framework-decisions.md` 作为决策日志，新接手者可快速理解「为什么这样设计」，降低架构漂移风险。

---

## 4. 分项评估

### 4.1 编排内核（backend/common/）

**评分：4.5 / 5**

| 优点 | 风险 / 不足 |
|------|-------------|
| 模块职责清晰，Process 仅编排入口 | `store.py` 仍 748 行，CRUD + 视图 + 导入器耦合 |
| AgentPort 看门狗、幂等、对账 GC 完备 | DAG **串行**（D12 有意为之），大项目 wall-clock 长 |
| plan_gate 硬校验 agent∈team、task_type 边界 | 决策类 Interaction 仍依赖 LLM 产出合法 JSON，弱模型易失败 |
| workspace_gc、audit_log 等运维向模块已出现 | audit 默认关闭，生产排障依赖手动开配置 |

**建议**：保持 Process 瘦身成果；下一步拆 `store.py` 读写层与视图层，而非再堆逻辑进 Process。

### 4.2 Hub API 与服务层

**评分：3.0 / 5**

| 优点 | 风险 / 不足 |
|------|-------------|
| FastAPI + SSE 聊天/群组/项目/可观测 API 齐全 | `server.py` 829 行，路由、线程任务、业务逻辑同文件 |
| observability 独立 router，只读边界清楚 | 交付物 API 与测试不同步（2 例失败，见 §5.2） |
| 启动时 auto-resume + workspace GC | `@app.on_event("startup")` 已 deprecated，应迁 lifespan |
| Claude adapter 已实现 | Hub 层 **无认证**；绑定 `0.0.0.0` + CORS `*` |

**建议**：按 domain 拆 router（chat / projects / agents / admin）；交付物 API 与 `project_artifacts` 对齐并修测试。

### 4.3 前端（frontend/）

**评分：2.5 / 5**

| 优点 | 风险 / 不足 |
|------|-------------|
| 单页覆盖聊天、群组、项目、Agent 管理、设置 | `app.js` 3,488 行单体，状态全局对象 `S`，难测试难协作 |
| 项目进度、交付物浏览、SSE 事件流已有 UI 钩子 | 无组件化、无构建链、无前端测试 |
| 主题、本地缓存、@mention 等体验细节 | Chat / Project / Obs 仍多源拉取，缺统一时间线（对标 OpenAgents P0） |

**建议**：D9「UI 重设计」时机已到可预研阶段——至少先做 **API 契约冻结 + 前端按 tab 拆模块**，不必一次重写视觉。

### 4.4 产品体验

**评分：2.5 / 5**

`product-improvement-plan.md` 中的 P1–P5 问题大部分仍成立，部分已缓解：

| 原问题 | 现状 |
|--------|------|
| P1 新用户路径长 | **部分缓解**：`--init` / `--demo` + quick-start |
| P2 无用户文档 | **已缓解**：user-guide / glossary / troubleshooting |
| P3 错误信息偏技术 | **部分缓解**：run_kernel 有 friendly traceback；Hub/API 仍不足 |
| P4 进度不可视 | **部分缓解**：Obs API + 前端项目页；未形成统一 Workspace 时间线 |
| P5 workspace 手动配置 | **已缓解**：`--init` + agent_bootstrap |

仍缺：

- `business/demo/` 预置目录（product plan A1）未落地，demo 逻辑内嵌于 `run_kernel`
- Hub 内交付物浏览与文件 API 回归失败，影响「跑完能看」闭环
- Agent 能力发现 / manifest（OpenAgents P1）未实现

### 4.5 工程与质量保障

**评分：3.0 / 5**

| 优点 | 风险 / 不足 |
|------|-------------|
| 内核 24 个测试文件，覆盖 contracts/gate/process/integration | **无 CI**；本地 `pytest backend` 全量运行易挂起 |
| 注入式 Transport，集成测不依赖真实 CLI | `test_observability_api.py` SSE 用例 **>120s 无结束**（疑似 stream 未触发终态） |
| refactor 有基线与验收记录 | `test_projects_api.py` 2 例失败（deliverable 读取） |
| 依赖极简（4 个 Python 包） | 无 ruff/mypy/pre-commit；Python 版本文档写 3.12，venv 实测 3.13 |

### 4.6 安全与运维

**评分：2.0 / 5**（作为本地开发工具可接受；作为局域网共享服务不足）

| 项 | 现状 | 风险 |
|----|------|------|
| 鉴权 | 无 | 局域网任何设备可调用 API、触发 agent 运行 |
| 绑定地址 | `0.0.0.0` | 有意支持局域网，但无配套 ACL |
| CORS | `allow_origins=["*"]` | 浏览器侧过度开放 |
| 密钥 | CLI token 在 opencode/claude 侧 | myteam 不存模型密钥 ✓ |
| 审计 | audit_log 可选 | 默认关，合规场景不足 |
| 部署 | 无 Dockerfile / CI | 环境 reproducibility 靠人工 |

---

## 5. 关键发现（需优先处理）

### 5.1 P0 — 测试回归不可信

**现象**：`pytest backend -q` 在开发环境中长时间无输出/不结束；逐文件执行时 `test_observability_api.py` 单独运行超过 120s timeout。

**根因推测**：SSE stream 测试（`test_project_stream_until_done`、`test_events_sse_streams_until_done`）在 TestClient 下未能在项目/交互终态时收到 `[DONE]`，导致 `iter_text()` 无限等待。

**影响**：团队无法信任「全绿」作为 merge 门禁；与 framework-decisions 声称的「全仓 N 例绿」产生漂移。

**建议**：

1. 为 SSE 测试加 **pytest timeout** 或 mock `asyncio.sleep` + 限定迭代次数
2. 引入 **GitHub Actions / 本地 pre-push**：`pytest backend/common/tests --ignore=test_observability_api.py` 作第一阶段
3. 修复 stream 终态逻辑或测试夹具，使 205 例在 <60s 内稳定全绿

### 5.2 P0 — 交付物 API 回归失败

**现象**：`test_deliverable_read`、`test_deliverable_file_read` 失败。

**影响**：产品闭环「跑完 → Hub 看交付物」受损；与 Phase B「交付物可浏览」目标直接冲突。

**建议**：对齐 `get_task_deliverable_bundle` 与 API 路由的路径约定；修复后补集成测。

### 5.3 P1 — 前端与事件模型分裂

Chat SSE、Obs run_event、群组消息、deliverables 分属不同路径（`OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md` P0 已识别）。

**影响**：用户认知负担高；难以做统一搜索、通知、审计。

**建议**：按清单设计轻量 `WorkspaceEvent` 表/视图，先 **双写** 再逐步收敛 UI。

### 5.4 P1 — Hub  monolith 与缺失的 Hub 测试

`server.py` 承载 30+ 路由，仅 `test_projects_api.py`（8 例，2 失败）覆盖项目相关子集；聊天、群组、agent CRUD 无自动化测试。

**建议**：router 拆分 + 每 router 至少 smoke test；关键路径（创建项目、取消、deliverable）纳入 CI。

### 5.5 P2 — 配置与身份的双轨 confusion

- **Cursor Agent**：`.cursor/rules/`、`CLAUDE.md`、Skills
- **myteam 内核 Agent**：`agents_registry.json`、`workspace-*/IDENTITY.md`

两者互不读取，文档中未显式区分，易导致配置改错层。

**建议**：在 `user-guide.md` 或 `glossary.md` 增加「两种 Agent 配置」说明；Cursor 侧已有 `project-lead.mdc` 可引用。

---

## 6. 改进建议路线图

### Phase 1 — 工程可信（1–2 周，阻塞后续）

| # | 动作 | 验收标准 |
|---|------|----------|
| E1 | 修复 SSE 测试挂起 + deliverable API 失败 | `pytest backend` <60s 全绿 |
| E2 | 添加 CI（GitHub Actions 或本地 `make test`） | PR/提交必跑测试 |
| E3 | FastAPI `on_event` → lifespan 迁移 | 无 DeprecationWarning |

### Phase 2 — 产品闭环（2–4 周）

| # | 动作 | 验收标准 |
|---|------|----------|
| P1 | 交付物 Hub 浏览修复 + 下载/复制稳定 | 新用户 demo 跑完后在 UI 直接看报告 |
| P2 | 友好错误码与用户向 troubleshooting 链接 | run_kernel / Hub API 错误含「下一步」 |
| P3 | Agent roster 页展示 capabilities / task_types / runtime status | 对标 upgrade checklist P1 |

### Phase 3 — 架构演进（1–2 月）

| # | 动作 | 验收标准 |
|---|------|----------|
| A1 | WorkspaceEvent 统一事件模型（双写） | 项目页一条时间线涵盖 chat + task + gate |
| A2 | `store.py` 拆分 + Hub router 拆分 | 单文件 <400 行（server 除外可 <500） |
| A3 | 前端按 domain 拆 JS 模块（无框架亦可） | 每 tab 独立文件 + 最小 smoke |
| A4 | 可选：DAG 有限并行（在 D12 框架内评估） | 独立任务可并发，Store 锁语义清晰 |

### Phase 4 — 安全与对外（按需）

| # | 动作 | 适用场景 |
|---|------|----------|
| S1 | Hub API token / 本地 mTLS | 局域网多人使用 |
| S2 | 默认绑定 127.0.0.1，0.0.0.0 opt-in | 降低误暴露 |
| S3 | audit_log 生产默认策略文档 | 合规审计 |

---

## 7. 与现有规划的关系

| 文档 | 本报告结论 |
|------|------------|
| `product-improvement-plan.md` Phase A | `--init`/`--demo`/用户文档 **已部分完成**；demo 目录化、错误友好化 **未完成** |
| `product-improvement-plan.md` Phase B | 交付物 UI **有雏形但 API 回归失败**，需先 E1/P1 |
| `OPENAGENTS_MYTEAM_UPGRADE_CHECKLIST.md` P0 | 统一事件流、频道 Workspace **仍是最高价值 Hub 升级** |
| `refactor-baseline.md` Phase 2 | Process 目标 **已达成**；下一 refactor 目标应是 store + server |

---

## 8. 结论

myteam 的 **编排内核已达到可长期演进的基础**，设计决策（D1–D19）与代码实现高度一致，这是项目最宝贵的资产。

下一阶段不应再扩大内核功能面，而应把资源集中在：

1. **让测试与 CI 成为真实门禁**（否则 refactor 与 Hub 迭代必然回归）
2. **补齐「跑通 → 看见 → 理解错误」的产品闭环**
3. **按已有 OpenAgents 对标清单做 Hub Workspace 一体化**，而非重复造轮子

按上述 Phase 1→2 执行后，系统可从「内核工业级、产品实验级」进入 **「可对外演示、可多人协作开发」** 的下一阶段。

---

## 附录 A：测试执行记录（2026-06-06）

```
205 tests collected
逐文件执行（timeout 180s/file）：
  - 23/24 文件通过
  - test_observability_api.py：超时（>120s）
  - test_projects_api.py：2 failed, 6 passed
代表性通过套件：test_process (42), test_gate (13), test_contracts (14), test_integration (1)
```

## 附录 B：推荐阅读顺序（新成员）

1. `README.md` → `docs/quick-start.md`
2. `docs/glossary.md` → `docs/user-guide.md`
3. `docs/framework-decisions.md`（D1–D19）
4. `docs/ARCHITECTURE.md` §11–§12
5. 本报告 §6 路线图

---

*本报告基于静态分析与局部测试执行，未包含真实 opencode/claude 长时运行压测与多用户并发场景。*
