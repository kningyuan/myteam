# OpenCode CLI 实现

`backend/adapter/opencode/` 是 [OpenCode CLI](https://opencode.ai) 的适配实现。本目录是整个仓库**唯一**知道 OpenCode 命令行参数与 NDJSON 输出格式的地方(AGENTS.md §10)。

## 文件职责(4 个)

| 文件 | 职责 |
|------|------|
| `adapter.py` | `OpenCodeAdapter`(id=`opencode`);命令行构建、env 注入、模型列举、末尾 `registry.register` |
| `parser.py` | OpenCode NDJSON → `AgentEvent`(**唯一** opencode 格式耦合处) |
| `mcp_sync.py` | 把 myteam 挂载的 MCP 写入 `workspace/opencode.json` 的 `mcp` 块 |
| `skill_sync.py` | 把 myteam 挂载的 Skill 软链到 `workspace/.opencode/skills/<id>/` |

## 命令行构建(`adapter.py`)

`OpenCodeAdapter` 继承 `SubprocessCLIAdapter`,capabilities 全开(streaming/tool_use/multi_turn/custom_rules/native_skill_registry/native_mcp_registry)。

`run(request)` 构建的命令行:

```
<cli_path> run \
  --dangerously-skip-permissions \
  --format json \
  --thinking \
  [-m <model>] \
  [-s <session_id>] \
  --dir <workspace> \
  [-f <rules_file>]
```

子进程以 `cwd=workspace`、`start_new_session=True` 启动,经基类 `stream_subprocess_io` 逐行读 stdout 并交 `parse_line`。

### CLI 路径探测(`_cli_path()`)

优先级:`system_config.get_cli_path("opencode")` → `OPENCODE_CLI_PATH` 环境变量 → `~/.opencode/bin/opencode`。找不到时 `run()` 直接 yield `ERROR`。

### env 注入

- `OPENCLAW_WORKER_AGENT_ID` — 传入 `request.agent_id`。
- `OPENCODE_DISABLE_EXTERNAL_SKILLS` / `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` — 当 agent 有挂载 skill 时置 `1`,严格模式:仅用工作区 `.opencode/skills` 已挂载的 Skill。
- `DISPATCH_TOKEN_ENV` — 传入 `request.extra["dispatch_token"]`(供 `common.delivery.submit_result` 回写结果鉴权)。

### list_models

优先 `opencode models` 真实输出(进程级缓存,TTL 5 分钟,`invalidate_models_cache()` 可清);失败回退 `system_config.get_models("opencode")`;再失败回退静态 `opencode/mimo-v2.5-free`。模型 id 含 `/` 时按 `provider/name` 拆分,`default` 标记对齐 `system_config.get_default_model("opencode")`。

## parser 格式说明(`parser.py`)

`parse_line(line)` 解析 OpenCode `--format json` 的一行 NDJSON stdout,返回 0~N 个 `AgentEvent`。每行是一个 JSON 对象,顶层 `type` 决定分支:

| 顶层 `type` | 产出 EventKind | 关键字段提取 |
|-------------|----------------|--------------|
| `step_start` / `step-start` | `STEP_START` | `{}` |
| `text` | `TEXT` | `part.text` → `{content}` |
| `reasoning` | `REASONING` | `part.text` → `{content}` |
| `tool_use` | `TOOL_USE` | `part.tool`/`part.name` → `name`;`part.input` 或 `state.input` → `input`(JSON 串);`state.output` → `output`;`state.status` → `status` |
| `tool_result` | `TOOL_RESULT` | `part.content` 或 `state.output` → `{content}`(list 转 JSON 串) |
| `step_finish` / `step-finish` | `STEP_FINISH` | `part.tokens` → `{input,output,total,reasoning}`;`part.reason` → `reason` |
| `error` | `ERROR` | `raw.error` 经 `_opencode_error_message` 提取 `data.message`/`data.detail`/`data.error`/`message`/`name` |

特殊处理:

- 顶层 `sessionID` 存在时,先产出 `SESSION({session_id})`。
- **tool_use 内联返回**:OpenCode 把工具返回放在同一个 `tool_use` 事件的 `state.output`(无独立 `tool_result` 事件),parser 一并捕获到 `output`。
- 行非 JSON / 空行 → 返回 `[]`(静默丢弃,不抛错)。
- `_opencode_error_message` 兼容 `error.data.{message,detail,error}` 与 `error.{message,name}` 多层兜底。

## MCP 同步(`mcp_sync.py`)

`sync_workspace_mcp(workspace, server_ids)` 把 `common.mcp_catalog.load_mcp_registry()` 中 `enabled` 的服务写入 `workspace/opencode.json`:

- **local** → `{type:"local", enabled:true, command:[...], environment?:{...}, timeout?}`
- **remote** → `{type:"remote", enabled:true, url, headers?:{...}, timeout?}`

与 Claude 的差异:OpenCode 的 `command` 是**完整列表**(非 `command`+`args` 拆分);`remote` 的 `type` 值是 `"remote"`(Claude 是 `"http"`)。

行为:

- 读已有 `opencode.json`(保留 `$schema`,缺失时补默认 `https://opencode.ai/config.json`),仅覆写 `mcp` 块,其他字段保留。
- `enabled: False` 或 catalog 中不存在的 `server_id` → 进 `missing`,不写入 `mcp` 块。
- 写 `workspace/.opencode/.myteam-mcp.json` manifest(`server_ids` / `linked` / `missing`)。
- 返回 `{success, workspace, config_path, linked, missing}`。

CLI 运行时由 `adapter.run` 通过 `--dir <workspace>` 让 OpenCode 自动发现 `opencode.json`。

## Skill 同步(`skill_sync.py`)

`sync_workspace_skills(workspace, skill_ids)` 把 skill 目录软链到 `workspace/.opencode/skills/<id>/`(目录级软链,非仅 `SKILL.md`),清理已挂载但不在 `skill_ids` 中的 stale 条目,写 `workspace/.opencode/.myteam-skills.json` manifest(`version:2`)。底层复用 `common.skill.skill_link`。

## 注册

`adapter.py` 末尾:

```python
registry.register(OpenCodeAdapter())
```

由 `adapter/__init__.py` 的 `import adapter.opencode.adapter` 触发。

## 变更维护

- **改命令行参数**:只动 `adapter.py` 的 `run()` / `_cli_path()`;补 `test_opencode_models.py`(命令行相关断言)。
- **改 NDJSON 解析**:只动 `parser.py`;补 `test_opencode_parser.py`。
- **改 MCP entry 格式**:只动 `mcp_sync.py` 的 `_to_opencode_mcp_entry`;补 `test_opencode_mcp_sync.py`。
- **改 Skill 软链**:只动 `skill_sync.py`;补 `test_opencode_skill_sync.py`。
