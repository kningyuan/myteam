# Backend 模块总览

myteam 后端由 **7 个顶层模块** 组成,支撑两条正交流程:人机交互流(chat/group,streaming)与编排内核流(goal→task DAG,batch)。每个模块自包含 `README.md` + `tests/`,边界清晰、依赖单向。

## 两大正交流程

```
A) Chat / Group(人 ↔ agent,流式):
  frontend/ → hub/api → hub/services/chat_service → base/agent_chat
            → adapter/registry → adapters/opencode → AgentEvent → SSE → UI

B) Orchestration Kernel(goal → task DAG,批处理):
  run_kernel.py → common/process(DAG 状态机)
                → common/agent(AgentPort + transport → adapter subprocess → AgentEvent)
                → common/gate(契约 + 格式 + 完整性校验)
                → common/store(SQLite 真相)
                → common/observability(只读审计)
```

**关键区别**:A 流程走 Hub HTTP 入口,实时流式;B 流程走 CLI 入口,批处理,不需要 Hub 运行。两者共享同一 SQLite 真相库(`business/tasks/state.db`)。

## 模块拓扑与依赖方向

```
                         ┌──────────────────────────────────────────┐
                         │                 hub/                      │  ← A 流程 HTTP 入口
                         │  api/(FastAPI 薄路由) + services/(业务)    │
                         └──────┬──────────────┬─────────────┬────────┘
                                │              │             │
                    ┌───────────▼──┐   ┌───────▼──────┐  ┌──▼──────────────┐
                    │    base/     │   │ config_store/ │  │ execution_harness│
                    │ (Hub 业务层) │   │ (持久化配置)  │  │ (pre/post 处理)  │
                    └──────┬───────┘   └──────┬───────┘  └──────────────────┘
                           │                  │
                    ┌──────▼──────────────────▼──────┐
                    │          adapter/               │  ← CLI 隔离层
                    │  core/ + opencode/ + claude/    │
                    └─────────────────────────────────┘
                                       ▲
                    ┌──────────────────┴──────────────────┐
                    │            common/                   │  ← B 流程编排内核
                    │  13 子模块(process/agent/gate/store  │
                    │  /observability/delivery/loop/...)   │
                    └──────────────────────────────────────┘

  独立栈(被多模块调用):
    config_store/  ← 系统最底层配置(base/hub/common/adapter 都依赖)
    memstack/      ← 记忆/偏好/知识库(base.agent_chat 是入口)
    execution_harness/ ← 自我改进引擎(hub 间接调用,独立于 kernel 主循环)
```

**依赖规则**:上层依赖下层,同层不互相依赖。`common` 不依赖 `hub`;`base` 不依赖 `hub`(base 的 stream_chat 是正向委托);`config_store` 不依赖任何业务模块;`adapter` 只被 `common.agent` 和 `hub.services.chat_service` 调用。

## 模块清单

