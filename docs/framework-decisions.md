# 框架决策索引（D1–D19 / F1）

> 完整设计说明曾归档于 `docs/0607/`（已移除）。**当前以代码注释 + 本索引 + [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)** 为准。

代码中引用形如 `D12`、`F1` 的决策，主要分布在：

| 区域 | 文件 |
|------|------|
| AgentPort / 看门狗 / 文件交卷 | `backend/common/agent_port.py` |
| Interaction 契约 | `backend/common/contracts.py`、`submit_result.py` |
| Gate 确定性 vs 质量 | `backend/common/gate.py`、`registry.py` |
| 适配器隔离 | `backend/adapter/`、`agent_transport.py` |
| Process 失败语义 | `backend/common/process.py`、`process_types.py` |
| 可观测 | `backend/common/observability.py`、`hub/api/observability_api.py` |

## 核心决策（摘要）

| ID | 主题 | 要点 |
|----|------|------|
| **D10** | 格式注册表 | `templates.yaml` → `registry.get_spec`；下发与 Gate 同源 |
| **D11** | Interaction 契约 | 仅 `InteractionRequest` / `InteractionResponse`；`submit_result` 本地校验 |
| **D12** | AgentPort | 同步阻塞；`.request`/`.response` 为传输缓存；**Store 为真相** |
| **D13** | 持久化 | SQLite `state.db` 为项目/interaction 真相源 |
| **D14** | Gate 范围 | 契约 + 格式 + 完整性；质量归 Agent 自评 + review |
| **D15** | outcome_kind | `artifact` / `action` / `code_project`；action 校验发布证据 |
| **D18** | 失败语义 | `failed` vs `needs_review`；triage 升级 |
| **F1** | 禁止 JSON rescue | 无效契约拒绝，不抢救 |

## 延伸阅读

- 升级阶段共识：`docs/0608/05-交叉讨论共识.md`
- L2 封板：`docs/0608/14-L2-框架封板门禁.md`
- 需求映射：`docs/new/03-需求-实现映射与演进.md`
