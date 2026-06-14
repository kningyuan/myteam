# 六维架构诊断报告

> **生成时间**：2026-06-14  
> **输入**：`docs/FRAMEWORK-FREEZE.md`、`docs/ARCHITECTURE.md`、`backend/hub/api/server.py`、pytest 实测  
> **权威 Gate**：[`platform-v3-gates.md#p1-gate`](./platform-v3-gates.md#p1-gate) P1-G2  
> **六维定义来源**：`business/workflows/myteam-platform-v3.yaml` 任务 `p1-2-six-dim-report`

---

## 度量快照（扫描实证）

| 指标 | 实测值 | 证据 |
|------|--------|------|
| `server.py` 行数 | **~1540** | `wc -l backend/hub/api/server.py`（P3.1 API 拆分 Phase 2 后） |
| Hub HTTP 路由装饰器 | **97** `@app.*` | `rg -c '@app\.(get\|post\|put\|delete\|patch)' backend/hub/api/server.py` |
| Hub API 模块文件 | **5** | `server.py`, `observability_api.py`, `skills_api.py`, `deps.py`, `errors.py` |
| `observability_api.py` | **291** 行 | 只读观测域已部分拆分 |
| `store.py` | **1099** 行 | `backend/common/store.py` |
| pytest 用例（`def test_`） | **589+** | `pytest backend/common/tests -q` 计数 |
| pytest 运行（2026-06-14） | **589 passed, 0 failed**（common） · **594 passed, 0 failed**（`backend -q`） | `PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests -q` |
| 生产 SQLite bypass | **0** | `rg '_conn.execute' backend` 除 `store.py` → 仅测试 4 处 |
| E2E 基线双跑 | **8 passed × 2，consistent** | `scripts/regression/reg_platform_v3_e2e_baseline.py` |
| `_KERNEL_RUNS` 内存 dict | **已删除** | `rg '_KERNEL_RUNS' backend/hub/api/server.py` → 0 匹配 |
| `kernel_run.py` | **存在，95 行** | `backend/hub/services/kernel_run.py` |
| `token_usage.py` | **存在，64 行** | `backend/common/token_usage.py` + `StoreTokenUsageSink` |
| `state.db` 路径 | `business/tasks/state.db` | `common/store.py:33-34` `default_db_path()` |
| `state.db` 大小 | **~12 MB** | `du -h business/tasks/state.db` |
| WAL 模式 | **wal** | `sqlite3 … PRAGMA journal_mode` |
| 生产 workflow yaml | **13** 个 | `ls business/workflows/*.yaml` |

---

## 维度 1：通信层韧性

### 现状

- **Hub 聊天 / 群聊**：SSE 流式；v2 在 `api.ts` 实现 `readStreamWithAbort` + `reader.cancel()`（L438–471），与 v1 `ui-core.js` 同模式。
- **Adapter 隔离**：`FRAMEWORK-FREEZE.md` §2.2 要求 `stream_fanout` 仅消费规范化 `thinking` SSE；`backend/adapters/opencode/` 独立目录。
- **群事件**：`EventSource /api/groups/{id}/events`（v1 `group.js:250`，v2 `api.ts:416`）。
- **项目观测**：`EventSource` 项目 stream + interaction events（v2 `api.ts:749-786`）。
- **圆桌**：`roundtable_runtime.py` + 群 SSE 多阶段事件（v2 `GroupsSection.tsx` 处理 `roundtable_*`）。

### 差距

| 项 | 严重度 | 说明 |
|----|--------|------|
| Hub 单进程 | 中 | 无多实例负载均衡；重启依赖 `_reconcile_stale_kernel_runs` |
| v2 无 per-agent SSE | 低 | v1 `agents/{id}/events`；v2 改全局 `agentChatStream` |
| Hub 单进程重启 | 低 | `_reconcile_stale_kernel_runs` 已收拢 ghost running |

### 改进方向（P2+）

- P2.1 API 拆分后，SSE 路由与 REST 分域，便于独立超时/重连策略。
- 保持 adapter 边界；token/usage 走 `TokenUsageSink` 契约（`token_usage.py` 已落地抽象）。

---

## 维度 2：路由模块化

### 现状

- **单体 Hub（拆分中）**：`server.py` **~1540 行**（自 ~1911 削减）；projects/agents 部分已提取至 `routes/`；仍承载 groups、chat、workflows、config 等。
- **已拆分**：`observability_api.py`（291 行，只读 obs）、`skills_api.py`（Skill drafts/matrix）。
- **内核独立**：`run_kernel.py` / `Process` 不依赖 Hub 进程（`ARCHITECTURE.md` §1）。

### 差距

| 项 | 严重度 | 证据 |
|----|--------|------|
| 上帝文件 | 高 | `server.py` 占 Hub 路由绝大部分 |
| 跨域耦合 | 中 | 同文件内 chat + 编排 + 管理 CRUD |
| deps 薄 | 低 | `deps.py` 仅注入，无域边界 enforcement |

### 改进方向

- P2.1 `api-split-plan.md`：按 obs / projects / groups / agents / config 切 router。
- 目标：`server.py` < 500 行（装配层），每域 < 400 行。

---

## 维度 3：前端功能完整度

### 现状

- **双前端并存**：v1 `frontend/`（13 JS 模块 + `index.html`）；v2 `frontend-v2/`（9 pages + 7 sections + React Router）。
- **P0 覆盖**：矩阵 **31/31** P0 行 v1、v2 均可用（见 `v1-v2-feature-matrix.md`）。
- **v2 增值**：DAG 组件化、Gate 失败列表、Skill 草案页、圆桌 UI、群讨论设置。

### 差距

| 项 | P级 | v2 状态 |
|----|-----|---------|
| sync-task-types / suggest-* | P1 | API 有，UI 无 |
| init / demo 演示 | P2 | 仅 v1 |
| workspace timeline.js | P2 | 仅 v1 |

### 改进方向

- P2.2 v2 迁移计划以矩阵 P1 缺口为 scope。
- P3.2 执行后 P3-G6 轻量确认 + P4 完整验收。

---

## 维度 4：部署确定性

### 现状

- **启动**：`./run.sh start`（`ARCHITECTURE.md` §1 流 A）。
- **封板验证**：`FRAMEWORK-FREEZE.md` 记录 `pytest backend -q` + `run_regression.sh --suite v1`。
- **路径单一来源**：`backend/hub/paths.py` `MYTEAM_ROOT` 解析。
- **依赖**：项目 `venv/`；SQLite 单文件 `business/tasks/state.db` 可拷贝。
- **REG 脚本**：`scripts/regression/reg_platform_v3_e2e_baseline.py` 双跑 PASS（2026-06-14）。

### 差距

| 项 | 说明 |
|----|------|
| pytest 全绿 | **589/594 passed, 0 failed**（2026-06-14 终验）；封板基线已扩张并恢复绿灯 |
| 无容器/compose 一等公民 | 部署文档分散在 README / run.sh |
| frontend-v2 需 build | `frontend-v2/dist` 产物需构建步骤 |

### 改进方向

- P1-G6 已满足：`pytest backend -q` → 0 failed（594 passed，2026-06-14）。
- ops：document 单用户本地标准路径（venv + state.db + business/config gitignore 清单）。

---

## 维度 5：成本可观测性

### 现状

- **Store 计量**：`interaction.tokens` 字段 + `Store.tokens_total(project_id)`（E2E 基线 Test 2 验证 200 tokens）。
- **契约层**：`backend/common/token_usage.py` — `TokenUsageSink` Protocol + `StoreTokenUsageSink`。
- **Obs API**：`/api/obs/projects/{id}/cost`、`overview` 含 budget 字段（v2 `ProjectOverview` types）。
- **测试**：`backend/common/tests/test_token_usage.py` 存在。
- **双通道**：SQLite 真相 + `deliverables/` 文件（`ARCHITECTURE.md` §3）。

### 差距

| 项 | 说明 |
|----|------|
| Adapter → sink 未全接线 | P2.3a/2.3b 契约已写，功能性三步验收在 P3-G4 |
| 前端 token 展示 | v2 有 `tokens`/`budget` 类型，SSE 实时 token 展示待 P3 验证 |
| 无外部账单集成 | 无 OpenAI/Cursor 用量 API 对账 |

### 改进方向

- 完成 P2.3 store-token-metering-contract + P3 token adapter 功能性验收。
- 保持 `observability_api.py` 只读，避免 Hub 写路径绕过 Store。

---

## 维度 6：行业差异化

### 现状（myteam 定位）

- **协作模型**：DAG 编排，Process 调度，Agent **不互聊**（`ARCHITECTURE.md` §3）。
- **Gate 契约**：`submit_result` + deterministic Gate，非 LLM 自评为主。
- **Strategy 增量**：`business/workflows/*.yaml`（13 个）+ Skill 目录。
- **适配器**：opencode + claude 双后端（`FRAMEWORK-FREEZE.md`）。
- **竞品对比详表**：见 [`competitor-baseline.md`](./competitor-baseline.md)。

### 差距

| 项 | 说明 |
|----|------|
| 生态规模 | CrewAI/LangGraph 社区与文档体量更大 |
| Human-in-the-loop | LangGraph 一等公民；myteam 以 Gate/review 节点代替 |
| 多租户 / 云托管 | 未提供；单用户本地为主 |

### 改进方向

- 产品叙事强化：**确定性编排 + 可验收交付物 + 中文 workflow 资产**。
- 不盲目对标 Crew「角色互聊」；保持 DAG 非互聊 invariant（封板）。

---

## 六维评分卡（0–10，诊断用）

| 维度 | 分数 | 一句话 |
|------|------|--------|
| 通信层韧性 | 7 | SSE/abort 成熟；单 Hub 实例 |
| 路由模块化 | 5 | server.py ~1540 行；Wave 2 projects/agents 已拆 |
| 前端功能完整度 | 8 | P0 双端齐全；P1 suggest 系列缺 v2 |
| 部署确定性 | 8 | REG 双跑 PASS；pytest 0 failed |
| 成本可观测性 | 6 | Store+契约有；adapter 全链待 P3 |
| 行业差异化 | 7 | DAG+Gate 清晰；生态体量弱于头部框架 |

**平均**：6.7 / 10 — P1 6/6 PASS；P2 方案完成；P3 执行与回归已 PASS；P4 验收见 `p4-gate-record.md`。
