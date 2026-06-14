# SQLite / Store 现状审计

> **生成时间**：2026-06-14  
> **扩展自**：[`sqlite-direct-write-audit.md`](./sqlite-direct-write-audit.md)（2026-06-13）  
> **权威 Gate**：[`platform-v3-gates.md#p1-gate`](./platform-v3-gates.md#p1-gate) P1-G3

---

## 1. state.db 实证

| 项 | 值 | 证据 |
|----|-----|------|
| 路径 | `business/tasks/state.db` | `backend/common/store.py:33-34` `default_db_path()` → `TASKS_DIR / "state.db"` |
| 绝对路径示例 | `/Users/kuanghualong/Project/Cursor/myteam/business/tasks/state.db` | 本机 `ls` |
| 文件大小 | **12 MB**（11,878,400 bytes） | `du -h` / `ls -la` 2026-06-14 |
| journal_mode | **wal** | `sqlite3 … PRAGMA journal_mode` |
| page_count | 2900 | 同上 |
| 核心表行数（快照） | project **9** · task **38** · interaction **44** · memory **1** · conversation **12** | `sqlite3` COUNT 查询 |

### 表清单（sqlite_master）

核心真相表（`store.py` `_SCHEMA` 文档）：`project`, `task`, `interaction`, `run_event`, `memory`, `conversation`, `message`。

运行时扩展表（已存在于生产库）：`workspace_event`, `projection_state`, `agent_runtime`, `job`, `message_fts*`, `publish_log`, `audit_log`, `agent_config`, `workflow_version`。

---

## 2. Store 架构

### 2.1 定位

```
人类产物 → business/tasks/project/<id>/deliverables/*.md（文件）
静态配置 → business/config/*.json（agents, groups, session_map）
运行态真相 → business/tasks/state.db（SQLite，ACID）
```

来源：`backend/common/store.py` 文件头注释（D13/O4）；`docs/ARCHITECTURE.md` §3。

### 2.2 Store 类

| 属性 | 说明 |
|------|------|
| 文件 | `backend/common/store.py`（**1099** 行） |
| 并发 | WAL + `busy_timeout`；每线程独立连接（L12 注释） |
| 状态机 | interaction / task 状态转换（L13-15） |
| 默认路径 | `Store()` 无参 → `business/tasks/state.db` |
| 测试 | `backend/common/tests/test_store.py` 等 |

### 2.3 backend/store/ 子包

| 文件 | 职责 |
|------|------|
| `backend/store/__init__.py` | 包标记「持久化层」 |
| `backend/store/sessions.py` | 会话相关持久化 |
| `backend/store/system_config.py` | 系统配置读写 |
| `backend/store/skill_config.py` | Skill 配置读写 |

**与 `common/store.py` 关系**：`common/store.py` 是编排/项目**运行态真相库**；`backend/store/` 是 Hub 配置类 JSON/SQLite 辅助，审计脚本将其排除在「直写 bypass」之外。

### 2.4 Hub 读 + Kernel 写并发模式

| 写方 | 路径 | 说明 |
|------|------|------|
| Process / AgentPort | `Store.upsert_*` / `update_interaction` | 编排内核主写路径 |
| Hub API | 经 Store 方法；**生产 bypass = 0** | 见 §3 |
| kernel_run | `hub/services/kernel_run.py` → `update_project_meta` | 已收拢到 Store API |
| group_manager | 部分 bypass | P2.5 收拢输入 |

Hub 重启：`kernel_run._reconcile_stale_kernel_runs()` 清除 `meta.hub_kernel_run.running` 残留（`kernel_run.py:73-94`）。

---

## 3. 直写 bypass 清单（2026-06-14 终验）

> 扫描命令：`rg '_conn\.execute|sqlite3\.connect' backend --glob '*.py'`  
> 范围：`backend/` 内 `_conn.execute` / `sqlite3.connect`  
> 排除：`backend/common/store.py`（Store 本体）、`backend/store/`（配置子包）

| 分类 | 数量 | 说明 |
|------|------|------|
| **生产 bypass** | **0** | P2.5 / P3 收拢完成；Hub `server.py` 无 `_conn.execute` |
| **测试-only bypass** | **4** | 见下表 |

### 3.1 测试-only `_conn.execute`（2）

| 文件:行 | 上下文 |
|---------|--------|
| `backend/common/tests/test_store.py:187` | 测试直接探针 |
| `backend/common/tests/test_store.py:192` | 测试断言探针 |

### 3.2 测试-only `sqlite3.connect`（2）

| 文件:行 | 上下文 |
|---------|--------|
| `backend/common/tests/test_process.py:1199` | 测试临时库 |
| `backend/common/tests/test_regression_archive.py:22` | 回归归档测试 |

### 3.3 历史 bypass（已收拢）

2026-06-13 审计曾列 **9** 处（含 `server.py` 3 处、`agent_port.py`、`workspace_gc.py`）。截至 2026-06-14：

- `backend/hub/api/server.py` — **0** 直写
- `backend/common/agent_port.py` — **0** 直写
- `backend/common/workspace_gc.py` — **0** 直写

详见 [`group-direct-write-plan.md`](../plans/group-direct-write-plan.md) 与 [`sqlite-direct-write-audit.md`](./sqlite-direct-write-audit.md)。

---

## 4. WAL 与单用户本地运行

| PRAGMA / 行为 | 实测 | 含义 |
|---------------|------|------|
| `journal_mode=wal` | ✅ | 读写并发友好；Hub 读 + kernel 写可并行 |
| 单文件可移植 | ✅ | 拷贝 `state.db` + `business/tasks/project/` 即可迁移 |
| busy_timeout | 代码层有 | `store.py` 连接初始化 |

**风险**：WAL 需同目录 `-wal`/`-shm` 伴生文件；硬杀进程后偶发 `-wal` 残留，SQLite 可恢复。

---

## 5. PostgreSQL 迁移价值评估（诚实结论）

### 5.1 当前部署画像

- **单用户本地**：一人一台，`./run.sh start` + 单 Hub 进程 + 单 `state.db`。
- **数据量**：12 MB / 9 projects——远未触达 SQLite 上限。
- **并发**：无多 Hub 实例水平扩展需求。

### 5.2 PG 能带来什么

| 收益 | 单用户本地 | 多实例 / 团队 |
|------|------------|---------------|
| 行级锁 / 连接池 | 低收益（WAL 已够） | **高收益** |
| 复制 / 备份 | 低（文件拷贝简单） | **高收益** |
| 全文检索扩展 | 已有 FTS5 表 | 可选 |
| 运维复杂度 | **显著上升**（需 PG 服务） | 可接受 |

### 5.3 结论（P1-G3 要求）

| 场景 | 建议 |
|------|------|
| **单用户本地（当前主场景）** | **暂不切换 PG**。优先收拢直写 bypass、修 Store 测试、保持 WAL SQLite。 |
| **多 Hub 实例 / 远程协作** | PG **有价值**；迁移前提：P2.3a Store 契约 + P2.5 bypass 清单清零。 |
| **v3 时间线** | P2.4 出方案；P3 或 P4-7 在测试环境验证，或记录「暂不切换」理由。 |

**产品价值前提**：在单用户本地场景，PG 是**架构预备**而非**立即收益**；强行迁移会增加 deploy 步骤（Docker PG、连接串、迁移脚本）而无明显 UX 提升。

---

## 6. 与 Workflow v3 任务映射

| 任务 | 本文输入 |
|------|----------|
| P2.4 PG 迁移方案 | §5 结论 + §3 bypass 规模 |
| P2.5 直写清单 | §3 全表 |
| P2.3a token 契约 | Store `interaction.tokens` 已为 sink 目标 |
| P3-G5 _KERNEL_RUNS | §2.4 kernel_run 已 Store-only |

---

## 7. 审计检查清单

- [x] state.db 路径与大小
- [x] PRAGMA journal_mode（WAL）
- [x] Store 架构说明
- [x] 直写 bypass 样例路径（继承 sqlite-direct-write-audit.md）
- [x] Hub 读 + kernel 写模式
- [x] PG 单用户 vs 多实例诚实结论
