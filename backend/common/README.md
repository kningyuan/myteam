# Common 编排内核

myteam 的 L1/L2 编排内核(`backend/common/`),实现 **Process / AgentPort / Gate / Store / contracts / observability** 六大抽象。框架冻结边界(`docs/FRAMEWORK-FREEZE.md`):新能力进 `business/workflows/` 与 `business/skills/`,不在此处重构。

## 整体职责

| 维度 | 说明 |
|------|------|
| **是什么** | goal → task DAG 的状态机内核:分解、调度、门控、重试、归档 |
| **不是什么** | 不是 CLI 适配层(在 `adapter/`);不是 Hub Web 服务(在 `hub/`);不是配置存储(在 `config_store/`);不是记忆/偏好栈(在 `memstack/`) |
| **入口** | `runtime/run_kernel.py`(`backend/common/run_kernel.py <project_id> --goal ...`) |
| **真相源** | `store/store.py` → SQLite (`business/tasks/state.db`) |

## L0 基础层(根文件)

`common/` 根目录的 5 个文件是零依赖基础层,被所有子模块共享,**不可反向依赖子模块**:

| 文件 | 职责 |
|------|------|
| `__init__.py` | 包标识 |
| `paths.py` | 路径常量唯一来源(`MYTEAM_ROOT`/`BACKEND_DIR`/`BUSINESS_DIR` 等);`parents[2]` 锚定 myteam root |
| `contracts.py` | Interaction 统一契约(D11/D5/D15):`InteractionRequest` / `InteractionResponse` 辨识联合,`SCHEMA_VERSION = "1.0"` |
| `coordinator.py` | 协调者 agent_id 获取(默认 `main`),消除硬编码 |
| `mcp_catalog.py` | MCP 服务目录,读 `business/config/mcp_registry.json`,提供 `validate_mcp_ids` 等 |

## 子模块协作流程

13 个功能子目录(每个含 `README.md` + `tests/`,自包含可测):

```
                    ┌─────────────────────────────────────────────┐
                    │              runtime/run_kernel             │  ← 入口
                    │  (kernel_config + run_kernel + hooks + gc)  │
                    └──────────────────────┬──────────────────────┘
                                           │ 启动
                                           ▼
┌──────────────┐   team_config    ┌────────────────┐   task_plan    ┌──────────────┐
│  workflow/   │ ───────────────▶ │   process/     │ ─────────────▶ │   agent/     │
│ (bootstrap + │                  │ (DAG 状态机)   │                 │ (AgentPort + │
│  validate)   │ ◀─────────────── │                │ ◀───────────── │  transport)  │
└──────────────┘    hooks         └────┬────┬──────┘   submit       └──────┬───────┘
                                         │    │                            │ RunRequest
                                         │    │                            ▼
                                         │    │                   ┌─────────────────┐
                                         │    │                   │   adapter/      │  ← CLI 隔离层
                                         │    │                   │ (opencode/claude)│   (backend/adapter/)
                                         │    │                   └────────┬────────┘
                                         │    │                            │ AgentEvent
                                         │    ▼                            ▼
                                         │ ┌──────────────┐    ┌────────────────────┐
                                         │ │  delivery/   │    │     gate/          │
                                         │ │ submit_result│    │ (contract + format │
                                         │ │ + templates  │    │  + registry)       │
                                         │ └──────┬───────┘    └─────────┬──────────┘
                                         │        │ response              │ pass/fail
                                         │        ▼                       ▼
                                         │ ┌──────────────────────────────────────┐
                                         │ │            store/                    │
                                         │ │ (SQLite 真相:project/task/interaction)│
                                         │ └──────────────┬───────────────────────┘
                                         │                │ 只读
                                         │                ▼
                                         │ ┌──────────────────────────────────────┐
                                         │ │         observability/                │
                                         │ │ (audit_log + token_usage + ops_log)   │
                                         │ └──────────────────────────────────────┘
                                         │
                                         │ 循环/复盘
                                         ▼
                                  ┌──────────────┐    ┌──────────────┐
                                  │   loop/      │    │ roundtable/  │
                                  │ (loop runtime│    │ (group msg   │
                                  │  + discussion)│   │  + context)  │
                                  └──────────────┘    └──────────────┘

  横切(被多模块依赖):
    paths/contracts/coordinator/mcp_catalog   ← L0 基础层
    prompt/    ← context_assembler + prompt_composer(被 agent/process 用)
    skill/     ← skill_catalog + skill_settings(被 agent/hub 用)
    project/   ← project_admin + project_runtime + job_supervisor + project_cancel
```

### 循环依赖(已用懒加载破除,标注供维护参考)

