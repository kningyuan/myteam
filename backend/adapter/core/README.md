# Core 抽象层

`backend/adapter/core/` 是 adapter 的 **CLI 无关抽象层**:定义统一事件模型、运行请求、适配器接口、注册中心、SSE 线协议与子进程基类。本目录不 import 任何 `opencode` / `claude` / `subprocess` 的 CLI 专有知识(仅 `subprocess_cli.py` 用标准库 `subprocess`,属通用进程管理)。

## 文件职责(5 个)

| 文件 | 职责 | 关键符号 |
|------|------|----------|
| `events.py` | 统一 Agent 流式事件模型(UI 与 Service 层唯一事件契约) | `EventKind`(8 种枚举)、`AgentEvent` dataclass、`to_thinking_payload()` |
| `protocol.py` | CLI Adapter 抽象接口 + 请求/能力/模型 dataclass | `ModelInfo`、`AdapterCapabilities`、`RunRequest`、`CLIAdapter`(ABC) |
| `registry.py` | Adapter 注册中心(单例) | `AdapterRegistry`、模块级 `registry` |
| `sse.py` | AgentEvent → SSE JSON 线协议(UI 消费) | `encode_event` / `encode_error` / `encode_done` / `encode_citations` |
| `subprocess_cli.py` | 基于 subprocess 的 CLI 后端基类 | `SubprocessCLIAdapter`、`terminate_process_group`、`stream_subprocess_io` |

## 内部依赖链

```
events.py ◄──────────── sse.py            (sse 依赖 events)
   │
   ▼
protocol.py ◄─────── registry.py          (registry 依赖 protocol 的 CLIAdapter/ModelInfo)
   │
   ▼
subprocess_cli.py                          (继承 CLIAdapter,用 events 的 AgentEvent/EventKind)
   │
   ▼
adapters/<cli>/adapter.py                  (子类继承 SubprocessCLIAdapter)
```

- `events` 是最底层,零依赖本目录其他文件。
- `protocol` 依赖 `events`(`CLIAdapter.run` 返回 `Generator[AgentEvent]`)。
- `subprocess_cli` 依赖 `events` + `protocol`(继承 `CLIAdapter`)。
- `registry` 仅依赖 `protocol`(`register(CLIAdapter)`)。
- `sse` 仅依赖 `events`。

**无循环依赖**,新增 core 文件须保持不反向依赖 `adapters/<cli>/`。

## 抽象接口说明

### EventKind(`events.py`)

```python
class EventKind(str, Enum):
    STEP_START = "step_start"
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    STEP_FINISH = "step_finish"
    ERROR = "error"
    SESSION = "session"
```

`AgentEvent.to_thinking_payload()` 把除 `SESSION`/`ERROR` 外的事件转为 `{type, **data}`(供 SSE `thinking` 事件);`SESSION`/`ERROR` 由 `sse` 模块单独走 `done`/`error` 事件。

### RunRequest / CLIAdapter(`protocol.py`)

`RunRequest` 是与 CLI 无关的运行请求(字段见上级 [README](../README.md#核心契约))。

`CLIAdapter` 抽象基类规定每个 CLI 实例必须实现:

| 成员 | 类型 | 说明 |
|------|------|------|
| `id` | property | 后端标识(`opencode` / `claude`),用于 registry 取实例与 `--backend` 选择 |
| `display_name` | property | UI 展示名 |
| `capabilities` | property | `AdapterCapabilities`(streaming/tool_use/multi_turn/custom_rules/native_skill_registry/native_mcp_registry) |
| `list_models()` | method | 返回 `list[ModelInfo]` |
| `get_default_model()` | method | 返回默认模型 id |
| `run(request)` | method | `Generator[AgentEvent]`,核心执行入口 |
| `sync_agent_skills(...)` | method(默认 no-op) | 同步 Skill 到 CLI 原生注册表;支持 `native_skill_registry` 的 adapter 覆盖 |
| `sync_agent_mcp(...)` | method(默认 no-op) | 同步 MCP 到 CLI 原生注册表;支持 `native_mcp_registry` 的 adapter 覆盖 |

`sync_agent_*` 默认返回 `{"success": True, "skipped": True, "reason": ...}`,不支持原生注册表的 adapter 无需覆盖。

### AdapterRegistry(`registry.py`)

模块级单例 `registry`,方法:

- `register(adapter)` — 按 `adapter.id` 注册(`__init__.py` side-effect import 触发)。
- `get(adapter_id)` — 取实例(上游入口)。
- `list_all()` — 全部已注册 adapter(供 `/api/backends` 列出)。
- `list_models_all()` — `{adapter_id: [ModelInfo]}`(供模型选择 UI)。

### SSE 线协议(`sse.py`)

| 函数 | 产出 | 触发场景 |
|------|------|----------|
| `encode_event(event)` | `{"event":"thinking","data":{type,...}}` | 常规事件;`SESSION` 返回 `None`,`ERROR` 转发 `encode_error` |
| `encode_error(message)` | `{"event":"error","data":{"message":...}}` | 错误事件 |
| `encode_done(session_id)` | `{"event":"done","data":{"session_id":...}}` | 流结束 |
| `encode_citations(citations)` | `{"event":"citations","data":[...]}` | 引用闭环(检索召回来源推 UI) |

### SubprocessCLIAdapter(`subprocess_cli.py`)

子进程型 CLI 后端基类,子类只负责拼命令行与提供 `parse_line`:

- `terminate_process_group(proc)` — 杀整个进程组(`start_new_session=True` 时子进程同组):先 `SIGTERM` 整组 → 2s 退出窗口 → 未退 `SIGKILL`;拿不到进程组时退回单进程 kill。
- `stream_subprocess_io(proc, *, message, cancel_event, parse_line)` — 写 stdin、逐行读 stdout 并 `yield` 事件:
  - 起一个 daemon 线程 drain `stderr`,结束时若 stderr 非空则 `yield ERROR`。
  - `cancel_event` 置位时,旁路 daemon 线程按 `CANCEL_POLL_SEC=0.3` 轮询,置位即 `terminate_process_group` 解除 stdout 阻塞并回收子进程。
  - 先 `yield` 当前行事件再检查 cancel,保证 `step_finish` / `result` 行仍能被读出。
  - `finally` 块 `stop_watch.set()` + `terminate_process_group` + join watcher,确保无残留进程。

## 变更维护

- **新增 EventKind**:改 `events.py`;评估是否需要进 `to_thinking_payload` 的排除集合(`SESSION`/`ERROR`)。
- **改 RunRequest / CLIAdapter 签名**:影响所有 adapter 子类,同步 `opencode/`、`claude/` 与上游 `agent_transport`。
- **改 SSE 事件形状**:与前端 `api-reference.md` 对齐,属前端契约变更,须走变更登记(见 `tests/test_api_contract.py` 同域)。
- **改子进程回收/cancel 逻辑**:谨慎,影响所有 CLI;补 `stream_subprocess_io` 的 cancel/stderr 路径测试。
