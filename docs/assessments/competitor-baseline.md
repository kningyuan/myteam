# 竞品基线对比（Competitor Baseline）

> **状态**：已填充 · P1.4 交付物  
> **对比日期**：2026-06-14  
> **定位**：产品定位参考，**非** P2 技术方案依赖（修正项 4）  
> **权威 Gate**：[`platform-v3-gates.md#p1-gate`](./platform-v3-gates.md#p1-gate) P1-G4

---

## 1. 对比范围

| 字段 | 值 |
|------|-----|
| 对比日期 | 2026-06-14 |
| myteam 基线 | `docs/FRAMEWORK-FREEZE.md`（L1/L2 封板）；pytest **585** `def test_` / 运行 **588 passed, 1 failed** |
| 竞品 | CrewAI · LangGraph · AutoGPT |
| 数据来源 | 官方文档与 GitHub 公开 README（见 §5）；myteam 列为代码库扫描 |

---

## 2. 对比矩阵（≥5 维度）

| 维度 | myteam | CrewAI | LangGraph | AutoGPT | 说明 / 引用 |
|------|--------|--------|-----------|---------|-------------|
| **协作模型** | **DAG 编排**：Process 按 wave 调度 `execute/review/triage`；Agent **不互聊** | **Crew**：Role + Task 委托；Agent 可 delegate、sequential/hierarchical process | **有向图状态机**：节点=函数/Agent，边=条件转移；支持环与持久状态 | **自主循环**：目标分解→执行→自我批判→再规划 | myteam `ARCHITECTURE.md` §3 · CrewAI [Concepts](https://docs.crewai.com/concepts/crews) · LangGraph [Graph API](https://langchain-ai.github.io/langgraph/) · AutoGPT [README](https://github.com/Significant-Gravitas/AutoGPT) |
| **Gate / 契约校验** | **确定性 Gate** + `submit_result.py` 契约；失败回灌 `retry_feedback` | 任务输出靠 Task `expected_output`；无统一 submit 契约 | 图节点可挂 validator；依赖开发者自建 | 目标完成度自检（LLM）；无统一 Gate 层 | myteam `FRAMEWORK-FREEZE.md` §2.1 · CrewAI [Tasks](https://docs.crewai.com/concepts/tasks) |
| **持久化 / 状态** | **SQLite** `business/tasks/state.db`（WAL，12 MB 实测）+ 文件 deliverables | 内存为主；可选外部存储集成 | **Checkpointer** 一等公民（内存/SQLite/Postgres） | 文件/向量记忆；架构随版本变化 | myteam `store.py` · LangGraph [Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) |
| **可观测性** | `/api/obs/*` 只读 API；interaction timeline；deliverables 双通道 | 内置 tracing 集成（LangSmith 等）可选 | LangSmith / Studio 可视化图执行 | 日志 + 插件生态 | myteam `observability_api.py`（291 行） |
| **CLI / 后端适配** | **Adapter 隔离**：opencode + claude；Hub SSE 仅消费规范化 `thinking` | 多 LLM provider 配置 | LangChain 模型生态 | 多模型 + 插件 | myteam `backend/adapters/` · `FRAMEWORK-FREEZE.md` §2.2 |
| **扩展维度：Human-in-the-loop** | `needs_review` 任务态 + review interaction；无全局 interrupt API | 支持 human input on task | **interrupt / breakpoint** 原生 | 用户批准工具调用（版本相关） | LangGraph [Interrupts](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/) |

---

## 3. 量化指标表

| 指标 | myteam | CrewAI | LangGraph | AutoGPT | 来源 |
|------|--------|--------|-----------|---------|------|
| GitHub Stars（约，2026-06） | N/A（私有/本地） | **~25k+** `crewAIInc/crewAI` | **~12k+** `langchain-ai/langgraph` | **~175k+** `Significant-Gravitas/AutoGPT` | GitHub 公开仓库页（快照，随时间变化） |
| 主语言 | Python | Python | Python | Python | 各仓库 |
| 内置编排测试（本仓库） | **585** test 函数；**588 passed** | 上游 CI 有 pytest（见仓库 workflows） | 上游 CI 有 pytest | 上游 CI 有 pytest | myteam `rg def test_`；竞品见各 GitHub Actions |
| 文档结构 | `docs/ARCHITECTURE.md` + `FRAMEWORK-FREEZE.md` | docs.crewai.com 分 Concepts/How-to | langchain-ai.github.io/langgraph | 文档分散（主 README + wiki） | §5 URL |
| 生产 workflow 资产（磁盘） | **13** yaml（`business/workflows/`） | 示例 crew 模板 | 示例 graph 教程 | 插件/示例 | myteam `ls business/workflows/*.yaml` |
| 默认部署单元 | 单 Hub + SQLite 文件 | Python 包 / Flow | Python 包 + 可选 LangGraph Platform | CLI / 插件 | 各官方 README |

> **注**：GitHub Stars 为公开页面数量级，用于定位生态体量，非精确竞对 KPI。

---

## 4. 差异化判断

### 4.1 myteam 优势维度

| 维度 | 证据 | 置信度 |
|------|------|--------|
| 确定性交付链 | Gate + deliverables 目录 + SQLite 真相分离；非纯 LLM 自评 | 高 — `store.py` + `submit_result` 测试覆盖 |
| 中文业务 workflow | 13 条 yaml 含 GEO/内容运营/平台 v3 等 | 高 — 磁盘清单 |
| 编排/Hub 解耦 | `run_kernel.py` 可脱离 Hub；共用 state.db | 高 — `ARCHITECTURE.md` §1 |
| Adapter 隔离 invariant | 封板文档 + opencode parser 独立 | 中高 — `FRAMEWORK-FREEZE.md` |

### 4.2 myteam 劣势 / 追赶维度

| 维度 | 证据 | 优先级 |
|------|------|--------|
| 生态与社区 | Stars/docs 体量小于 CrewAI/LangGraph/AutoGPT | P2 叙事，非阻塞 |
| 图可视化 / Studio | 无 LangGraph Studio 级调试 UI | P1 可观测增强 |
| 分布式持久化 | 单 SQLite 文件；PG 未落地 | P2.4 方案后 P3 |
| Human-in-the-loop API | 仅 review 节点，无通用 interrupt | P2 产品 backlog |

### 4.3 对 v3 改进方向的启示（非技术依赖）

1. **保持 DAG+Gate 定位**，不改为 Crew 式角色互聊——与封板 invariant 一致。
2. **补齐可观测与 token 功能性验收**（P3-G4）可缩小与 LangGraph Studio 的「运维体验」差距。
3. **竞品社区体量**用于对外话术，不改变 P2 API/Store 技术 DAG 优先级。

---

## 5. 引用来源清单

| # | 来源 | URL | 访问日期 |
|---|------|-----|----------|
| 1 | myteam FRAMEWORK-FREEZE | `docs/FRAMEWORK-FREEZE.md` | 2026-06-14 |
| 2 | myteam ARCHITECTURE | `docs/ARCHITECTURE.md` | 2026-06-14 |
| 3 | CrewAI 官方文档 | https://docs.crewai.com/ | 2026-06-14 |
| 4 | CrewAI GitHub | https://github.com/crewAIInc/crewAI | 2026-06-14 |
| 5 | LangGraph 官方文档 | https://langchain-ai.github.io/langgraph/ | 2026-06-14 |
| 6 | LangGraph GitHub | https://github.com/langchain-ai/langgraph | 2026-06-14 |
| 7 | AutoGPT GitHub | https://github.com/Significant-Gravitas/AutoGPT | 2026-06-14 |

---

## 6. P1.4 完成检查清单

- [x] ≥3 竞品行已填（非 TBD）
- [x] ≥5 对比维度已填（6 维）
- [x] 量化指标表 ≥3 项有数字
- [x] 外部结论附 URL
- [x] §4 差异化判断（优势 + 劣势）
- [x] 文首对比日期已更新
