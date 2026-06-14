# SQLite → PostgreSQL 迁移方案（P2.4）

> **Workflow**：`myteam-platform-v3` · 任务 `p2-4-pg-migration-plan`  
> **输入**：[`docs/assessments/sqlite-store-audit.md`](../assessments/sqlite-store-audit.md) · [`group-direct-write-plan.md`](./group-direct-write-plan.md)  
> **约束**：Store 对外接口向后兼容；不破坏 FRAMEWORK-FREEZE 内核语义  
> **生成时间**：2026-06-14（代码库扫描）

---

## 1. 目标状态

- **默认部署**：单用户本地继续使用 **SQLite WAL**（`business/tasks/state.db`），零额外依赖。
- **可选 PG 后端**：通过环境变量切换，`Store()` 对外方法签名不变；Hub + kernel 无感。
- **迁移可逆**：SQLite 导出 → PG 导入脚本；回滚切回 `MYTEAM_DB_BACKEND=sqlite`。
- **直写清零前提**：生产代码无 Store bypass（已达成，见 group-direct-write-plan）。

---

## 2. 当前差距

### 2.1 存储现状（实证）

| 项 | 值 | 证据 |
|----|-----|------|
| 实现 | 单类 `Store` + `sqlite3` | `backend/common/store.py`（~1099 行） |
| 路径 | `business/tasks/state.db` | `default_db_path()` |
| 大小 | ~12 MB · 9 projects | P1.3 审计 |
| journal_mode | **wal** | `PRAGMA journal_mode` |
| PG 代码 | **0** | `rg postgres\|asyncpg\|psycopg backend` → 无匹配 |
| Store 抽象 | **部分** | 全方法挂 `Store` 类，无 `Backend` 接口层 |

### 2.2 何时需要 PG（诚实结论）

| 场景 | 需要 PG？ | 理由 |
|------|-----------|------|
| **单用户本地**（当前主场景） | **否** | WAL 已支持 Hub 读 + kernel 写；12 MB 远未触顶 |
| 多 Hub 实例水平扩展 | **是** | 单文件 SQLite 无法跨主机共享 |
| 团队远程协作 / 7×24 Hub | **是** | 连接池 + 行级锁 |
| 仅 token/obs 读放大 | **否** | 只读 API 已分离（`observability_api.py`） |

**v3 建议**：P2 出方案；P3/P4 **测试环境验证或记录「暂不切换」**（platform-v3-gates P4-7）。

### 2.3 直写 bypass 状态

2026-06-14 复扫（`scripts/audit_sqlite_direct_writes.py` 等价 rg）：

| 类别 | 生产代码 | 测试 |
|------|----------|------|
| `_conn.execute` bypass | **0** | `test_store.py:187,192` |
| `sqlite3.connect` bypass | **0** | `test_process.py:1199`, `test_regression_archive.py:22` |

P2.5 收拢已完成；PG 迁移不再被 bypass 阻塞。

---

## 3. Store 抽象（已有 vs 待建）

### 3.1 已有（可复用）

- **单一真相 API**：`upsert_project`, `create_interaction`, `bump_interaction_tokens`, `append_run_event`, …
- **Token 契约**：`TokenUsageSink` / `StoreTokenUsageSink` 与 backend 无关
- **Obs 只读层**：`common/observability.py` 仅依赖 Store 方法，不触 SQL 方言
- **配置分离**：`backend/store/` 包处理 JSON 配置，与 `common/store.py` 运行态分离

### 3.2 待建（P3.4）

```
common/store/
  __init__.py      # Store = get_store() 工厂
  base.py          # StoreBackend Protocol（或 ABC）
  sqlite.py        # 现有 store.py 逻辑迁入
  postgres.py      # psycopg3 或 asyncpg 实现
  migrate.py       # sqlite → pg 一次性导入
```

**最小 Protocol 面**（首批 15 方法，覆盖编排 E2E）：

- project / task / interaction CRUD + 状态机
- `append_run_event` / `list_run_events`
- `bump_interaction_tokens`
- `list_projects` / transaction 边界（`with conn:`）

其余 message / memory / conversation 方法 Wave 2 迁移。

---

## 4. 实施步骤

