# Base 业务逻辑层

myteam 的 **Hub 侧 A 流程（人机交互）业务逻辑层**（`backend/base/`），处于 `hub/api` → `base` → `adapter` / `config_store` 之间：把 Agent 身份识别、后端配置、Agent 创建、群组管理与 @mention 路由等 Hub 侧业务聚合起来，向上对 `hub/api` 暴露函数式 API，向下经 `hub.services.chat_service` 委托到 `adapter` 抽象层。

> 与 `common/`（编排内核 B 流程）正交：`common` 做 goal → task DAG 的状态机；`base` 做人 ↔ agent 的会话/群组/配置。`common` 不依赖 `base`，`base` 依赖 `common`（见下文边界表）。

## 整体职责

| 维度 | 说明 |
|------|------|
| **是什么** | Hub 侧 A 流程的业务逻辑层：Agent 身份、后端配置、Agent 创建、群组 CRUD + @mention 路由 |
| **不是什么** | 不是 Web 服务（在 `hub/api`）；不是 CLI 适配层（在 `adapter/`）；不是配置存储（在 `config_store/`）；不是编排内核（在 `common/`） |
| **入口** | 被 `hub/api/*` 直接调用（如 `hub/api/agent_api.py`、`hub/api/group_api.py`） |
| **真相源** | workspace 身份文件（`business/workspaces/workspace-<id>/`）+ `agents_config.json` + `groups.json` |

## 文件清单

4 个 `.py` 文件，分层清晰：

| 文件 | 职责 | 关键类 / 函数 | 依赖 |
|------|------|---------------|------|
| `agent_identity.py` | Agent 身份识别。读 workspace 下 `IDENTITY.md`/`SOUL.md`/`USER.md`（文件名列表来自 `common.paths.IDENTITY_FILES`），正则提取中文名/角色；拼装身份文本块与 prompt 前缀 | `AgentIdentityBuilder`、`MultiAgentManager`、模块级单例 `multi_agent_manager`、`extract_chinese_name`（含 ID→中文名兜底映射，`main`→项目协调专家）、`get_identity_context`、`get_agent_prompt_prefix`、`build_multi_agent_context` | `common.coordinator`、`common.paths` |
| `agent_chat.py` | **中枢**。轻量级本地 Agent 交互核心：后端配置管理、Agent 扫描、系统提示构建、流式对话、删除/清空 | `BackendConfig`、`_load/_save_agents_config`、`get/set_agent_backend_config`、`apply_model_to_all`、`delete_agent_config`、`scan_agents`、`build_system_prompt`、`stream_chat`、`delete_agent`、`clear_agent_chat_context` | `common.paths`、`config_store.system_config`、`base.agent_identity`；运行时懒加载 `common.agent.*`、`hub.services.chat_service`、`memstack.l1`、`execution_harness.pre.interactive`、`adapter`（side-effect 注册） |
| `agent_factory.py` | 一键创建 Agent。创建 workspace（含 `.trigger`/`.response` 子目录），通过 LLM 或模板生成身份文件，写后端配置，推测 task_types，注册到 `agents_registry.json` | `generate_agent`、`_generate_via_llm`、`_generate_template`、`_extract_name_from_identity`、`suggest_agent_id`、`list_available_agent_ids` | `common.paths`、`base.agent_chat`、`hub.services.agent_registry`；运行时 `common.agent.agent_task_type_suggest`、`adapter` |
| `group_manager.py` | **最大文件**。群组 CRUD + @mention 路由 + 圆桌讨论（设置解析、发言顺序、prompt 构建、共识投票统计、轮次执行、转录） | `_load/_save_groups`、`create/delete/dissolve/restore/list/get/search_groups`、`add/remove_member`、`reorder_group_members`、`resolve_mentions`、`detect_group_mode`、`format_group_context`、圆桌设置/轮次/共识投票系列 | `common.paths`、`common.coordinator`、`base.agent_chat`、`hub.services.stream_fanout`；运行时 `memstack.l1`、`hub.services.group_broadcast`、`common.skill.skill_settings`、`common.roundtable.group_message_store` |

## 内部分层协作

依赖链（`agent_factory` 与 `group_manager` 之间无直接依赖，二者都只向上依赖 `agent_chat`）：

```
                 ┌──────────────────────────────────────┐
   基础层         │        agent_identity.py             │  只依赖 common
                 │  AgentIdentityBuilder /              │  （coordinator + paths）
                 │  MultiAgentManager (单例)            │
                 └──────────────────┬───────────────────┘
                                    │ import AgentIdentityBuilder,
                                    │ multi_agent_manager
                                    ▼
                 ┌──────────────────────────────────────┐
   中枢          │        agent_chat.py                 │  顶层 import
                 │  BackendConfig / 配置管理 /          │  config_store.system_config
                 │  scan_agents / build_system_prompt / │
                 │  stream_chat (委托 hub.services)     │
                 └─────────┬────────────────┬───────────┘
                           │                │  import get/set_agent_backend_config,
              ┌────────────┘                │  scan_agents, stream_chat
              ▼                             ▼
   ┌────────────────────────┐   ┌────────────────────────────┐
   │  agent_factory.py      │   │  group_manager.py          │
   │  一键创建 Agent         │   │  群组 CRUD + @mention 路由  │
   │  (LLM/模板生成身份)     │   │  + 圆桌讨论                │
   └────────────────────────┘   └────────────────────────────┘
            ↑ 无直接依赖 ↑                   ↑ 无直接依赖 ↑
            └─────── 二者都只向上依赖 agent_chat ────────┘
```

`stream_chat` 是唯一对外部（`hub.services.chat_service` → `adapter`）的调用出口；`agent_factory._generate_via_llm` 与 `group_manager` 的圆桌执行都经它走。

