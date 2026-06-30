# Common 根测试

`common/tests/` 根目录的测试**不归属单一子模块**,而是覆盖:

1. **L0 测试** — 直接测 `common/` 根 L0 文件(`contracts.py` / `mcp_catalog.py`)
2. **跨模块集成测试** — 验证多模块协作流程(全链路 capstone、Hub 路由对齐、设置贯通、回归基线)

与 [`common/README.md`](../README.md) 的「L0 基础层」与「子模块协作流程」两节对应:子模块内部测试在各子目录 `tests/` 下,本目录只放**跨子模块**或**L0**测试。

## 目录结构

```
common/tests/
├── README.md                       ← 本文件
├── conftest.py                     ← 共享 fixture(task_types 注册表 + submit 绕过 dispatch)
├── fixtures/
│   └── task_types.yaml             ← 测试用 task_type 定义(隔离于生产 templates.yaml)
├── test_contracts.py               ← L0:contracts.py 契约
├── test_mcp_catalog.py             ← L0:mcp_catalog.py MCP 目录
├── test_integration.py             ← 集成:Phase 8 capstone 全链路
├── test_platform_e2e_baseline.py   ← 集成:P1 平台 E2E baseline
├── test_layer_b_web.py             ← 集成:Layer B distill/pending/memory
├── test_fe_hub_route_contract.py   ← 集成:前端 ↔ Hub 路由对齐
├── test_settings_config_contract.py← 集成:设置页 ↔ /api/config 字段
├── test_ui_config_linkage.py       ← 集成:Web 设置 ↔ 运行时贯通
├── test_r2_features.py             ← 集成:Store workspace_event + JobSupervisor
├── test_p1_default_review.py       ← 集成:default_review 默认值一致性
├── test_fix_be_contract.py         ← 集成:budget_degrade 空串 + models 剥离
├── test_reg_platform_v3_baseline.py← 集成:回归基线解析(依赖 scripts/regression)
└── test_regression_archive.py      ← 集成:regression_archive(依赖 scripts/regression)
```

## 测试清单(与目录实际文件一一对应)

### L0 测试(2 个)

| 文件 | 被测 L0 文件 | 验证内容 |
|------|--------------|----------|
| `test_contracts.py` | `common/contracts.py` | Interaction 契约(D11):各 kind 合法信封通过、非法 JSON/缺字段/自评缺失被拒而非被修;`submit_result.submit` 本地校验 |
| `test_mcp_catalog.py` | `common/mcp_catalog.py` | MCP 服务目录:`validate_mcp_ids` 过滤 disabled/unknown、server_id 校验、create/update/delete |

### 跨模块集成测试(11 个)

| 文件 | 覆盖协作流程 | 依赖子模块 |
|------|--------------|------------|
| `test_integration.py` | Phase 8 capstone:Process → AgentPort → AdapterTransport(FakeOpencode)→ Gate → Store → Observability 全链路 | process / agent / gate / store / observability / delivery |
| `test_platform_e2e_baseline.py` | P1 平台 baseline:Hub `/api/status` 200、Store roundtrip + `tokens_total`、roundtable parse、`kernel_run` meta | store / roundtable / runtime + `hub/` |
| `test_layer_b_web.py` | Layer B 后处理:`distill_ledger_body`、`pending` bundle、canonical USER.md | `execution_harness/post/` + `memstack/preferences/` |
| `test_fe_hub_route_contract.py` | 前端 `lib/api/*.ts` 的 `/api/` 路径与 Hub FastAPI 路由表对齐(parity) | `hub/api/server.py` + `frontend/src/lib/api/` |
| `test_settings_config_contract.py` | 设置页 `SettingsPage.tsx` 字段与 `/api/config`、`/api/skill-config` 覆盖一致(防漂移) | `hub/api/config_api.py` + `frontend/src/pages/SettingsPage.tsx` |
| `test_ui_config_linkage.py` | Web 设置 Tab 与运行时贯通:`kernel_configs_for_run` + `skill_settings` 读取 | runtime / skill + `config_store/` |
| `test_r2_features.py` | Store `workspace_event` 写入 + `JobSupervisor` 生产路径 | store / project |
| `test_p1_default_review.py` | `system.default_review` 默认值读取路径一致性(`DEFAULT_CONFIG` / `get()` / `get_all()` / `update_all()` 缓存同步) | `config_store/` + skill |
| `test_fix_be_contract.py` | `budget_degrade_backend/model` 空串短路 + `models` 字段从 `DEFAULT_CONFIG` 与 GET 响应剥离 | runtime / skill + `config_store/` |
| `test_reg_platform_v3_baseline.py` | 回归基线脚本逻辑:`parse_pytest_q_output`、`execute_double_run`、`runs_are_consistent` | `scripts/regression/reg_platform_v3_e2e_baseline.py` |
| `test_regression_archive.py` | `regression_archive` 归档逻辑 | `scripts/regression/regression_archive.py` |

## 共享 fixture

### `conftest.py`

两个 autouse fixture(所有根测试自动生效):

1. **`_test_task_type_registry`** — 用 `fixtures/task_types.yaml` 替换生产 `templates.yaml`,使单测不依赖业务配置
2. **`_framework_submit_bypass`** — 包装 `submit_result.submit`,绕过编排派发门(`require_dispatch=False`),单测可直接写回响应

### `fixtures/task_types.yaml`

测试用 task_type 定义(隔离于生产 `business/templates/templates.yaml`),被 L0/集成测试用作 registry 锚点。

## 运行方式

### 全部根测试

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/ -q
```

### 仅 L0 测试

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_contracts.py backend/common/tests/test_mcp_catalog.py -q
```

### 仅跨模块集成测试

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/ \
  --ignore=backend/common/tests/test_contracts.py \
  --ignore=backend/common/tests/test_mcp_catalog.py -q
```

### 单个测试

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_integration.py -q
```

## 外部依赖说明

- `test_fe_hub_route_contract.py` / `test_settings_config_contract.py` 依赖 `frontend/src/`(前端目录);若前端重命名(如 `web/`),需同步修正 `ROOT` 路径
- `test_reg_platform_v3_baseline.py` / `test_regression_archive.py` 依赖 `scripts/regression/`(项目根的回归脚本目录)
- `test_layer_b_web.py` 依赖 `execution_harness/` 与 `memstack/`(backend 同级模块)
- `test_platform_e2e_baseline.py` / `test_fe_hub_route_contract.py` 依赖 `hub/` 与 `fastapi` / `httpx`

## 变更维护

- **新增根测试**:先判断是 L0 测试(测根文件)还是跨模块集成测试(测多模块协作);放入本目录后,更新本 README 的「测试清单」表
- **L0 文件新增/删除**:同步更新 `common/README.md` 的「L0 基础层」表 + 本 README 的「L0 测试」清单
- **子模块拆分/合并**:若新模块带新的协作流程,在 `common/tests/` 增加集成测试覆盖,并更新本 README 的「跨模块集成测试」表
- **外部依赖路径变化**(如 frontend 改名):同步修正本 README 的「外部依赖说明」+ 测试文件内的 `ROOT` 路径
- **conftest.py / fixtures/ 变更**:更新本 README 的「共享 fixture」节
- **功能变更后**:重跑全部根测试 + 相关子模块测试,确保零回归
