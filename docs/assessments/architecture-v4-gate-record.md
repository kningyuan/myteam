# Architecture v4 边界闸门记录

> **记录时间**：2026-06-14 post-refactor  
> **Workflow**：`myteam-architecture-v4` · 任务 `arch-gate`  
> **诊断基线**：[`architecture-v4-diagnosis.md`](./architecture-v4-diagnosis.md)  
> **关系**：与 v3 P4 独立签发；v4 PASS 不替代 v3 final-gate

---

## 总览

| 结果 | 数量 |
|------|------|
| **PASS** | **5** / 7 |
| **FAIL** | **2** / 7 |
| **v4 Gate 整体** | **CONDITIONAL PASS** — StoreBackend、前端端口、契约 parity、全量 pytest 已绿；server.py 行数与 Wave 5 收尾未达标 |

---

## 逐项验收清单

| # | 验收项 | 标准 | 证据 | 结果 | 备注 |
|---|--------|------|------|------|------|
| **V4-1** | `server.py` 行数 | < 400（仅装配层） | `wc -l` → **865** | **FAIL** | Wave 3–4 已提取 chat/groups/config；agents CRUD + task-types + delivery-templates 仍驻留 |
| **V4-2** | StoreBackend Protocol | 存在且 Store 委托 | `store_backend.py` 49 行；`test_store_backend.py` | **PASS** | `SqliteStoreBackend` 默认实现 |
| **V4-3** | API Wave 3–5 路由提取 | server 遗留仅 SPA/health/obs-agents | routes/ 9 域 + obs + skills；server 仍 37 `@app` 路由 | **FAIL** | 功能性拆分完成；**行数/遗留 handler** 未清零 |
| **V4-4** | 前端 pages/components 边界 | 零 `fetch(`、零 `/api/` REST 字符串 | rg → fetch **0**；REST 字符串 **0** | **PASS** | import `@/lib/api/*` 不计违规 |
| **V4-5** | `api.ts` barrel | < 50 行或已删除 | **2 行** re-export | **PASS** | 域模块 1224 行承载全部路径 |
| **V4-6** | FE↔Hub route parity | 100% pass | `test_fe_hub_route_contract.py` **3/3** | **PASS** | 覆盖 projects/chat/groups/config + 全 lib/api |
| **V4-7** | pytest backend | 0 failed | `pytest backend -q` → **602 passed** | **PASS** | 含新增 3 个 parity 用例 |

---

## 契约测试证据（V4-6）

| 套件 | 结果 |
|------|------|
| `test_fe_hub_route_contract.py` | **3 passed** |
| `test_priority_modules_contribute_routes` | PASS — projects/chat/groups/config 均有路由产出 |
| `test_fe_hub_route_parity` | PASS — 77 FE 路径全部匹配 Hub |
| `test_priority_module_paths_registered` | PASS — priority 模块 ≥20 路径 |

---

## FAIL 项说明

### V4-1 — server.py 仍 865 行

| 项 | 现状 | 目标 |
|----|------|------|
| 行数 | 865 | < 400 |
| 遗留域 | agents CRUD/detail/files/manage/notify/events/create、suggest-id、task-types CRUD、delivery-templates CRUD、projects deliverable/cancel/resume | 提取至 routes/ 或 hub/services |

### V4-3 — Wave 5 遗留 handler

已提取：chat、groups、config、workflows、projects（部分）、channels、jobs、workspace_events、obs、skills。

仍驻留 `server.py`：agents 管理面、task-types、delivery-templates、部分 projects 生命周期。

---

## Adapter 登记（信息项）

| Backend | 状态 | 实现 |
|---------|------|------|
| claude | 生产 | `adapters/claude/adapter.py` |
| opencode | 生产 | `adapters/opencode/adapter.py` |
| codex | stub | `PlannedCLIAdapter` in `stub_cli.py` |
| cursor | stub | `PlannedCLIAdapter` in `stub_cli.py` |

---

## 签发结论

**Architecture v4：CONDITIONAL PASS**

- 可合并/integration-test 任务：**完成**
- 阻塞 full PASS：**V4-1**（server.py < 400）、**V4-3**（server 遗留 handler 清零）
- 建议下一迭代：提取 task-types + delivery-templates + agents CRUD → `routes/`，复跑 gate