- **R1**: `agent/agent_port.py` ↔ `project/project_cancel.py`(跨 project 聚类,`agent_port` 内懒加载 `project_cancel`)
- **R2**: `gate/task_type_store.py` ↔ `gate/task_type_suggest.py`(同模块内,通过函数级 import 破除)
- **R3**: `loop/` ↔ `workflow/`(`loop` 通过 `workflow_loader` 读 workflow 定义,`workflow` 不反向依赖 `loop`)

## 与其他 backend/ 模块的边界

| 模块 | 关系 | 边界规则 |
|------|------|----------|
| `adapter/` | common 通过 `agent/agent_transport.py` 调用 | common 只见 `RunRequest` / `AgentEvent`,不见 CLI 原始输出(`docs/ARCHITECTURE.md` §10) |
| `config_store/` | common 通过 `paths.py` + `coordinator.py` 读配置 | common 不直接写 `config/`,只读 `system_config.json` / `skill_config.json` |
| `base/` | common 不依赖 base;base 依赖 common | `base/agent_chat.py` 调 `common.agent.agent_registry`;反向禁止 |
| `hub/` | hub 依赖 common(common 不依赖 hub) | `hub/api/observability_api.py` 只读 common 的 SQLite;`hub/services/kernel_run.py` 调 `common.runtime.run_kernel` |
| `memstack/` | common 通过 `agent/` 间接调用 | common 不直接 import `memstack`;`base/agent_chat.py` 才是 memstack 的入口 |
| `execution_harness/` | common 不依赖;hub 间接调用 | `execution_harness/` 是 post/pre 处理,独立于 kernel 主循环 |

## 特殊目录:`project_lib/`

`project_lib/meta.py` 定义 `ProjectMeta` / `TaskMeta` 两个共享 Pydantic 模型,被 `project/` 与 `store/` 复用。**不单独建 tests**(由 `project/tests/` 与 `store/tests/` 覆盖),**不单独建 README**(由本节说明)。

## 测试

### 子模块测试(13 个)

每个子目录 `tests/` 内的测试只测本模块,运行方式见各自 `README.md`。统一入口:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/<子模块>/tests/ -q
```

### 根测试(`common/tests/`)

`common/tests/` 根目录的测试**不归属单一子模块**,分两类:

1. **L0 测试(2 个)** — 直接测 `common/` 根 L0 文件:
   - `test_contracts.py` → `contracts.py`(Interaction 契约 D11)
   - `test_mcp_catalog.py` → `mcp_catalog.py`(MCP 服务目录)

2. **跨模块集成测试(11 个)** — 验证多模块协作流程:
   - `test_integration.py` — Phase 8 capstone 全链路(Process→AgentPort→Adapter→Gate→Store→Observability)
   - `test_platform_e2e_baseline.py` — P1 平台 baseline(Hub health + Store + roundtable + kernel_run)
   - `test_layer_b_web.py` — Layer B 后处理(distill/pending/user_store,跨 execution_harness/memstack)
   - `test_fe_hub_route_contract.py` — 前端 ↔ Hub 路由对齐
   - `test_settings_config_contract.py` — 设置页 ↔ `/api/config` 字段覆盖
   - `test_ui_config_linkage.py` — Web 设置 ↔ 运行时贯通
   - `test_r2_features.py` — Store workspace_event + JobSupervisor
   - `test_p1_default_review.py` — `default_review` 默认值读取一致性
   - `test_fix_be_contract.py` — budget_degrade 空串短路 + models 字段剥离
   - `test_reg_platform_v3_baseline.py` — 回归基线解析(依赖 `scripts/regression/`)
   - `test_regression_archive.py` — regression_archive 归档(依赖 `scripts/regression/`)

共 13 个测试文件,与 `common/tests/` 目录实际文件一一对应。详细运行方式、共享 fixture、外部依赖说明见 [`tests/README.md`](./tests/README.md)。

## 变更维护

- **新增子模块**:在 `common/<新模块>/` 下建 `__init__.py` + 代码 + `tests/` + `README.md`(参照 13 个现有子模块模板);更新本 README 的「子模块协作流程」图
- **新增 L0 根文件**:必须零依赖子模块;更新本 README 的「L0 基础层」表
- **新增根测试**:判断是 L0 测试还是跨模块集成测试,放入 `common/tests/` 并更新 `tests/README.md` 清单
- **删除/重命名文件**:同步更新本 README 的「L0 基础层」表 + 对应子模块 README 的「核心文件」清单 + `tests/README.md` 的测试清单
- **功能变更**:重跑相关子模块 `tests/` + `common/tests/` 根测试,确保零回归
