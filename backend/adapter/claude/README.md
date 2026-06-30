# Claude Code CLI 实现

`backend/adapter/claude/` 是 [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) 的适配实现。本目录是整个仓库**唯一**知道 Claude Code 命令行参数与 `stream-json` 输出格式的地方(AGENTS.md §10)。

## 文件职责(4 个)

| 文件 | 职责 |
|------|------|
| `adapter.py` | `ClaudeCodeAdapter`(id=`claude`);CLI 探测、命令行构建、env 注入、模型列举、末尾 `registry.register` |
| `parser.py` | Claude `stream-json` → `AgentEvent`(**唯一** claude 格式耦合处,6 种行格式) |
| `mcp_sync.py` | 把 myteam 挂载的 MCP 写入 `workspace/.mcp.json` 的 `mcpServers` 块 |
| `skill_sync.py` | 把 myteam 挂载的 Skill 软链到 `workspace/.claude/skills/<id>/` |

## 命令行构建(`adapter.py`)

`ClaudeCodeAdapter` 继承 `SubprocessCLIAdapter`,capabilities 全开(streaming/tool_use/multi_turn/custom_rules/native_skill_registry/native_mcp_registry)。

`_build_run_command(request)` 构建的命令行:

```
<cli_prefix> -p \
  --no-session-persistence \
  --output-format stream-json \
  --verbose \
  --dangerously-skip-permissions \
  --settings <runtime_settings_json> \
  [--model <model>] \
  [--session-id <session_id>] \
  [--append-system-prompt-file <rules_file>]    # 仅当 rules_file 存在 \
  [--strict-mcp-config --mcp-config <workspace>/.mcp.json]   # 仅当 .mcp.json 存在 \
  [--setting-sources project]                   # 仅当 agent 有挂载 skill
```

`<cli_prefix>` 由 `_cli_command()` 决定:普通路径直接 `[path]`;若是 `npx` 回退则展开为 `npx @anthropic-ai/claude-code`。

子进程以 `cwd=workspace`、`start_new_session=True` 启动,经基类 `stream_subprocess_io` 逐行读 stdout 并交 `parse_line`。

### CLI 路径探测(`_cli_path()`)

优先级:`system_config.get_cli_path("claude")` → `CLAUDE_CLI_PATH` 环境变量 → `PATH` 中的 `claude` → 逐 PATH 目录找 `claude` → 回退 `npx`。`_cli_available()` 检查可启动性(npx 回退仅查 `npx` 存在);不可用时 `run()` 直接 yield `ERROR`。

### settings / env 注入

- `_runtime_settings_json()`:`{"showThinkingSummaries": true, "env?": {...}}`。`--settings` 传入,在 `stream-json` 中输出思考摘要(对齐 opencode `--thinking`)。
- `_load_claude_user_settings()`:读 `~/.claude/settings.json`(ccswitch / 用户鉴权与代理常写这里),取其 `env`。
- `_claude_subprocess_env()`:继承 Hub 环境,并 `setdefault` 补齐 `~/.claude/settings.json` 的 env(不覆盖已有变量)——`--setting-sources project` 时仍需代理/鉴权 env。
- `OPENCLAW_WORKER_AGENT_ID` / `DISPATCH_TOKEN_ENV`:同 opencode。

### list_models

`_merge_claude_models()`:内置目录 `_CLAUDE_MODEL_CATALOG`(别名 `sonnet`/`opus`/`haiku`/`fable` + 完整 id `claude-sonnet-4-6` 等 12 项)+ `system_config.get_models("claude")` 扩展/覆盖。`default` 对齐 `system_config.get_default_model("claude")`;无显式 default 时 `sonnet` 置 default。

## parser 6 种行格式说明(`parser.py`)

`parse_line(line)` 解析 Claude Code `--output-format stream-json --verbose` 的一行 stdout,返回 0~N 个 `AgentEvent`。每行是一个 JSON 对象,顶层 `type` 决定分支,共 6 种行格式:

