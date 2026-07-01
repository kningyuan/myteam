# myteam 工程行为规范

本规范约束所有向 myteam 仓库提交代码、配置、文档的行为。**核心目标：文件各归其位，工程可维护。**

AGENTS.md 是架构不变量的权威源（adapter 隔离、交互契约、三层职责）。本规范是 AGENTS.md 的补充，聚焦"什么文件放什么目录"。

---

## 一、目录归属总表

| 目录 | 放什么 | 不放什么 | 入库 |
|------|--------|----------|------|
| `backend/common/` | 编排内核：process/gate/store/agent/delivery/contracts/paths | UI 代码、CLI 专属解析 | ✅ |
| `backend/adapter/` | CLI 适配器（opencode/claude），每个 CLI 一个子目录 | 业务逻辑、Hub 服务 | ✅ |
| `backend/base/` | Agent 基础设施：chat/factory/identity/group | 编排逻辑、CLI 解析 | ✅ |
| `backend/hub/` | Web Hub：API 路由 + 服务层（FastAPI） | 编排内核逻辑 | ✅ |
| `backend/config_store/` | 系统配置读写（system_config/skill_config/sessions） | 业务配置 | ✅ |
| `backend/execution_harness/` | 执行挽具：pre/injection/post/skill/identity | 编排内核 | ✅ |
| `backend/memstack/` | 记忆栈：l1/kb/preferences/orchestration/injection | 编排逻辑 | ✅ |
| `business/templates/` | 策略注册表：templates.yaml（task_type 定义）、business-roster.json、delivery_templates | Skill 内容、代码 | ✅ |
| `business/skills/` | Skill Pack：每个 skill 一个目录，含 SKILL.md | 非 skill 的文档 | ✅ |
| `business/workflows/` | Workflow 模板 YAML | 代码、skill | ✅ |
| `business/rules/` | 角色行为规则 markdown（ethos/worker-template 等） | 代码 | ✅ |
| `business/hooks/` | 业务钩子 Python 脚本 | 通用工具 | ✅ |
| `business/experience/` | 经验沉淀模板和 schema | 运行态数据 | ✅ |
| `business/playbooks/` | 操作手册和脚本模板 | 运行态数据 | ✅ |
| `business/means/` | 工具手段（diagram-build 等） | 业务配置 | ✅ |
| `business/regression/` | 回归测试结果（JSON） | 源码 | ✅ |
| `frontend/src/` | 前端源码（React + TS） | 后端代码 | ✅ |
| `scripts/` | 一次性脚本、bootstrap、工具 | 运行态业务数据 | ✅ |
| `config/` | 系统配置 JSON（运行态生成） | 源码 | ❌ gitignore |
| `business/config/` | 业务配置（agents_config/agents_registry/groups） | 源码 | ❌ gitignore |
| `business/workspaces/` | Agent workspace（运行态） | 源码 | ❌ gitignore |
| `business/tasks/` | 任务运行态数据（state.db、交付物） | 源码 | ❌ gitignore |

---

## 二、后端代码归属规则

### 2.1 三层职责（来自 AGENTS.md，不可违反）

| 层 | 位置 | 放什么 |
|----|------|--------|
| **System Kernel** | `backend/common/`, `backend/adapter/`, `backend/hub/api/observability_api.py` | 必须可测试、可恢复、可审计、可重试、可持久化的逻辑 |
| **Strategy Registry** | `business/templates/templates.yaml`, `business/config/agents_registry.json`, `business/rules/` | task_type 定义、角色名册、验收标准 |
| **Skill Pack** | `business/skills/*/SKILL.md`, agent workspace 的 `AGENTS.md`/`IDENTITY.md` | 单一任务类型的执行方法论 |

**决策规则**：
- 失败会污染系统状态 → System Kernel
- 改变 task_type / 角色选择 / 验收标准 → Strategy Registry
- 只影响单个任务质量 → Skill

### 2.2 模块内文件归属

