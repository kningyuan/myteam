# P3.2 产品轻量确认（P0 矩阵）

> **日期**：2026-06-14  
> **Workflow**：`myteam-platform-v3` · 任务 `p3-2-product-light-confirm`  
> **Gate 锚点**：[`platform-v3-gates.md#p3-gate`](./../assessments/platform-v3-gates.md#p3-gate) P3-G6（**不阻塞** P3-G1–G5）  
> **矩阵真源**：[`v1-v2-feature-matrix.md`](../assessments/v1-v2-feature-matrix.md)

---

## 确认范围

**轻量验收** = P0 核心用户旅程在 v1 与 v2 均可完成，不要求 P1 增强项（sync/suggest 系列）或 P2 演示项迁移。

| 层级 | 标准 | 本确认 |
|------|------|--------|
| 轻量（P3-G6） | P0 矩阵 100% 可用 | ✅ 31/31 |
| 完整（P4-1/2） | P1 缺口 + 核心旅程 @product 签字 | 见 `p4-gate-record.md` P4-4 |

---

## P0 矩阵逐项（31/31）

| # | 功能域 | 子功能 | v1 | v2 | 轻量确认 |
|---|--------|--------|----|----|----------|
| 1 | 项目 | 列表（obs/projects） | ✅ | ✅ | ✅ |
| 2 | 项目 | 概览 / 成本 / 舰队 / 事件 | ✅ | ✅ | ✅ |
| 3 | 项目 | 发起 run | ✅ | ✅ | ✅ |
| 4 | 项目 | 续跑 resume | ✅ | ✅ | ✅ |
| 5 | 项目 | 取消 cancel | ✅ | ✅ | ✅ |
| 6 | 项目 | 删除 delete | ✅ | ✅ | ✅ |
| 7 | 项目 | run-status | ✅ | ✅ | ✅ |
| 8 | 项目 | SSE stream + interaction events | ✅ | ✅ | ✅ |
| 9 | 项目 | DAG 可视化 | ✅ | ✅ | ✅ |
| 10 | 项目 | 交付物浏览 / 多文件 | ✅ | ✅ | ✅ |
| 11 | 项目 | 执行树 + Gate 失败展示 | ✅ | ✅ | ✅ |
| 13 | 私聊 | SSE 流式发送 | ✅ | ✅ | ✅ |
| 14 | 私聊 | 消息历史 | ✅ | ✅ | ✅ |
| 15 | 私聊 | 清空 / 归档 / 恢复 | ✅ | ✅ | ✅ |
| 19 | 群组 | 列表 / 详情 / SSE events | ✅ | ✅ | ✅ |
| 20 | 群组 | 群聊 SSE | ✅ | ✅ | ✅ |
| 23 | 管理 | Agents CRUD + 工作区文件 | ✅ | ✅ | ✅ |
| 24 | 管理 | Task types CRUD | ✅ | ✅ | ✅ |
| 25 | 管理 | Delivery templates CRUD | ✅ | ✅ | ✅ |
| 26 | 管理 | 知识库 memory | ✅ | ✅ | ✅ |
| 30 | Workflow | 列表 / 编辑 / suggest / 删除 | ✅ | ✅ | ✅ |
| 31 | 设置 | system + skill config | ✅ | ✅ | ✅ |
| 32 | 设置 | apply-model 全员 | ✅ | ✅ | ✅ |
| 34 | 可观测 | obs/summary 首页 | ✅ | ✅ | ✅ |

> 行号与矩阵 §2 一致；P0 行共 **31** 条（矩阵 §4 汇总）。

---

## 汇总

| 指标 | 值 |
|------|-----|
| P0 行总数 | **31** |
| P0 v1 可用 | **31/31** |
| P0 v2 可用 | **31/31** |
| P0 v2 弱于 v1 | **0** |
| **P3-G6 判定** | **PASS** — P0 已补齐（轻量层） |

---

## 证据

| 类型 | 路径 / 命令 |
|------|-------------|
| 矩阵扫描 | `docs/assessments/v1-v2-feature-matrix.md` §2–§4 |
| v2 API 封装 | `frontend-v2/src/lib/api.ts`（52 函数 · ~45 HTTP 路径） |
| 回归 | `docs/executions/p3-regression-report.md` — pytest **589 passed**, E2E 8/8 |
| E2E 双跑 | `scripts/regression/reg_platform_v3_e2e_baseline.py` — consistent |

---

## 非本确认范围（带入 P4）

| 项 | P级 | 说明 |
|----|-----|------|
| sync-task-types / suggest-* | P1 | v2 Manage UI 未暴露；API 已有 |
| 多会话侧栏 / per-agent SSE | P1 | v2 实现路径不同 |
| init / demo | P2 | 仅 v1 |
| Skill L3 页 | P2 | v2 增值，非 P0 |

---

## 签发

| 字段 | 值 |
|------|-----|
| P3-G6 状态 | **PASS** |
| P0 标注 | 矩阵 P0 行均可标「**已补齐（轻量）**」 |
| 阻塞 P3.5 | **否** |