## 与其他 backend/ 模块的边界

| 模块 | 关系 | 边界规则 |
|------|------|----------|
| `common/` | base 依赖 common（`paths`/`coordinator`/`agent`/`roundtable`/`gate`/`skill`/`store`） | common **不依赖** base；`base.agent_chat` 调 `common.agent.agent_registry` 等属正向调用，反向禁止 |
| `config_store/` | base 依赖（`system_config` 读配置、`sessions` 清会话） | base 经 `paths` 读 `system_config`，不直接写 `config/`；`sessions` 仅在 `delete_agent`/`clear_agent_chat_context` 中清映射 |
| `adapter/` | base 间接依赖（`get_backend_models`/`list_all_backends_with_models` 经 adapter registry；side-effect `import adapter` 注册 CLI） | base **不解析** CLI 原始输出；`stream_chat` 经 `hub.services.chat_service` → `adapter`，base 不直接 `subprocess` |
| `hub/services/` | **双向**：`hub/api` + `hub/services` 消费 base；base 的 `stream_chat` 委托 `hub.services.chat_service`（正向调用，非反向依赖） | base 是 Hub 侧业务层；`hub/api` 调 base 暴露的函数，base 调 `hub.services.chat_service`/`agent_registry`/`stream_fanout` |
| `memstack/` | base 经 `stream_chat`/`build_system_prompt` 懒加载调用 | base 不在模块顶层持有 memstack；`stream_chat` 内按 scope 选择 `memory_scope_dm/group/roundtable` |
| `execution_harness/` | base 经 `build_system_prompt` 懒加载调用 `pre.interactive` | base 不依赖 `execution_harness` post 处理；仅拼装 interactive harness block |

## 测试

### 本目录测试（`tests/`）

3 个测试文件，共 55 个用例，全部用 `tmp_path` 隔离，不依赖外部 CLI 与 Hub 服务器：

```bash
PYTHONPATH=backend python3 -m pytest backend/base/tests/ -q
```

| 文件 | 覆盖范围 |
|------|----------|
| `test_agent_identity.py` | `AgentIdentityBuilder`（读 IDENTITY.md 提取中文名/角色、`get_identity_context`、`get_agent_prompt_prefix`、`extract_chinese_name` 兜底映射）、`MultiAgentManager.build_multi_agent_context` |
| `test_agent_chat.py` | 后端配置管理（`get/set_agent_backend_config`、`_load/_save_agents_config`、`apply_model_to_all`、`delete_agent_config`）、`scan_agents` 扫描 workspace。不测 `stream_chat`（已 mock） |
| `test_group_manager.py` | 群组 CRUD（`create/list/get/delete/dissolve/restore_group`、`search_groups`）、成员管理（`add/remove_member`）、@mention 路由（`resolve_mentions`/`detect_group_mode`）。不测圆桌讨论执行（依赖 `stream_chat`） |

`conftest.py` 隔离策略（参照 `backend/common/roundtable/tests/conftest.py` 风格）：

- **路径重定向**：用 `tmp_path` 重定向 `common.paths` 的 `WORKSPACES_DIR`/`AGENTS_CONFIG_FILE`/`GROUPS_FILE`/`GROUP_ARCHIVES_FILE` 等常量。**关键**：base 各子模块在 `from common.paths import XXX` 时已把常量**按名绑定**到自身命名空间，仅 patch `common.paths` 不够，必须逐一 patch 各 base 子模块（`base.agent_identity`/`base.agent_chat`/`base.group_manager`）的绑定。
- **外部调用 mock**：`stream_chat`（委托 `hub.services`，需 Hub 运行）在 `base.agent_chat` 与 `base.group_manager` 两处绑定均替换为空生成器；`system_config` 替换为 stub，避免读写真实 `config/system_config.json`。
- 绝不写真实 `config/` 或 `business/`。

### 间接覆盖（其它模块测试）

base 的部分功能已被 `common/` 侧测试间接覆盖：

- `common/roundtable/tests/test_group_roundtable.py`、`test_group_mentions.py` — 覆盖 `group_manager` 的圆桌讨论（共识投票/发言顺序/终止命令）与 @mention 路由（`detect_group_mode`/`resolve_mentions`/`extract_agenda`）。
- `common/agent/tests/test_apply_model.py` — 覆盖 `agent_chat.apply_model_to_all`（批量应用 model + 跨后端迁移 + 保留字段）。

## 变更维护

- **新增文件**：遵循 identity → chat → {factory, group_manager} 的分层；新文件若依赖 `agent_chat`，放在其上层；不得让 `agent_identity` 反向依赖 `agent_chat`/`group_manager`。同步更新本 README 的「文件清单」表与分层图。
- **新增外部依赖**：`stream_chat` 是唯一对外出口，新增对外调用（`hub.services`/`memstack`/`adapter`）一律懒加载（函数级 import），保持模块顶层 import 轻量；在边界表中登记。
- **路径常量**：base 各子模块按名绑定了 `common.paths` 常量，新增绑定时须在 `tests/conftest.py` 的 `isolated_paths` fixture 中同步 patch，否则测试会写真实 `business/`。
- **新增群组/Agent 字段**：先在 `group_manager._load/_save_groups` 或 `agent_chat._load/_save_agents_config` 落盘结构中加字段，再补 `tests/` 用例。
- **功能变更**：重跑 `backend/base/tests/`；若改了 `group_manager` 圆桌/路由或 `agent_chat.apply_model_to_all`，同时重跑 `common/roundtable/tests/` 与 `common/agent/tests/test_apply_model.py` 确保零回归。