| 模块 | 只放 | 禁止放 |
|------|------|--------|
| `backend/common/agent/` | agent 生命周期：port/transport/registry/skills/mcp/model | 编排调度、Gate 校验 |
| `backend/common/process/` | DAG 调度、plan 展开、process 状态机 | CLI 解析、UI 逻辑 |
| `backend/common/gate/` | Gate 校验、registry、task_type_store、rules_merge | agent 执行逻辑 |
| `backend/common/store/` | SQLite 持久化、store_backend、task_data_store | 业务逻辑 |
| `backend/common/delivery/` | 交付物保障、submit_result、delivery_profiles/templates | 编排调度 |
| `backend/common/observability/` | 审计日志、ops_log、thinking_trace、token_usage | 状态变更 |
| `backend/common/loop/` | 循环运行时（discussion/workflow） | 非循环逻辑 |
| `backend/common/workflow/` | workflow 加载/校验/建议/能力绑定 | 循环运行时 |
| `backend/common/project/` | 项目管理：admin/artifacts/cancel/runtime/hooks | 内核调度 |
| `backend/common/prompt/` | prompt 组装、注入、模板 | 业务逻辑 |
| `backend/common/roundtable/` | 圆桌讨论运行时 | 非讨论逻辑 |
| `backend/common/runtime/` | 内核运行入口：run_kernel/kernel_config/workspace_gc | 重复的内核逻辑 |
| `backend/common/skill/` | skill 目录管理、分类、提取、链接 | skill 内容本身 |
| `backend/hub/api/routes/` | FastAPI 路由定义（薄层，委托 service） | 业务逻辑实现 |
| `backend/hub/services/` | Hub 服务层（chat/project/group/kernel_run 等） | CLI 专属代码 |
| `backend/adapter/<cli>/` | 单个 CLI 的 adapter + parser + mcp_sync + skill_sync | 业务逻辑、其他 CLI 的代码 |

### 2.3 Adapter 隔离不变量（最高优先级）

- `adapters/<cli>/parser.py` 是**唯一**允许知道 CLI 原始输出格式的地方
- `hub/services/`、`base/` **禁止**包含 `opencode` 或 `subprocess` 字样
- UI **禁止**引用 CLI 专属字段（`part.text`、`sessionID`、原始 JSON）
- 新增 CLI = 新建 `adapters/<cli>/` 目录 + parser + 更新 `agent_transport._default_adapter()`，**不改 UI**

### 2.4 测试归属

| 测试位置 | 测什么 |
|----------|--------|
| `<module>/tests/` | 模块内部单元测试 + 模块间协作测试 |
| `backend/common/tests/` | 跨模块集成测试、契约测试、端到端 baseline |
| `backend/hub/services/tests/` | Hub 服务层测试 |
| `backend/<module>/tests/conftest.py` | 模块级 fixture（autouse token 注入等） |

**规则**：
- 每个功能模块必须有 README + 测试，覆盖子功能 + 模块间协作
- 测试文件命名：`test_<被测模块>.py`
- conftest.py 只放 fixture，不放测试断言

---

## 三、前端代码归属规则

| 路径 | 放什么 |
|------|--------|
| `frontend/src/pages/` | 路由页面组件 |
| `frontend/src/sections/` | 页面内 section（Dashboard/Execute/Manage/Skills/Chat 等） |
| `frontend/src/sections/manage/` | 管理页子面板（Agents/TaskTypes/Templates/Knowledge 等） |
| `frontend/src/components/` | 可复用组件（layout/ui/chat/skills/manage 等） |
| `frontend/src/lib/api/` | API 客户端函数（按域分文件：agents/projects/workflows/execute 等） |
| `frontend/src/hooks/` | 自定义 React Hook |
| `frontend/src/styles/` | CSS 文件（tokens/base/components/markdown/animations） |
| `frontend/src/test/` | 测试 setup 和工具 |

**规则**：
- UI **禁止**引用 CLI 专属字段，只消费 `AgentEvent` / `InteractionRequest` 等通用契约
- 新增 API 调用 → 对应 `lib/api/<domain>.ts` 文件
- 新增页面 → `pages/` + `sections/` 配合

