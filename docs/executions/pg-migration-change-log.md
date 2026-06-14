# PG 迁移变更日志（P3.4 · stub）

> **状态**：**未 fully implemented** — Store 主库仍为 SQLite；本文件记录计划边界与前置条件。  
> **参照**：P2.4 PG 迁移方案、P2.5 `sqlite-direct-write-audit.md` 直写收拢清单

## 当前真相

- 生产/开发默认：`backend/common/store.py` → SQLite（`state.db`）
- Hub API、`AgentPort`、`kernel_run` 均经 `Store` 抽象访问，无 PG 连接串落地

## 前置 Gate（未满足）

- [ ] P2.5 群组/频道等领域直写 SQLite 收拢完成
- [ ] 测试环境 PG 实例与迁移脚本 idempotent 验证
- [ ] @ops 签字：生产切换与回滚预案

## 计划实施步骤（未来）

1. 引入 `Store` 后端适配层（SQLite / PG 双实现或 SQLAlchemy）
2. 迁移脚本：schema 对齐 + 数据导出/导入
3. CI：PG 容器 job + `pytest` 子集
4. 灰度：读 PG / 写双写或只读副本（按 P2.4 方案选定）

## 验收指标（目标）

- 测试环境 Store→PG 全绿：`pytest backend/common/tests -q`
- 无新增 Hub 直写 SQLite 路径（对照 P2.5 审计）
- 回滚演练：≤15 分钟切回 SQLite

## 本阶段产出

无代码迁移；仅本 stub 与 Workflow v3 P3.4 任务闭环说明。
