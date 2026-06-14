# API 拆分变更日志（P3.1 · Phase 2）

> **日期**：2026-06-14  
> **参照**：`docs/plans/api-split-plan.md` Wave 2/3 部分落地

## 行数快照

| 文件 | 提取前 | 提取后 | Δ |
|------|--------|--------|---|
| `backend/hub/api/server.py` | 1803 | 1540 | **−263** |
| `backend/hub/api/routes/channels.py` | 94 | 94 | —（Wave 1，未变） |
| `backend/hub/api/routes/projects.py` | — | 98 | +98（新建） |
| `backend/hub/api/routes/agents.py` | — | 74 | +74（新建） |
| `backend/hub/services/project_launch.py` | — | 176 | +176（新建，共享内核调度） |
| `backend/hub/api/routes/__init__.py` | 9 | 13 | +4 |

**server.py 累计削减**（含 Wave 1 channels）：约 −400 行（自 ~1900 基线）。

## 本阶段提取端点

### `routes/projects.py`（prefix `/api/projects`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects/run` | 发起项目（后台内核） |
| GET | `/api/projects/{project_id}` | 项目详情 |
| GET | `/api/projects/{project_id}/log` | 项目日志 |

### `routes/agents.py`（prefix `/api/agents`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | Agent 列表 + DM 活动态（`last_message_at` / `last_message_preview`） |

## 共享依赖

- `hub/api/deps.py` — `we_store()`（agents 活动扫描复用 Store 单例）
- `hub/api/errors.py` — `APIError`
- `hub/services/project_launch.py` — `slug`、`persist_project_launch`、`run_kernel_bg`、`resume_kernel_bg`、`start_kernel_job`（server 遗留路由与 lifespan 续跑共用）

## 仍驻留 `server.py` 的项目/Agent 路由（后续 Wave）

- `/api/projects/run-status/*`、`/resume`、`/cancel`、`/deliverable/*`、`/dispatch`、group 绑定等
- `/api/agents/{id}/config`、`/detail`、`/events`、`/chats`、CRUD 等

## 测试

- `pytest backend/common/tests -q`：**589 passed**
- `test_projects_api.py` monkeypatch 目标迁至 `hub.services.project_launch`

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| `POST /run` 与 `GET /{project_id}` 路径冲突 | `/run` 路由注册在 `/{project_id}` 之前 |
| 循环导入 server ↔ routes | 内核调度下沉 `project_launch.py` |
| Store 单例测试污染 | agents 路由使用 `deps.we_store()`，与 channels 一致 |
