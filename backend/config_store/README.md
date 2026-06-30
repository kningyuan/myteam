# Config Store 持久化配置层

myteam 的**纯持久化配置层**（`backend/config_store/`）：三个互不引用的 `.py` 文件，各自只依赖 `common.paths` 的一个路径常量，对系统配置 / 协作 skill 配置 / Session 映射做 JSON 读写。它是整个 backend 最底层的配置依赖，被 `base/`、`hub/`、`common/`、`adapter/`、`memstack/` 广泛引用，自身**不依赖任何业务模块**。

## 整体职责

| 维度 | 说明 |
|------|------|
| **是什么** | 三个独立 JSON 配置存储的读写封装 + 模块级单例 |
| **不是什么** | 不是编排内核（在 `common/`）；不是 CLI 适配层（在 `adapter/`）；不是 Web 服务（在 `hub/`）；不持有任何业务规则 / 任务状态 |
| **依赖方向** | 仅依赖 `common.paths`（路径常量）+ 标准库（`json` / `fcntl` / `time` / `pathlib`） |
| **真相源** | 三个 JSON 文件：`config/system_config.json`、`config/skill_config.json`、`business/config/session_map.json` |

## 文件清单

| 文件 | 职责 | 模块级单例 | 依赖的路径常量（`common.paths`） |
|------|------|-----------|--------------------------------|
| `__init__.py` | 包标识（一行 docstring「持久化层。」） | — | — |
| `system_config.py` | 系统配置：端口、默认 backend/model、coordinator/deputy agent id、CLI 路径、规则 profile 文件名映射。`SystemConfig` 类，JSON 读写 + `_deep_merge` 默认值补齐；`get` / `get_all` / `update_all`（update 时保留 `models` 字段不被覆盖）、`get_models` / `get_default_model` / `get_cli_path` | `system_config = SystemConfig()` | `SYSTEM_CONFIG_FILE` |
| `skill_config.py` | 协作 skill 配置：notifications / hub / executor 超时重试 / auto_group / process_defaults 预算并行 / group_discussion 圆桌参数。`SkillConfig` 类，JSON 读写 + `_deep_merge`；`get(*keys, default)` 多级键查询、`get_all` / `update_all` | `skill_config = SkillConfig()` | `SKILL_CONFIG_FILE` |
| `sessions.py` | Session 映射存储，键 = `adapter_id:agent_id:workspace`。`SessionStore` 类，基于 JSON 文件 + `fcntl.flock` 文件锁；`get` / `set` / `remove` / `remove_for_agent_workspace`。兼容旧 `opencode_session_map.json` 自动迁移 | `session_store = SessionStore()` | `SESSION_MAP_FILE` |

> 三个 `.py` 文件**互不引用**，可独立阅读 / 测试 / 替换。

## 默认值结构说明

### `system_config.DEFAULT_CONFIG`

文件缺失 / 损坏时落盘的默认配置（`_load` 仅在 `not self._data` 时调用 `_deep_merge` 灌入；**已存在的文件原样加载，不与默认值合并**）。关键键：

| 顶层 | 关键键 | 默认值 |
|------|--------|--------|
| `system` | `port` | `8765` |
| | `default_backend` | `"opencode"` |
| | `default_model` | `"sensenova/sensenova-6.7-flash-lite"` |
| | `coordinator_agent_id` / `deputy_agent_id` | `"main"` / `"deputy"` |
| | `rules.profile_filenames` | `{interactive, discussion, workflow_execute, ethos}` → 对应 md 文件名 |
| | `placeholder_markers` / `blocked_markers` / `code_extensions` | 占位 / 拦截 / 代码扩展名列表 |
| `backends` | `opencode` `{enabled, cli_path, model_aliases}` | `enabled=True`、`cli_path=""` |
| | `claude` `{enabled, cli_path}` | `enabled=True`、`cli_path=""` |

`models` 字段**不在** `DEFAULT_CONFIG` 中（由 `/api/backends` 管理）；`get_all()` 返回时剥离 `models`，`update_all()` 拒收外部传入的 `models` 并保留磁盘上既有值。

### `skill_config.DEFAULT_SKILL_CONFIG`

| 顶层 | 关键键 | 默认值 |
|------|--------|--------|
| `notifications` | `enable_telegram` / `use_project_group` | `False` / `True` |
| `hub` | `url` | `"http://127.0.0.1:8765"` |
| `executor` | `poll_interval` / `ack_timeout` / `task_timeout` / `max_retries` | `5` / `300` / `3600` / `3` |
| `auto_group` | `enabled` / `include_main` / `name_prefix` | `True` / `True` / `""` |
| `process_defaults` | `default_project_budget` / `max_parallel` / `max_cycles` / `budget_degrade_threshold` | `1000000` / `3` / `3` / `0.8` |
| `group_discussion` | `default_max_rounds` / `quorum_ratio` / `terminate_commands` | `3` / `0.667` / `["/终止讨论","/终止圆桌","/stop roundtable"]` |

`SkillConfig.get_all()` 直接返回内部 `_data` 引用（不剥离任何字段，区别于 `SystemConfig`）。