| 模块 | 定位 | 子目录数 | README | tests | 测试用例 |
|------|------|---------|--------|-------|---------|
| **common/** | L1/L2 编排内核(goal→DAG 状态机) | 13 子模块 + project_lib | [README](./common/README.md) | common/tests/ + 13 子模块 tests/ | ~200+ |
| **adapter/** | CLI 隔离层(opencode/claude) | core/ + opencode/ + claude/ | [README](./adapter/README.md) | adapter/tests/ | 42 |
| **base/** | Hub 侧 A 流程业务逻辑层 | — (4 文件) | [README](./base/README.md) | base/tests/ | 55 |
| **config_store/** | 纯持久化配置层 | — (3 文件) | [README](./config_store/README.md) | config_store/tests/ | 50 |
| **hub/** | Web Hub 表现层 + 服务层 | api/ + services/ | [README](./hub/README.md) | hub/services/tests/ | 48 |
| **execution_harness/** | 自我改进引擎(pre/post) | pre/ + post/ + identity/ + ... | [README](./execution_harness/README.md) | execution_harness/tests/ | — |
| **memstack/** | 记忆/偏好/知识库栈 | l1/ + kb/ + preferences/ + orchestration/ | [README](./memstack/README.md) | memstack/tests/ | — |

## 各模块职责速览

### common/ — 编排内核(框架冻结)

goal → task DAG 的状态机内核。6 大抽象:**Process / AgentPort / Gate / Store / contracts / observability**。13 个功能子模块各含 README + tests,根目录 `common/tests/` 放 L0 基础层测试 + 跨模块集成测试。入口:`runtime/run_kernel.py`。真相源:`store/store.py` → SQLite。详见 [common/README.md](./common/README.md)。

### adapter/ — CLI 隔离层

核心不变量(AGENTS.md §10):唯二跨 CLI 数据契约 = `RunRequest` + `AgentEvent`;`adapters/<cli>/parser.py` 是唯一允许知道 CLI 原始输出格式的地方。三层结构:core/(抽象层) + opencode/(实现) + claude/(实现)。新增 CLI = 新建 `adapters/<cli>/` + parser + 末尾 `registry.register()`。详见 [adapter/README.md](./adapter/README.md)。

### base/ — Hub 侧业务逻辑层

A 流程(chat/group)的中间层,被 `hub/api` 调用,向下委托 `adapter` 与 `config_store`。4 文件分层协作:`agent_identity`(基础)→`agent_chat`(中枢)→`agent_factory`+`group_manager`。详见 [base/README.md](./base/README.md)。

### config_store/ — 持久化配置层

系统最底层配置依赖,3 个互不引用的 JSON 配置存储单例:`system_config`(端口/backend/model/CLI 路径)、`skill_config`(executor 超时/process 预算/圆桌参数)、`session_store`(Adapter 无关会话映射)。只依赖 `common.paths`。详见 [config_store/README.md](./config_store/README.md)。

### hub/ — Web Hub 表现层

FastAPI HTTP 入口 + 业务服务层。`api/`(11 个直接路由文件 + 10 个域路由 + server.py 装配) + `services/`(14 个业务服务:SSE 桥接、对话服务、项目调度、广播)。SSE 推流链:路由→`sse_bridge`→`chat_service`→`stream_fanout`→`agent_broadcast`/`group_broadcast`。项目调度链:`project_launch`→`kernel_run`→`project_hooks`→`project_group_service`。详见 [hub/README.md](./hub/README.md)。

### execution_harness/ — 自我改进引擎

Agent 任务执行的前/后处理框架。`pre/`(准备 + 注入)、`post/`(蒸馏 + 审批 + 提升)、`identity/`(bounded 身份)、`skill/`(umbrella + references)。独立于 kernel 主循环,由 `hub/services/single_execute_service` 和 `chat_service` 间接调用。详见 [execution_harness/README.md](./execution_harness/README.md)。

### memstack/ — 记忆/偏好/知识库栈

分层记忆系统:`l1/`(短期对话记忆,mem0/native/sqlite/noop)、`kb/`(知识库,sqlite/store_adapter)、`preferences/`(偏好库,sectioned/user_store)、`orchestration/`(经验检索 + 上下文)。`base/agent_chat.py` 是 memstack 的入口。详见 [memstack/README.md](./memstack/README.md)。

## 测试体系

### 运行方式

```bash
# 全部 backend 测试
PYTHONPATH=backend python3 -m pytest backend -q

# 单模块
PYTHONPATH=backend python3 -m pytest backend/common/tests/ -q
PYTHONPATH=backend python3 -m pytest backend/adapter/tests/ -q
PYTHONPATH=backend python3 -m pytest backend/base/tests/ -q
PYTHONPATH=backend python3 -m pytest backend/config_store/tests/ -q
PYTHONPATH=backend python3 -m pytest backend/hub/services/tests/ -q

# 单个测试
PYTHONPATH=backend python3 -m pytest backend/common/tests/test_integration.py -q
```

### 测试分层

| 层级 | 位置 | 覆盖内容 |
|------|------|---------|
| **L0 基础层** | 各模块根 tests/ | 零依赖基础文件(common/contracts.py、config_store 单例) |
| **子模块单元** | 各子模块 tests/ | 单一子模块内部逻辑(隔离 fixture,不依赖外部) |
| **跨模块集成** | common/tests/ | 多模块协作流程(Process→AgentPort→Adapter→Gate→Store 全链路) |
| **模块级集成** | base/tests/、hub/services/tests/ | 模块内多文件协作(base 分层、hub SSE 推流链) |
| **契约测试** | adapter/tests/test_api_contract.py、common/tests/test_fe_hub_route_contract.py | 前后端接口形状防漂移 |

### 测试约束

- `PYTHONPATH=backend` 必须设置(测试 import `common`/`hub`/`adapter` 等包)
- 用 `tmp_path` / `monkeypatch` 隔离,绝不写真实 `config/` 或 `business/`
- 不依赖外部 CLI(opencode/claude 未安装时用 FakeAdapter / mock)
- 不启动真实 Hub 服务器(FastAPI 用 TestClient)

## 变更维护

- **新增顶层模块**:在 `backend/<新模块>/` 下建 `__init__.py` + 代码 + `tests/` + `README.md`;更新本 README 的模块清单表 + 拓扑图
- **新增子模块**:参照 `common/` 13 个子模块的模板(`__init__.py` + 代码 + `tests/` + `README.md`);更新所属模块 README
- **跨模块协作变更**:在 `common/tests/` 增加集成测试覆盖;更新 `common/tests/README.md` 清单
- **依赖方向变更**:本 README 的拓扑图是依赖真相源;任何 import 方向变更须同步更新拓扑图 + 相关模块 README 的边界表
- **功能变更后**:重跑相关模块 `tests/` + `common/tests/` 根测试,确保零回归
