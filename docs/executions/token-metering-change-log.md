# Token 计量变更日志（P3.3 · 修正项 #2）

> **日期**：2026-06-14  
> **状态**：契约 + `AgentPort` 接线已完成；adapter 层采集与前端展示为后续 Wave

## 目标

adapter 采集 usage → `TokenUsageSink.record_usage` → Store 真相库（`interaction.tokens` + 项目 meta 汇总）。

## 实现

### 契约层 — `backend/common/token_usage.py`

- `TokenUsageSink` Protocol
- `StoreTokenUsageSink` — 经 `Store.bump_interaction_tokens(interaction_id, tokens)` 落盘

### 接线 — `backend/common/agent_port.py`

| 位置 | 行为 |
|------|------|
| `AgentPort.__init__` L110 | `self._token_sink = token_sink or StoreTokenUsageSink(self.store)` |
| `_drain_events` L316 | `step_finish` 事件时 `_token_sink.record_usage(project_id, iid, running, ...)` |
| `_finalize_done` L345 | `finalize_interaction(..., token_sink=self._token_sink)` |
| `finalize_interaction` L451 | 无 sink 时回退 `StoreTokenUsageSink(store)`；采纳 meta.tokens 或 event_tokens |

数据流：

```
Transport emit(step_finish) → AgentPort._drain_events → StoreTokenUsageSink.record_usage
                                                      → Store.bump_interaction_tokens
finalize_interaction (done 采纳) → 同上（meta.tokens / event_tokens 回退）
```

## 测试证据

- `backend/common/tests/test_token_usage.py` — sink 协议与 `bump_interaction_tokens` 集成
- `backend/common/tests/test_agent_port.py` — 计量与 budget 硬停
- 全量：`pytest backend/common/tests -q` — **589 passed**

## 未完成（诚实范围）

- [ ] 各 adapter `_extract_tokens` 统一回退策略文档化到本文件附录
- [ ] Hub API `/api/obs/*` token 字段与前端 SSE 展示端到端验收（修正项 #2 功能性 Gate 后半段）
- [ ] 项目级 `meta.tokens` 月度汇总与 Home 趋势微标对齐

## 关联

- P2.3a：`docs/assessments/six-dimension-diagnosis.md` 契约说明
- P2.3b：adapter 采集方案（待执行 stub 细化）
