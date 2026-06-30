# Hub API 薄路由层

`backend/hub/api/` 是 FastAPI 薄路由层:只做参数解析 / 路由分发 / 统一错误信封 / SPA 静态托管,**业务逻辑下沉到** `hub/services/` 与 `base/`。路由层不直接 `subprocess`、不直接碰 CLI 原始输出(D10 隔离)。

## server.py 的装配职责

`server.py` 是 FastAPI app 的装配中心,自身不定义业务路由,只做 5 件事:

| 职责 | 说明 |
|------|------|
| **lifespan 启动恢复** | 启动时补 `agents_config` 条目、同步 Skill/MCP 挂载、清 Hub 重启残留 kernel 标记(`_reconcile_stale_kernel_runs`)、对账孤儿 `.response`(`reconcile_on_start`)、GC workspace、自动续跑中断项目(`_auto_resume_on_startup`) |
| **CORSMiddleware** | `_CORS_ORIGINS` 来自 `MYTEAM_CORS_ORIGINS` 环境变量(默认 `*`) |
| **路由挂载** | 直接文件 `*_api.py` 的 router 逐个 `app.include_router`;`routes/__init__.py` 的 `api_router` 聚合后一次性挂载 |
| **异常处理** | `APIError` → 统一 error 信封(`to_dict`);手抛 `fastapi.HTTPException` 归一化为同形状并保留 `detail` 向后兼容;Starlette 404 / 422 走默认形状不误伤 |
| **SPA 托管** | `/` → 302 重定向 `/v2/`;`/v2/` 与 `/v2/{rest_path}` 兜底 `index.html`(深链可刷新);UI 未构建时 `/` 返回 503 |

`main()` 读端口(默认 8765)+ `uvicorn.run(host="0.0.0.0", reload=MYTEAM_RELOAD)`。

## 直接文件清单(api/ 根目录)

| 文件 | 职责 | 前缀 / 备注 |
|------|------|-------------|
| `server.py` | FastAPI app 装配(lifespan / CORS / 路由挂载 / 异常 / SPA) | 见上表 |
| `deps.py` | 共享依赖:`we_store()` 返回 `Store` 单例 | 无 router |
| `errors.py` | 统一错误类型 `APIError`(code/message/hint/doc_url/status_code)+ `to_dict` 信封 | 无 router |
| `config_api.py` | Phase4 配置 API:5 个子路由(kb 模板 / task_type_skills / preference_sections / workflow_profile / agent_task_type_rules) | `/api/knowledge/templates`、`/api/task-types`、`/api/preferences`、`/api/workflows`、`/api/task-types/rules` |
| `observability_api.py` | 只读可观测路由(D17):项目列表 / 总览 / cost / events / fleet / 任务详情 / interaction timeline / SSE | `/api/obs` |
| `skills_api.py` | Skill 库 / 草案 / 分组 / 分类 CRUD + pending 审批包 | `/api/skills` |
| `rules_api.py` | 团队通用 rules API(`business/rules/*.md`) | `/api/rules` |
| `mcp_api.py` | MCP server 库 CRUD | `/api/mcp` |
| `preferences_api.py` | 团队偏好库 API(`config/USER.md`) | `/api/preferences` |
| `prompt_injections_api.py` | 注入块 CRUD | `/api/prompt-injections` |
| `prompt_templates_api.py` | 模板 CRUD | `/api/prompt-templates` |
| `delivery_profiles_api.py` | 交付 profile CRUD | `/api/delivery-profiles` |

## routes/ 域路由清单

`routes/__init__.py` 用一个 `api_router = APIRouter()` 聚合下面 10 个域路由文件(部分文件导出多个 router,均被 `include_router`)。

| 文件 | 职责 | 前缀 |
|------|------|------|
| `agents.py` | Agent 列表 / 详情 / workspace 编辑 / 删除 / manage / notify / events SSE / create / suggest-id / registry CRUD;另导出 `obs_router`(可观测) | `/api/agents`(+ obs 无前缀) |
| `chat.py` | 1-on-1 流式对话 / cancel / status / messages 历史 / clear / archive | `/api/chat` |
| `config.py` | agent backend/model 配置 / apply-model-to-all / backends 列表 / system config get/put / skill config / sync-task-types / sync-skills / sync-mcp | 路由级路径(`/api/agents/{id}/config`、`/api/backends`、`/api/config`…) |
| `groups.py` | 群 CRUD / 成员 / 圆桌设置 / 群聊 SSE / cancel / status / events;项目建群 / 群消息 | `groups_router` `/api/groups`、`projects_router` `/api/projects` |
| `projects.py` | 项目列表 / 详情 / 日志 / run / run-status / dispatch / resume / deliverable / cancel / delete | `/api/projects`(+ `_extra_router` 无前缀) |
| `single_execute.py` | 单 Agent execute:list / get / prepare / finish | `/api/single-execute` |
| `system.py` | `/api/status`:初始化状态 / 项目数 / 运行中数 / token 趋势 | 路由级路径(`/api/status`) |
| `task_types.py` | 任务类型注册表:list / outcome-kinds / suggest / create / update / delete | `/api/task-types` |
| `workflows.py` | workflow CRUD | 路由级路径(`/api/workflows`) |
| `delivery_templates.py` | 交付模板 CRUD | `/api/delivery-templates` |