| # | 行格式(`type`/`subtype`) | 产出 EventKind | 关键字段提取 |
|---|--------------------------|----------------|--------------|
| 1 | `system` / `init` | `SESSION` | `session_id` → `{session_id}`;`model` → `{model}` |
| 2 | `assistant`(content 含 `text`) | `TEXT` | `content[].text` → `{content}` |
| 3 | `assistant`(content 含 `thinking`/`redacted_thinking`) | `REASONING` | `_thinking_text` 兼容 `thinking`/`text`/`summary` → `{content}` |
| 4 | `assistant`(content 含 `tool_use`) | `TOOL_USE` | `name` → `name`;`input` → `input`(JSON 串);`result?` → `output` |
| 5 | `result` / `success` | `TEXT`(仅 result 行有文本时)+ `STEP_FINISH`(cumulative) | `result` → `{content, source:"result"}`;`_extract_usage_tokens` → `{input,output,total}` |
| 6 | `result` / `error`(或 `is_error:true`) | `ERROR` | `result`/`error` → `{message}` |

附加规则:

- **assistant.usage 增量计量**:每条 `assistant` 行若带 `message.usage`,产出 `STEP_FINISH`(`cumulative:false`),记录本轮增量 `input`/`output`。
- **result 累积计量**:`result` 行产出 `STEP_FINISH`(`cumulative:true`),`total` 取 `usage.total_tokens` 或 `modelUsage` 逐模型 `input+output` 最大值,再回退 `input+output`。
- **工具型回合无 assistant 文本块**:最终答复仅在 `result` 行,parser 在 result 行补 `TEXT`(标 `source:"result"`)。
- `_thinking_text` 兼容 `thinking` / `text` / `summary` 三键,空串跳过。
- 行非 JSON / 空行 → 返回 `[]`。

> 增量 vs 累积的聚合逻辑(`_apply_step_finish_tokens` / `_extract_tokens`)在 `common.agent.agent_port`,parser 只负责标注 `cumulative` 与产出 `tokens` 块——见 `test_claude_parser.py`。

## MCP 同步(`mcp_sync.py`)

`sync_workspace_mcp(workspace, server_ids)` 把 `common.mcp_catalog.load_mcp_registry()` 中 `enabled` 的服务写入 `workspace/.mcp.json`:

- **local** → `{command: <cmd[0]>, args?: [...cmd[1:]], env?:{...}}`(command 为可执行名,args 为剩余参数;无 command 时返回 `{}` 并进 missing)
- **remote** → `{type:"http", url, headers?:{...}}`

与 OpenCode 的差异:Claude 的 local 是 `command`+`args` 拆分(OpenCode 是完整列表 `command`);`remote` 的 `type` 值是 `"http"`(OpenCode 是 `"remote"`);无 `enabled`/`timeout` 字段。

行为:

- 整文件覆写为 `{"mcpServers": mcp_block}`(不保留已有字段,与 opencode 的保留策略不同)。
- `server_id == "workspace"` → 直接进 `missing`(`workspace` 是 Claude 保留内置,不走外部配置)。
- `enabled: False` / catalog 不存在 / entry 为空 → 进 `missing`。
- 写 `workspace/.claude/.myteam-mcp.json` manifest(`server_ids` / `linked` / `missing`)。
- 返回 `{success, workspace, config_path, linked, missing}`。

CLI 运行时由 `_build_run_command` 在 `.mcp.json` 存在时追加 `--strict-mcp-config --mcp-config <path>`。

## Skill 同步(`skill_sync.py`)

`sync_workspace_skills(workspace, skill_ids)` 把 skill 目录软链到 `workspace/.claude/skills/<id>/`(目录级软链),清理 stale 条目,写 `workspace/.claude/.myteam-skills.json` manifest(`version:2`)。底层复用 `common.skill.skill_link`。CLI 运行时由 `--setting-sources project` 让 Claude Code 仅加载项目级 `.claude/skills`。

## 注册

`adapter.py` 末尾:

```python
from adapter.core.registry import registry  # noqa: E402
registry.register(ClaudeCodeAdapter())
```

由 `adapter/__init__.py` 的 `import adapter.claude.adapter` 触发。

## 变更维护

- **改命令行参数 / CLI 探测**:只动 `adapter.py` 的 `_build_run_command` / `_cli_path` / `_cli_command`;补 `test_claude_adapter.py`。
- **改模型目录合并**:只动 `_merge_claude_models` / `_CLAUDE_MODEL_CATALOG`;补 `test_claude_models.py`。
- **改 stream-json 解析**:只动 `parser.py`;补 `test_claude_parser.py`(注意增量/累积计量与 `agent_port` 联动)。
- **改 MCP entry 格式**:只动 `mcp_sync.py` 的 `_to_claude_mcp_entry`;补 `test_claude_mcp_sync.py`。
- **改 Skill 软链**:只动 `skill_sync.py`;补 `test_claude_skill_sync.py`。