---

## 四、Business 资源归属规则

### 4.1 新增 task_type（必须先改 templates.yaml）

```
1. business/templates/templates.yaml → 定义 task_type（sections/format/acceptance）
2. business/templates/business-roster.json → 给角色分配该 task_type
3. business/skills/<skill_id>/SKILL.md → 编写执行方法论（可选但推荐）
```

**禁止**：只写 Skill 不改 templates.yaml，Process 不会识别未注册的 task_type。

### 4.2 新增 Skill

- 目录：`business/skills/<skill_id>/SKILL.md`
- skill_id 命名：`^[a-z0-9][a-z0-9-]{0,63}$`，禁止 `auto-` 前缀（保留给草案提取）
- 禁止用保留名：`categories`、`catalog`
- 通过 Hub UI 创建或手动创建，均需在 `catalog.yaml` 注册

### 4.3 新增 Workflow

- 目录：`business/workflows/<workflow_id>.yaml`
- YAML 必须通过 `validate_workflow_payload` 校验
- `marker` 值含冒号时**必须加引号**（如 `marker: "REVIEW: PASS"`）

### 4.4 新增 Agent 角色

- 模板：`business/templates/business-roster.json`（权威角色定义）
- 运行态：`business/config/agents_config.json`（backend/model/name）、`business/config/agents_registry.json`（role/task_types/skills）
- 身份文件：`business/workspaces/workspace-<agent_id>/` 下的 IDENTITY/SOUL/AGENTS/MEMORY.md（用 `scripts/bootstrap_agent_identity.py` 生成）

---

## 五、脚本和工具归属

| 路径 | 放什么 |
|------|--------|
| `scripts/` | 一次性脚本、bootstrap、运维工具 |
| `scripts/regression/` | 回归测试脚本 |
| `backend/execution_harness/single_execute.py` | 单 Agent 执行器（可直接运行） |
| `backend/common/runtime/run_kernel.py` | 内核运行入口（可直接运行） |

**规则**：可执行脚本放 `scripts/`，库代码放 `backend/`，不混放。

---

## 六、Git 提交规范

### 6.1 提交信息（中文 conventional-commit）

```
<type>(<scope>): <subject>

<body 可选>
```

- type：`feat` / `fix` / `refactor` / `polish` / `docs` / `chore` / `test`
- scope：`ux` / `reliability` / `css` / `architecture` / `kernel` / `hub` / `skill` 等
- subject：简洁中文描述

### 6.2 禁止提交（gitignore 已覆盖）

- `config/*.json` — 系统配置（运行态）
- `business/config/` — 业务配置（运行态）
- `business/workspaces/` — Agent workspace（运行态）
- `business/tasks/` — 任务数据（运行态）
- `venv/` — Python 虚拟环境
- `node_modules/` — Node 依赖
- `*.db` / `*.log` — 数据库和日志
- `.env` / 凭证文件

### 6.3 提交前检查

- `PYTHONPATH=backend venv/bin/python3 -m pytest backend -q` 全绿
- `cd frontend && npm run build` 编译通过
- `git status` 确认无敏感文件
- 不用 `git add -A`，按文件名添加

---

## 七、不变量速查（违反即 bug）

1. **Adapter 隔离**：`parser.py` 是唯一知道 CLI 格式的地方
2. **交互契约**：`InteractionRequest`/`InteractionResponse` 是唯一跨框架- agent 数据契约
3. **Gate 同源**：Gate 校验用 `registry.get_spec(task_type)`，与下发给 agent 的 spec 同源
4. **submit_result 原子性**：本地校验通过才写 `.response`，无 rescue/repair 路径
5. **task_type 注册优先**：先改 `templates.yaml`，再写 Skill
6. **框架冻结**：新能力去 `business/workflows/` 和 `business/skills/`，不重构内核
7. **中文优先**：注释、docstring、提交信息用中文；代码标识符用英文
