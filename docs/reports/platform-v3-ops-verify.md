# Platform v3 — 运维上线验证

> **日期**：2026-06-14  
> **Agent**：ops（Workflow v3 · `p4-ops-verify`）  
> **对象**：Hub 健康、Store 状态、PG 决策、回滚预案

---

## 健康检查

```bash
# Hub 启动后（默认端口见 run.sh / config）
curl -s http://127.0.0.1:8765/api/status | jq .
```

**期望**：HTTP 200，`status` 字段可用（E2E 基线 Test 1 覆盖）。

---

## Store / 数据库

| 项 | 值 |
|----|-----|
| 路径 | `business/tasks/state.db` |
| 模式 | SQLite WAL |
| 大小 | ~12 MB（单用户本地） |
| 生产直写 bypass | **0**（见 `sqlite-direct-write-audit.md`） |

**PG**：未启用。决策：**暂不切换** — 单实例本地 WAL 足够；PG stub 见 [`pg-migration-change-log.md`](../executions/pg-migration-change-log.md)。

---

## _KERNEL_RUNS 治理

- 内存 dict 已移除  
- `hub/services/kernel_run.py` + Store meta  
- Hub 重启无 ghost `running=true`（见 `kernel-runs-change-log.md` 验证步骤）

---

## 回滚预案（dry-run 记录）

| 场景 | 步骤 |
|------|------|
| API 拆分回归失败 | `git revert` 对应 PR；`pytest backend/common/tests -q` |
| Store 迁移失败 | 恢复 `state.db` 备份（`business/tasks/state.db.bak` 若存在） |
| PG 切换（未来） | 保持 SQLite 只读副本 + 切换连接串（P2.4 方案） |

**本次 v3 执行**：无 PG 切换；回滚范围 = git revert P3 代码变更 + 复跑 `reg_platform_v3_e2e_baseline.py`。

---

## 签发

**Hub + SQLite 本地运维：PASS**  
**PG 生产切换：N/A（defer）**
