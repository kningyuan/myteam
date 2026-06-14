# group_manager 直写收拢方案（P2.5）

> **Workflow**：`myteam-platform-v3` · 任务 `p2-5-group-direct-write`  
> **审计真源**：[`docs/assessments/sqlite-direct-write-audit.md`](../assessments/sqlite-direct-write-audit.md)  
> **扩展审计**：[`docs/assessments/sqlite-store-audit.md`](../assessments/sqlite-store-audit.md)（§3 部分条目已过时，以本文为准）  
> **生成时间**：2026-06-14（代码库复扫）

---

## 1. 目标状态

- **生产代码**：除 `backend/common/store.py` 外，无任何 `_conn.execute` / `sqlite3.connect` 直写 SQLite。
- **group_manager**：群组状态仅存 `business/config/groups.json`，不触碰 `state.db`。
- **Hub API**：观测与列表经 `Store` 公开方法或 `common/observability.py`，不持有 `store._conn`。
- **测试**：允许探针式直读 DB，但应逐步改为 Store API 断言。

---

## 2. 当前状态（2026-06-14 复扫）

### 2.1 生产 `_conn.execute`：**0 处**

扫描：`rg '_conn\.execute' backend --glob '*.py'`，排除 `store.py`。

| 文件 | 命中 | 分类 |
|------|------|------|
| `backend/common/store.py` | 全部合法 | Store 实现 |
| `backend/common/tests/test_store.py:187,192` | 2 | **测试 bypass** |
| `backend/hub/api/server.py` | **0** | ✅ 已收拢（旧审计 L298/378/443 已不存在） |
| `backend/common/agent_port.py` | **0** | ✅ |
| `backend/common/workspace_gc.py` | **0** | ✅ |
| `backend/base/group_manager.py` | **0** | ✅ 仅用 JSON 文件 |

### 2.2 生产 `sqlite3.connect`：**0 处**

| 文件 | 分类 |
|------|------|
| `backend/common/tests/test_process.py:1199` | **测试 bypass** |
| `backend/common/tests/test_regression_archive.py:22` | **测试 bypass** |

### 2.3 group_manager 持久化（实证）

```python
# backend/base/group_manager.py
GROUPS_FILE  # hub.paths → business/config/groups.json

def _load_groups() -> dict:   # json.load
def _save_groups(data: dict): # json.dump
```

**结论**：group_manager **从未**在现行代码中直写 SQLite；P1.3 审计中的「group_manager bypass」为历史风险项，**已不适用**。群组与 Store 的关联仅通过 `project_id` 字段逻辑绑定，无 DB 直写。

---

## 3. 已完成工作摘要

| 项 | 说明 | 证据 |
|----|------|------|
| Hub server 直写移除 | obs/列表 SQL 改走 Store/observability | `rg '_conn.execute' backend/hub` → 0 |
| agent_port 直写移除 | reconcile 经 `finalize_interaction` / Store API | 无 `_conn` 引用 |
| workspace_gc 直写移除 | GC 经 Store 或文件系统 | 无 `_conn` 引用 |
| kernel_run 收拢 | `_KERNEL_RUNS` 内存 dict 已删 | `kernel_run.py` + Store meta |
| 审计脚本 | `scripts/audit_sqlite_direct_writes.py` | 可 CI 回归 |

---

## 4. 剩余 bypass（仅测试）

| 文件:行 | 操作 | 收拢建议 |
|---------|------|----------|
| `test_store.py:187-193` | `store._conn.execute("SELECT COUNT(*) FROM run_event …")` | 新增 `Store.count_run_events(project_id_prefix=)` 或断言 `list_run_events` 为空 |
| `test_process.py:1199` | 临时 `sqlite3.connect` 探针 | 改用 `Store(tmp_path/"state.db")` 公开 API |
| `test_regression_archive.py:22` | 临时 `sqlite3.connect` | 同上 |

**优先级**：低（不阻塞 PG 迁移 / P2 Gate）。可在 P3.5 回归阶段顺带清理。

---

## 5. 原 P2.5 直写清单（历史 → 现状）

> 供 P2.4 PG 迁移追溯；2026-06-13 审计 9 处 → 2026-06-14 **生产 0 处**。

| 历史路径（sqlite-store-audit §3） | 2026-06-14 状态 |
|-----------------------------------|-----------------|
| `hub/api/server.py:298,378,443` | ✅ 已移除 |
| `common/agent_port.py:481` | ✅ 已移除（现为 reconcile 逻辑，无 SQL） |
| `common/workspace_gc.py:86` | ✅ 已移除 |
| `common/tests/test_store.py:151,156` | ⚠️ 现为 :187,:192，仍测试 bypass |

---

## 6. 验收指标

| ID | 指标 | 标准 | 2026-06-14 |
|----|------|------|------------|
| GDW-1 | 生产 `_conn.execute` bypass | 0 | ✅ PASS |
| GDW-2 | 生产 `sqlite3.connect` bypass | 0 | ✅ PASS |
| GDW-3 | group_manager 无 Store 直写 | JSON only | ✅ PASS |
| GDW-4 | 审计脚本可复现 | `python scripts/audit_sqlite_direct_writes.py` | 待 CI 挂载 |
| GDW-5 | 测试 bypass | ≤3 处，有收拢计划 | ✅ 已文档化 §4 |

---

## 7. 风险评估

| 风险 | 缓解 |
|------|------|
| 新代码 reintroduce bypass | PR review + audit 脚本 CI |
| 测试 `_conn` 探针掩盖 API 缺口 | 收拢为 Store 方法 |
| sqlite-store-audit §3 误导 | 以本文 + sqlite-direct-write-audit 为准 |

---

## 8. 人天估算

| 项 | 人天 |
|----|------|
| 生产收拢 | **0**（已完成） |
| 测试 bypass 清理 | 0.5 |
| audit 脚本 CI 集成 | 0.5 |

---

## 9. 与 Workflow v3 映射

| 下游 | 输入 |
|------|------|
| P2.4 PG 迁移 | §2 生产 bypass=0，可启动 Backend 抽象 |
| P3.4 PG exec | 无直写阻塞 |
| P2 Gate P2-G6 | 本文即直写方案交付物（路径 `group-direct-write-plan.md`） |