## 路由挂载方式

两种挂载路径,均在 `server.py` 顶层完成:

```python
# 1) 直接文件 *_api.py:各自定义 router,逐个 include
from hub.api.config_api import router as config_router
from hub.api.observability_api import router as observability_router
# … skills / mcp / rules / preferences / prompt_templates / prompt_injections
app.include_router(observability_router)
app.include_router(skills_router)
# …
app.include_router(config_router)

# 2) routes/ 域路由:由 routes/__init__.py 聚合为单个 api_router,一次性挂载
from hub.api.routes import api_router
app.include_router(api_router)
```

`routes/__init__.py` 内部把 10 个域文件导出的 router(含 `agents.py` 的 `obs_router`、`projects.py` 的 `_extra_router`、`groups.py` 的 `groups_router`/`projects_router`)逐个 `api_router.include_router`,再由 `server.py` 挂载 `api_router`。

## lifespan 启动流程

`server.py` 的 `lifespan` 异步上下文管理器在 Hub 启动时执行恢复逻辑(均幂等,重启安全)。前 3 步在 lifespan 主流程同步执行,后 4 步在 `_auto_resume_on_startup` 后台 daemon 线程执行(不阻塞启动):

**lifespan 同步(启动时):**
1. **补 `agents_config` 条目** — `ensure_agents_config_entries(persist=True)` 扫 workspace 补齐缺失 agent 配置
2. **同步 Skill 挂载** — `sync_all_agent_skill_mounts()` 把 `business/skills/` 同步到各 agent workspace
3. **同步 MCP 挂载** — `sync_all_agent_mcp_mounts()` 把 `mcp_registry.json` 同步到各 agent workspace

**`_auto_resume_on_startup` 后台线程(不阻塞):**
4. **清 Hub 重启残留 kernel 标记** — `_reconcile_stale_kernel_runs()` 把上次未正常退出的 `hub_kernel_run.running=true` 置 false
5. **对账孤儿 `.response`** — `reconcile_on_start(store)` 处理 kernel 中断遗留的未提交响应(先对账再 GC,避免误删可采纳孤儿)
6. **GC workspace** — `gc_workspace(store)` 清理过期临时文件
7. **自动续跑中断项目** — 恢复 status 为 `in_progress` / `paused` 的项目

## 异常处理与统一 error 信封

所有 API 错误归一为同一形状,前端只需处理一种结构。`server.py` 注册两个 `exception_handler`:

**1) `APIError` → 统一信封**(业务错误首选,见 `errors.py`):

```python
@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
```

`to_dict()` 产出:

```json
{"error": {"code": "AGENT_NOT_FOUND", "message": "...", "hint": "...", "doc_url": "..."}}
```

字段:`code`(机器可读)、`message`(人话)、`hint`(建议动作,默认 `""`)、`doc_url`(排查链接,默认 `""`);`status_code` 默认 400,由 HTTP 层带,不进信封体。

**2) `fastapi.HTTPException` → 归一化信封 + 向后兼容**:

```python
@app.exception_handler(HTTPException)
async def http_exception_envelope(request, exc):
    return JSONResponse(status_code=exc.status_code, content={
        "error": {"code": f"HTTP_{exc.status_code}", "message": exc.detail, "hint": "", "doc_url": ""},
        "detail": exc.detail,  # 向后兼容:旧前端 / 现有测试仍读 detail
    })
```

仅接管代码里**手抛**的 `fastapi.HTTPException`;Starlette 路由 404、`RequestValidationError`(422)是不同异常类,仍走默认形状,不误伤。

> `errors.py` 的 `APIError` 由 `services/tests/test_errors.py` 覆盖(构造 / 默认值 / `to_dict` 信封)。

## SPA 托管

- `/` → 302 重定向 `/v2/`(UI 就绪时);UI 未构建时 `/` 返回 503 并提示 `npm run build`
- `_V2_UI_READY` = `FRONTEND_DIST/index.html` 存在;启动时探测一次
- `/v2/` 与 `/v2/{rest_path}` 兜底 `index.html`(深链可刷新,前端路由接管)
- 静态资源(`/v2/assets/...`)由 `StaticFiles` 直出

## 变更维护

- **新增直接文件 API**:在 `api/` 建 `*_api.py` 定义 `router = APIRouter(prefix=...)`,在 `server.py` import + `app.include_router`;更新本 README 直接文件清单表
- **新增域路由**:在 `routes/` 建文件并定义 router,在 `routes/__init__.py` import + `api_router.include_router`;更新本 README 域路由清单表
- **新增共享依赖 / 错误码**:分别扩展 `deps.py` / `errors.py`,勿在路由文件内重复定义
- **删除 / 重命名路由文件**:同步更新 `server.py` 或 `routes/__init__.py` 的挂载点 + 本 README 清单表
