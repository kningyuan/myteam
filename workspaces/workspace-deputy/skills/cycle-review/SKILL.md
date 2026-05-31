---
name: cycle-review
description: "持续项目轮次业务效果评审。由 continuous-executor 在下一轮开始前触发（request_cycle_review），非 heartbeat。"
allowed-tools: "read exec"
---

# Cycle Review — 轮次业务效果评审

## 何时使用

- 收到引擎事件 **`request_cycle_review`**
- 存在 **`pending_review`**，评估**已结束且经过间隔**的上一轮
- **不是**任务级 review（交付物质量由 dispatch 内 reviewer 完成）
- **不是** heartbeat 监控（那是 Mode A）

## 输入

- `project_summary.goal` / `current_state`
- `last_closed_cycle`：任务列表、交付物路径、**hypotheses**、自报 metrics
- 可选：`deliverable_digest_paths`（引擎提供的摘要路径）

## 输出

### 1. JSON 响应（写入 `.response/..._cycle_NNN_review.response`）

```json
{
  "cycle_id": 1,
  "effectiveness": "met | partial | missed | inconclusive",
  "evidence_summary": "假设 vs 实际，引用交付物章节",
  "planning_hints": ["给 Main 的方向性建议，不是任务列表"],
  "deliverable_path": "deliverables/cycle-001/cycle-001-review.md"
}
```

### 2. 交付物 `cycle-NNN-review.md`

```markdown
# 第 N 轮业务效果评审

## 评审范围
- 周期 ID / 时间
- 本轮假设（来自 close）

## 证据
- 各任务交付物中的指标与结论（引用路径）

## 效果判定
- effectiveness: met | partial | missed | inconclusive
- 理由

## 对下轮规划的建议（planning_hints）
- 条目列表；**不**指定具体 task_id
```

## 边界

- ✅ 对比假设与可观测结果
- ✅ 输出 `planning_hints` 供 **Main cycle_plan** 使用
- ❌ 不制定本轮/下轮任务列表（Main 职责）
- ❌ 不修改 phase 配置或引擎状态
- ❌ 不替代 Ops 的例行健康检查

## MVP 数据不足时

- 优先 `inconclusive`，在 `evidence_summary` 说明缺什么数据
- 仍给出可操作的 `planning_hints`（如「下轮增加可量化 KPI 章节」）
