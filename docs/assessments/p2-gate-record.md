# P2 阶段闸门记录

> **Workflow**：`myteam-platform-v3` · 任务 `p2-gate`（@main）  
> **Gate 定义**：[`platform-v3-gates.md#p2-gate`](../assessments/platform-v3-gates.md#p2-gate)  
> **签发时间**：2026-06-14  
> **结论**：**PASS** — 可进入 P3 执行 stub

---

## 六要素合规（修正项 7）

每个方案交付物须含：目标状态 · 当前差距 · 实施步骤 · 验收指标 · 风险评估 · 人天估算。

| 交付物 | 六要素 | 判定 |
|--------|--------|------|
| 全部 P2 方案 | 均已包含 | ✅ |

---

## P2 交付物清单

| Gate ID | 任务 | 交付物路径 | 状态 | 证据摘要 |
|---------|------|------------|------|----------|
| P2-G1 | P2.1 API 拆分 | [`docs/plans/api-split-plan.md`](./plans/api-split-plan.md) | **PASS** | Mermaid 路由边界图；channels 已提取；`deps.py`/`errors.py` |
| P2-G2 | P2.2 v2 迁移 | [`docs/plans/v2-migration-plan.md`](./plans/v2-migration-plan.md) | **PASS** | P0 缺口 0/31；P1 六条补齐计划；Phase A–D |
| P2-G3 | P2.3a token 契约 | [`docs/plans/store-token-adapter-plan.md`](./plans/store-token-adapter-plan.md) §Part A | **PASS** | `token_usage.py` 已实现；Protocol + StoreTokenUsageSink；`contracts.Meta.tokens` |
| P2-G4 | P2.3b adapter 方案 | [`docs/plans/store-token-adapter-plan.md`](./plans/store-token-adapter-plan.md) §Part B | **PASS** | 功能性三步验收；opencode/claude 实证；SSE 路径图；codex/cursor 新建计划 |
| P2-G5 | P2.4 PG 迁移 | [`docs/plans/pg-migration-plan.md`](./plans/pg-migration-plan.md) | **PASS** | 单用户 SQLite 推荐；PG opt-in；Store Backend 拆分步骤 |
| P2-G6 | P2.5 直写收拢 | [`docs/plans/group-direct-write-plan.md`](./plans/group-direct-write-plan.md) | **PASS** | 生产 `_conn.execute` = **0**；测试 bypass 3 处已列 |

**注**：Workflow YAML 原路径 `store-token-metering-contract.md` / `group-manager-direct-write-inventory.md` 已合并为上述实际文件名，内容覆盖 P2-G3/G4/G6 要求。

---

## 逐项 Gate 勾选

### P2-G1 API 拆分

- [x] 含路由边界图（Mermaid）
- [x] 供 P2.3a 引用（store-token-adapter-plan 已引用）
- [x] 目标 / 差距 / 步骤 / 验收 / 风险 / 人天

### P2-G2 v2 迁移

- [x] P0 补齐范围与 [`v1-v2-feature-matrix.md`](../assessments/v1-v2-feature-matrix.md) 一致（P0=100%，无缺口）
- [x] P1 缺口明确（6 条）
- [x] 六要素完整

### P2-G3 token 契约

- [x] `TokenUsageSink` 抽象定义（代码 + 文档 Part A）
- [x] `Store.bump_interaction_tokens` 语义 documented
- [x] 修正项 3「先契约后实施」：契约代码已存在

### P2-G4 adapter 方案

- [x] 验收指标为**功能性三步**（非覆盖率 %）
- [x] 各 CLI adapter 路径（opencode/claude 实证；codex/cursor 待建）
- [x] SSE token 事件 Hub 路径 documented

### P2-G5 PG 迁移

- [x] 输入含 P2.5 直写结论（生产 bypass=0）
- [x] 单用户 vs 多实例诚实结论
- [x] Store 接口向后兼容约束

### P2-G6 直写清单

- [x] 每条 bypass 含文件 / 操作 / 收拢建议（§4 测试项 + §5 历史）
- [x] group_manager 状态：JSON only，无 SQLite 直写

---

## DAG 约束验证（修正项 3）

| 约束 | 状态 |
|------|------|
| 2.3a 依赖 2.1 路由边界图 | ✅ store-token-adapter-plan 引用 api-split-plan |
| 2.3b 依赖 2.3a | ✅ 同文件 Part A → Part B |
| 2.4 依赖 2.3a + 2.5 | ✅ pg-migration-plan 引用两者 |
| 2.3b 与 2.4 可并行 | ✅ 文档独立，无串行阻塞 |

---

## 代码库交叉验证（扫描 2026-06-14）

| 断言 | 结果 |
|------|------|
| `backend/common/token_usage.py` 存在 | ✅ 64 行 |
| `StoreTokenUsageSink` 接入 `AgentPort` | ✅ `agent_port.py:110` |
| Adapters: opencode + claude | ✅ `backend/adapters/` |
| Adapters: codex + cursor | ❌ 未实现（方案已标注 P3） |
| 生产 SQLite bypass | ✅ 0（`rg '_conn.execute' backend` 除 store.py） |
| group_manager SQLite | ✅ 0（仅 `groups.json`） |
| P0 v2 完整度 | ✅ 31/31（矩阵 §4） |

---

## 遗留 / 非阻塞项（带入 P3）

| 项 | 负责 | 说明 |
|----|------|------|
| P1 Manage UI 补齐 | P3.2 | v2-migration-plan Phase B |
| codex/cursor adapter | P3.3 | store-token-adapter-plan §B.4.3–4 |
| 私聊 token sink | P3.3 可选 | 编排路径已通，私聊未写 Store |
| 测试 bypass 3 处 | P3.5 | group-direct-write-plan §4 |
| PG Backend 抽象 | P3.4 或「暂不切换」 | pg-migration-plan Step 0 |
| api-split Wave 2–5 | P3.1 | server.py ~1750 行待继续拆分 |

---

## 签发

| 字段 | 值 |
|------|-----|
| **Gate 状态** | **PASS** |
| **可进入** | P3 执行 stub（p3-1 … p3-5） |
| **签发依据** | 六份 P2 方案文档 + 代码库扫描 |
| **FAIL 条件** | 未触发 |

---

## 证据链接索引

- P1 矩阵：[`v1-v2-feature-matrix.md`](../assessments/v1-v2-feature-matrix.md)
- P1 SQLite：[`sqlite-store-audit.md`](../assessments/sqlite-store-audit.md)
- 直写快照：[`sqlite-direct-write-audit.md`](../assessments/sqlite-direct-write-audit.md)
- Gate 定义：[`platform-v3-gates.md`](../assessments/platform-v3-gates.md)
- Workflow：[`business/workflows/myteam-platform-v3.yaml`](../../business/workflows/myteam-platform-v3.yaml)
