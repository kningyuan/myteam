# Mac App 契约（v1）

> **版本**：2026-06-11  
> Mac App **只通过 Hub HTTP API** 修改 Strategy 层；不直接写 Kernel 代码或 Store schema。

---

## 1. 允许的操作（Strategy 层）

| API | 作用 |
|-----|------|
| `GET/POST/PUT/DELETE /api/workflows` | workflow CRUD（保存前 `validate_workflow`） |
| `GET/POST/PUT/DELETE /api/agents` | agent CRUD |
| `GET/POST /api/run_kernel` | 启动/恢复项目 |
| `GET /api/obs/*` | 只读观测 |

写入 workflow 时服务端会：

1. 运行 `validate_workflow`（plan_gate + agent 能力 + task_type 注册）
2. 写入 `business/workflows/<id>.yaml`
3. 追加 `workflow_version` 行到 SQLite（版本历史）

---

## 2. 禁止（v1 安全边界 B/C）

- 直接修改 `backend/common/process.py` 等 Kernel 源文件
- 绕过 Gate 强制将 task 标为 `completed`
- 直接编辑 `state.db` 而不经 API（除只读导出）

---

## 3. 配置校验（安全边界 A）

非法 workflow 保存返回 **400**，`APIError` code `INVALID_WORKFLOW`，body 含具体原因。

常见拒绝原因：

- 未知 task_type
- agent 未配置对应 task_type 能力
- DAG 环或 plan_gate 失败
- 引用不存在的 delivery_template

---

## 4. 数据真相源

| 数据 | v1 真相源 |
|------|-----------|
| 项目/任务/交互 | SQLite `state.db` |
| 群消息（新） | `conversation`/`message` + `groups.json` 元数据 |
| workflow 定义 | YAML 文件 + `workflow_version` 表 |
| agent 运行配置 | `agents_config.json` + 可选 `agent_config` 表 |
| 交付物 | `deliverables/*.md` |

---

## 5. 相关文档

- [V1_CAPABILITY_PLAN.md](./V1_CAPABILITY_PLAN.md)
- [PRODUCTION_BASELINE.md](./PRODUCTION_BASELINE.md)
