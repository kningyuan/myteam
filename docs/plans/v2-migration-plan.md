# v2 功能迁移方案（P2.2）

> **Workflow**：`myteam-platform-v3` · 任务 `p2-2-v2-migration-plan`  
> **输入真源**：[`docs/assessments/v1-v2-feature-matrix.md`](../assessments/v1-v2-feature-matrix.md)  
> **API 边界**：[`docs/plans/api-split-plan.md`](./api-split-plan.md)  
> **生成时间**：2026-06-14（代码库扫描）

---

## 1. 目标状态

- **P0 核心旅程**：frontend-v2 与 v1 在功能上等价，用户可完成「项目编排 → 私聊 → 群组 → 管理 → Workflow → 设置 → Dashboard 观测」全流程。
- **P1 增强**：v2 Manage 暴露 v1 已有的 LLM 辅助入口（sync/suggest）；私聊多会话路径与 v1 对齐或文档化替代方案。
- **P2 演示/遗留**：明确「不迁移 / 运维脚本替代」清单，避免 P4 验收歧义。
- **v2 增值项**：Skill L3、圆桌设置、Gate 失败组件等 v2 独有能力列入 P4 验收加分项，不要求 v1 对等。

---

## 2. 当前差距（矩阵实证）

来源：[`v1-v2-feature-matrix.md`](../assessments/v1-v2-feature-matrix.md) §2–§4。

### 2.1 P0 缺口

| 指标 | 值 |
|------|-----|
| P0 行总数 | **31** |
| P0 v2 可用 | **31/31** |
| **P0 缺口** | **0** |

**结论**：无 P0 阻塞项。P3.2 执行 stub 的重点是 **P1 补齐 + 验收证据**，而非紧急补洞。

### 2.2 P1 缺口（建议 P3.2 范围）

| # | 功能 | v1 证据 | v2 状态 | API 是否已有 |
|---|------|---------|---------|--------------|
| 1 | sync-task-types | `manage.js:127` | ❌ 无 UI | `POST /api/agents/sync-task-types`（`server.py`） |
| 2 | suggest-task-types | `manage.js:422` | ❌ 无 UI | `POST /api/agents/suggest-task-types` |
| 3 | suggest-id | `manage.js:492` | ❌ 无 UI | `GET /api/agents/suggest-id` |
| 4 | task-types/suggest | `manage.js:342` | ❌ 无 UI | `POST /api/task-types/suggest` |
| 5 | 多会话侧栏 `/agents/{id}/chats` | `chat.js:122` | ❌ 无 | `GET /api/agents/{id}/chats` |
| 6 | per-agent SSE `/agents/{id}/events` | `chat.js:285` | ⚠️ 路径不同 | v2 用 `agentChatStream.ts` 全局流 |

### 2.3 P2 / 仅 v1 项（可不迁移）

| 功能 | 建议 |
|------|------|
| `POST /api/init` | 收敛为 `./run.sh` / 文档 onboarding，不建 v2 页 |
| `POST /api/demo` | 同上或保留 v1 演示入口 |
| `frontend/timeline.js` | v2 用 `obs/events` + `ProjectExecTree` 替代 |

### 2.4 v2 独有（保留并验收）

- Skill 草案页：`SkillsSection.tsx` · `/skills/:draftId`
- 圆桌设置 / 取消群聊：`GroupsSection.tsx` · `api.ts:484-918`
- Gate 失败结构化展示：`GateFailureList.tsx`
- Task 质量卡片：`ProjectTaskQualityCard.tsx`

---

## 3. 迁移阶段

### Phase A — P0 确认（当前，~0 人天）

**目标**：矩阵 P0 100% 有页面 + API 证据（已完成）。

| 动作 | 证据 |
|------|------|
| 逐条核对 P0 行 | 矩阵 §2 行 1–11、13–15、19–20、23–26、30–31、34 |
| v2 API 封装 | `frontend-v2/src/lib/api.ts` 52 函数 · ~45 HTTP 路径 |
| 回归 smoke | `pytest backend -q` · v2 手动走核心旅程 |