### Step 0 — 决策门（P4-7）

| 决策 | 动作 |
|------|------|
| 暂不切换 | 在 `pg-migration-change-log.md` 记录理由（单用户） |
| 测试验证 | 继续 Step 1–6 |

### Step 1 — 引入 Backend 接口（~2 人天）

1. 从 `store.py` 提取 `SqliteStoreBackend`，`Store` 变为薄门面委托。
2. 所有 `self._conn.execute` 留在 `sqlite.py`；门面零 SQL。
3. `pytest backend/common/tests/test_store.py` 全绿。

### Step 2 — PG 实现（~3–4 人天）

1. 新增 `postgres.py`：`CREATE TABLE` DDL 与 SQLite schema 对齐（类型映射：TEXT→VARCHAR, JSON→JSONB）。
2. 环境变量：
   - `MYTEAM_DB_BACKEND=sqlite|postgres`（默认 sqlite）
   - `MYTEAM_DATABASE_URL=postgresql://...`
3. 连接池：`psycopg_pool` 或单连接（单 Hub 足够）。

### Step 3 — 迁移脚本（~1 人天）

```bash
# 示意
python -m common.store.migrate \
  --from business/tasks/state.db \
  --to "$MYTEAM_DATABASE_URL" \
  --verify row-counts
```

- 表顺序：project → task → interaction → run_event → memory → …
- 校验：行数 + 抽样 hash + `interaction.tokens` 总和

### Step 4 — 双写/对比（可选，~1 人天）

- 测试环境：写 SQLite，异步镜像 PG，对比 obs API 输出。
- 单用户可跳过，直接 cutover 测试库。

### Step 5 — Hub + kernel 切换（~0.5 人天）

1. `Store()` 工厂读 env。
2. `run_kernel` subprocess 继承 env。
3. `./run.sh` 文档增加 PG docker-compose 示例（可选）。

### Step 6 — 回滚预案（~0.5 人天）

1. 停 Hub → 导出 PG → 写回 SQLite（或保留 SQLite 快照）。
2. `MYTEAM_DB_BACKEND=sqlite` 重启。
3. P4 ops：`platform-v3-ops-verify.md` dry-run 记录。

---

## 5. 验收指标

| ID | 指标 | 标准 |
|----|------|------|
| PG-M1 | 接口兼容 | 现有 `test_store.py` + `test_platform_e2e_baseline.py` 在 PG 后端 PASS |
| PG-M2 | obs 一致 | `obs/summary` · `project_overview` SQLite vs PG 同数据一致 |
| PG-M3 | 默认不变 | 无 env 时仍用 `business/tasks/state.db` |
| PG-M4 | 迁移脚本 | sqlite → pg → 行数校验 100% |
| PG-M5 | 回滚 | 文档化步骤可执行 |
| PG-M6 | bypass | 生产 `_conn.execute` bypass = 0（已满足） |

---

## 6. 风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| 过早 PG 增加运维负担 | 高（单用户） | 默认 sqlite；PG 显式 opt-in |
| SQLite 特有语法（`MAX()` upsert） | 中 | PG 用 `GREATEST` + `ON CONFLICT` |
| FTS5 message 索引 | 中 | PG 用 `tsvector` 或暂禁 PG 下 FTS |
| 大 blob run_event payload | 低 | JSONB 兼容 |
| 测试覆盖不足 | 中 | E2E 双跑 + obs 对比 |

---

## 7. 人天估算

| 阶段 | 人天 | 备注 |
|------|------|------|
| Step 1 Backend 提取 | 2 | P3.4 必做 |
| Step 2 PG 实现 | 3–4 | |
| Step 3 迁移脚本 | 1 | |
| Step 4–6 切换/回滚 | 1–2 | |
| **合计（完整 PG）** | **7–9** | |
| **仅文档 + Step 0 暂不切换** | **0.5** | 单用户推荐路径 |

---

## 8. 与 Workflow v3 映射

| 任务 | 本文 |
|------|------|
| P3.4 PG exec stub | §4 Step 1–6 |
| P4-7 ops 验证 | §4 Step 0 · §5 PG-M5 |
| P2.3a token 契约 | Store 方法不变；sink 无 PG 特殊逻辑 |