### `sessions.SessionStore`

- 键格式：`f"{adapter_id}:{agent_id}:{workspace_key}"`
- entry 结构：`{"session_id": str, "created_at": float, "last_used": float}`；`get` 会刷新 `last_used` 并落盘
- `remove_for_agent_workspace(agent_id, workspace_key)` 按后缀 `f":{agent_id}:{workspace_key}"` 批量删，返回删除数
- 兼容：模块导入时若 `SESSION_MAP_FILE` 不存在但同目录 `opencode_session_map.json` 存在，自动迁移内容

## 与其他 backend/ 模块的边界

config_store 是**被依赖方**，自身不反向依赖任何 backend 模块（除 `common.paths`）。

| 模块 | 关系 | 典型引用 |
|------|------|----------|
| `common/` | 依赖 config_store | `coordinator.py`（coordinator_agent_id）、`gate/`（rules profile）、`observability/audit_log.py`、`process/process_types.py`（process_defaults）、`runtime/run_kernel.py`、`agent/agent_model.py`、`skill/skill_settings.py` |
| `base/` | 依赖 config_store | `agent_chat.py`、`group_manager.py` |
| `hub/` | 依赖 config_store | `api/server.py`、`api/observability_api.py`、`api/routes/{config,agents,projects}.py`、`services/{chat,project_*,project_group}_service.py` |
| `adapter/` | 依赖 config_store | `opencode/adapter.py`（`get_cli_path` / `get_default_model`）、`claude/adapter.py`（`get_cli_path`） |
| `memstack/` | 依赖 config_store | `l1/native.py` |
| `common.paths` | config_store 依赖它 | `SYSTEM_CONFIG_FILE` / `SKILL_CONFIG_FILE` / `SESSION_MAP_FILE` 三个路径常量 |

> **CLI 路径优先级**：`SystemConfig.get_cli_path(backend_id)` 只读 `backends.<id>.cli_path`（空串表示未配置）。`OPENCODE_CLI_PATH` 环境变量兜底逻辑在 `adapter/opencode/adapter.py:_cli_path`，**不在 config_store 内**——config_store 不读环境变量。

## 测试

`tests/` 目录，自包含可测，**用 `tmp_path` 隔离，绝不写真实 `config/` 目录**，不依赖外部 CLI 或运行时状态。

```bash
PYTHONPATH=backend python3 -m pytest backend/config_store/tests/ -q
```

| 测试文件 | 覆盖点 |
|----------|--------|
| `tests/conftest.py` | 隔离 fixture：`monkeypatch` 把 `SYSTEM_CONFIG_FILE` / `SKILL_CONFIG_FILE` 重定向到 `tmp_path`（`common.paths` 与子模块两处都 patch，因 `from common.paths import X` 已把引用绑定到子模块全局）；`SessionStore` 因默认参数在导入时已绑定，显式传 `path=` 隔离 |
| `tests/test_system_config.py` | `DEFAULT_CONFIG` 默认值补齐（fresh-load / 已存在文件原样加载 / `_deep_merge` 递归 / 损坏回退）、`get`·`get_all`（剥离 models）、`update_all`（替换 + models 保留/拒收 + 落盘）、`get_models`·`get_default_model`（default 标记 → system.default_model 回退）、`get_cli_path` |
| `tests/test_skill_config.py` | `DEFAULT_SKILL_CONFIG` 默认值补齐、`get(*keys, default)` 多级键（含 None 值视同缺失）、`get_all`（返回内部引用）、`update_all`（替换 + 落盘） |
| `tests/test_sessions.py` | 键格式 `adapter:agent:workspace`、`get`/`set`（含 `last_used` 刷新）、`remove`、`remove_for_agent_workspace`（后缀匹配 / 跨 adapter 批量删 / 误匹配防护）、落盘持久化 |

## 变更维护

- **新增配置项**：先在对应 `DEFAULT_CONFIG` / `DEFAULT_SKILL_CONFIG` 加默认值，再更新本 README 的「默认值结构说明」表；新增键的读取走 `get(*keys, default=...)`，不要在调用方硬编码默认值
- **新增存储文件**：在 `config_store/` 下加 `<name>.py`，仅依赖 `common.paths` 的一个路径常量，模块级暴露单例；同步加 `tests/test_<name>.py` + 本 README「文件清单」表
- **修改 `update_all` 语义**：`SystemConfig.update_all` 对 `models` 的保留/剥离是合约（`/api/backends` 独占 models 写入），改动需同步 `backend/common/tests/test_fix_be_contract.py`
- **改 SessionStore 键格式**：会破坏存量 `session_map.json` 与 `common.paths.session_key` 的调用方，需同步评估 `adapter/` 与 `base/agent_chat.py`
- **路径常量变更**：路径唯一来源是 `common.paths`，改 `SYSTEM_CONFIG_FILE` / `SKILL_CONFIG_FILE` / `SESSION_MAP_FILE` 需同步 `conftest.py` 的 patch 目标
- **功能变更**：重跑 `backend/config_store/tests/` 确保零回归