**出口**：P3.2b 轻量确认可直接标注 P0「已补齐」。

### Phase B — P1 Manage 辅助（P3.2 主工作量，~2–3 人天）

**目标**：在 `ManageSection.tsx` 补齐 4 个 suggest/sync 入口，复用已有 Hub API。

| 步骤 | 交付 |
|------|------|
| B1 | `api.ts` 增加 `syncAgentTaskTypes`、`suggestAgentTaskTypes`、`suggestAgentId`、`suggestTaskType` |
| B2 | Agents 管理 tab：「同步 task types」「LLM 建议 task types」按钮 + loading/error |
| B3 | Task types 创建流：「LLM 起草」按钮，对接 `POST /api/task-types/suggest` |
| B4 | Create Agent 流：接入 `suggest-id` / `suggest-task-types`（对齐 v1 `manage.js:422,492`） |

**验收**：Manage 四入口可触发并成功展示结果；不要求 LLM 质量达标。

### Phase C — P1 私聊路径（可选，~1–2 人天）

**目标**：评估 v2 `agentChatStream` 是否满足多会话需求。

| 选项 | 说明 |
|------|------|
| C-保留 | 文档化：v2 用 agent 列表 + 归档/隐藏集代替 v1 多 chat 侧栏 |
| C-补齐 | 恢复 `/agents/{id}/chats` 侧栏 + 可选 per-agent SSE |

**建议**：Phase B 优先；Phase C 仅在产品明确要求 v1 对等时做。

### Phase D — P4 完整验收（P4 产品任务）

**目标**：P0「功能可用」+ 核心旅程可完成（相对 P3.2b「功能存在」）。

| 旅程 | 检查点 |
|------|--------|
| 发起项目 → run → SSE → 交付物 | `ProjectsSection` + `ProjectDetailPanel` |
| 私聊流式 | `ChatSection` + `ThinkingStream` |
| 群聊 / 圆桌 | `GroupsSection` |
| 管理 CRUD | `ManageSection` 全 tab |
| Dashboard token | `DashboardPage` · `GET /api/obs/summary` |

---

## 4. 验收指标

| ID | 指标 | 标准 |
|----|------|------|
| V2-M1 | P0 完整度 | 矩阵 P0 行 100% v2 ✅（已达成） |
| V2-M2 | P1 Manage 辅助 | Phase B 四 API 在 v2 UI 可触发 |
| V2-M3 | API 边界一致 | 新 UI 调用路径与 [`api-split-plan.md`](./api-split-plan.md) 域划分一致 |
| V2-M4 | 轻量确认 | `p3-2-product-light-confirm.md` 标注 P0 + 证据路径 |
| V2-M5 | 完整验收 | `platform-v3-product-acceptance.md` P0 旅程 PASS |
| V2-M6 | 单元测试 | `pytest backend -q` → 0 failed |

---

## 5. 风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| P1 API 在 monolith `server.py`，拆分后路径变更 | 中 | Phase B 经 `api.ts` 单点封装；跟随 P3.1 Wave 2–5 更新 |
| suggest 依赖外部 CLI/LLM | 低 | UI 仅保证调用链；失败展示 error 即可 |
| P0=100% 导致 P3.2 被跳过 | 中 | 本方案明确 P1 为 P3.2 主范围；Gate 文档化 |
| v2 独有功能无 v1 对照 | 低 | 列入 P4 增值项，不阻塞 PASS |

---

## 6. 人天估算（建议）

| 阶段 | 人天 | 负责人 |
|------|------|--------|
| Phase A 确认 | 0 | @product |
| Phase B Manage P1 | 2–3 | @developer |
| Phase C 私聊（可选） | 1–2 | @developer |
| Phase D 验收 | 0.5 | @product |
| **合计（不含 C）** | **2.5–3.5** | |

---

## 7. 与 Workflow v3 映射

| 任务 | 本文章节 |
|------|----------|
| P3.2 v2 功能 exec | §3 Phase B/C |
| P3.2b 轻量确认 | §3 Phase A · §4 V2-M4 |
| P4 产品验收 | §3 Phase D · §4 V2-M5 |
