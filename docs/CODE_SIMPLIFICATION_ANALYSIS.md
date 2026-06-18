# myteam 代码精简分析

> **版本**：2026-06-18  
> **方法**：全库 grep 依赖分析、文件级 import 追踪、CodeGraph 索引交叉验证、逐模块职责评估  
> **范围**：`/Users/kuanghualong/Project/Cursor/myteam`

---

## 执行摘要

myteam 后端生产代码 **28,253 行 / 155 个文件**。按当前主功能估算，合理体积约 **22,000 行**。

| 类别 | 规模 | 说明 |
|------|:----:|------|
| 可安全删除的死代码 | ~1,200 行 | 6 个文件 + `quality_gate` 主体 |
| 可大幅精简的膨胀代码 | ~5,000 行 | skill/workflow/loop 系统过度拆分 |
| 可清理的遗留物 | ~8,500 行 | frontend v1 + orphan API + regression 快照 |

**总计可减少：~14,700 行生产代码 + ~95,000 行 regression 磁盘数据。**

> 判断标准：**无人 import = 死代码**；**< 2 import + > 200 行 = 需精简**。每个判断均附验证方法，可复现。

---

## 1. myteam 功能与框架

### 1.1 两条正交流

```
A) Hub 交互流（人 ↔ Agent / 群）
   浏览器 frontend-v2 (/v2)
     → FastAPI backend/hub/api/server.py
     → hub/services/chat_service（或 groups / notify）
     → base/agent_chat + adapter/registry
     → adapters/opencode | adapters/claude（子进程 CLI）
     → 统一 AgentEvent → SSE 推前端

B) 编排内核流（目标 → 多 Agent 自动交付）
   run_kernel.py 或 Hub「运行项目」
     → common/process.py（状态机）
     → common/agent_port.py（Interaction 投递 + submit_result 收卷）
     → common/gate.py（确定性验收）
     → SQLite business/tasks/state.db（真相）
     → 交付物 business/tasks/project/<id>/deliverables/
```

两条流 **共用** Agent 名册、Skill/MCP 挂载、workspace、SQLite；**编排不依赖 Hub 进程**（Hub 只读同一库做可观测）。

### 1.2 三层职责

| 层 | 路径 | 职责 |
|----|------|------|
| **System Kernel** | `backend/common/`、`backend/adapter/`、`backend/hub/` | Process、AgentPort、Gate、Store、contracts、Hub API、CLI 适配 |
| **Strategy Registry** | `business/templates/`、`business/config/agents_registry.json`、`business/workflows/`、`business/rules/` | task_type、prompt 壳、workflow、名册、验收规则 |
| **Skill / MCP Pack** | `business/skills/*/SKILL.md`、`business/config/mcp_registry.json` | 具体执行方法论；MCP 工具目录 |

**决策规则**：需要持久化、重试、审计 → Kernel；改 task_type / 角色 / 验收 → Registry；单次执行质量 → Skill。

### 1.3 前端 v2 实际使用的 API（= 产品边界）

| 功能页 | API 域 | 后端入口 |
|--------|--------|----------|
| Dashboard | `/api/obs/summary`, agents, groups, projects, workflows | `observability_api`, `routes/*` |
| 私聊 | `/api/chat/*`, `/api/agents/*/events` | `chat.py`, `chat_service` |
| 群聊/圆桌 | `/api/groups/*` | `groups.py`, `group_manager` |
| Agent 管理 | `/api/agents/*`, `/api/rules/shared/*` | `agents.py`, `rules_api` |
| 项目 | `/api/projects/*`, `/api/obs/projects/*` | `projects.py`, `observability_api` |
| Workflow/TaskType/Skill | `/api/workflows/*`, `/api/task-types/*`, `/api/skills/*`, `/api/delivery-templates/*` | `workflows.py`, `skills_api` |
| MCP | `/api/mcp/*` | `mcp_api` |
| 设置 | `/api/config`, `/api/backends` | `config.py` |

**frontend-v2 零引用**：

- `/api/workspace/channels/*`
- `/api/jobs/*`
- `/api/workspace/events*`

可观测已统一走 `/api/obs/*`。

---

## 2. CodeGraph 验证

| 项 | 状态 |
|----|------|
| `.codegraph/codegraph.db` | 存在（~16MB，2026-06-18 索引） |
| `errors.log` | 8 个 stale 路径（已删 skill 仍被索引引用） |
| 本地 CLI | `codegraph query` / `codegraph explore` 可用 |

**建议复核命令**：

```bash
cd myteam
codegraph status
codegraph query "run_quality_gate"
codegraph query "ProjectionRunner"
codegraph explore "who calls loop_runtime"
codegraph explore "imports workspace_events"
```

**grep 与 CodeGraph 预期一致的关键结论**：

- `QualityGate` / `run_quality_gate` → 仅 test + 自身定义；生产 Gate 走 `gate.py`
- `ProjectionRunner` / `EventPipeline.dispatch` → 仅 test；生产从未启动 Runner
- `project_group_discussion` → 仅 test；生产走 `loop_discussion_dispatch` → business hook

---

## 3. 死代码（可安全删除）

### 3.1 完全无人 import 的文件（798 行）

| 文件 | 行数 | 删除依据 |
|------|:----:|----------|
| `backend/common/config.py` | 88 | 全库 0 个 import（legacy `skill/team/.env`） |
| `backend/common/logger.py` | 196 | 全库 0 个 import |
| `backend/common/event_handler.py` | 85 | 仅 `test_r2_features.py` |
| `backend/common/workspace_events.py` | 246 | 仅 test；`ProjectionRunner` 生产未实例化 |
| `backend/common/project_group_discussion.py` | 57 | 仅 test；shim，实现已在 `loop_discussion_*` |
| `backend/common/recurring_trigger.py` | 126 | 仅 test + regression 脚本引用 test |

验证命令：

```bash
grep -rn "from common.<name> import\|import common.<name>" backend/ --include="*.py"
```

### 3.2 主体代码已死，仅个别函数活着（341 行）

**`backend/common/quality_gate.py`（341 行）**

活的（4 个符号被 `gate.py` import）：

- `EVIDENCE_VERIFY_OFF`（常量）
- `_URL_RE`（正则）
- `_extract_field()`（工具函数）
- `verify_published_url()`（工具函数）

死的（零外部调用）：

- `QualityGate` 类 — 0 次调用
- `run_quality_gate()` — 0 次调用
- `GateResult` 类 — `gate.py` 有自己的同名类
- `_resolve_browse_bin()` — 0 次调用

**建议**：把 4 个活符号迁入 `gate.py`，删除 `quality_gate.py`。

### 3.3 inject_catalog 字段（死配置）

`delivery_profiles.yaml` 定义了 `inject_catalog: true/false`，`delivery_profiles.py` 的 `Profile` 类解析了它。但**全库没有任何代码读取这个字段**。

**建议**：从 YAML 和 `Profile` 类中删除。

### 3.4 templates.yaml 空壳

`business/templates/templates.yaml` 内容为 `{}`，FormatSpec 注册表未启用。

### 3.5 对 v2 报告的修正

**`agent_memory.py` 的 `before_turn`/`after_turn` 不是死代码** — `chat_service.py` 在 DM 流中调用。瘦身时只删未用 Provider 实现，不要删这两个方法。

---

## 4. 历史遗留

### 4.1 `frontend/` v1 — 19 个文件 / ~8,349 行

纯 JavaScript + HTML + CSS，通过 `MYTEAM_V1_UI=1` 环境变量启用。`backend/hub/api/server.py` 中的 `classic_v1_ui()` 路由指向它。

frontend-v2（~7,300 行 TS/TSX）已是完整替代品，v1 无存在理由。

**建议**：删除 `frontend/` 和 `classic_v1_ui()` 路由。

### 4.2 Orphan HTTP API — 3 个路由文件 / ~170 行

| 路由 | 文件 | 前端引用 |
|------|------|:--------:|
| `/api/workspace/channels/*` | `routes/channels.py` | frontend-v2 零引用 |
| `/api/jobs/*` | `routes/jobs.py` | frontend-v2 零引用 |
| `/api/workspace/events*` | `routes/workspace_events.py` | 可观测已走 `/api/obs/*` |

**注意**：`JobSupervisor` **要保留** — `project_runtime.py` 和 `server.py` 启动 orphan 扫描在用。删的是 HTTP 暴露的 `/api/jobs`，不是 supervisor 本身。

**建议**：删除这 3 个文件，从 `routes/__init__.py` 中去掉注册。

### 4.3 R2 事件基础设施（~331 行）

`event_handler.py` + `workspace_events.py` 与 orphan `/api/workspace/events` 是一套未接线的方案。`ProjectionRunner` 从未在生产 `lifespan` 中启动。

### 4.4 regression 数据出 git 跟踪

`business/regression/` 下有 131 个文件，部分已被 git 跟踪。`.gitignore` 已阻止新增，但旧文件仍在仓库历史里。

`scripts/regression/` 下有 36 个测试驱动脚本（活的，不能删）。

**建议**：`git rm --cached` 将被跟踪的 regression 数据文件从索引中移除。

---

## 5. 膨胀模块（过大，需精简）

### 5.1 Skill 系统：12 个文件 / ~2,136 行

```
skill_catalog.py       531   ← 管理 catalog.yaml 的读写
skill_categories.py    293   ← UI 分类
skill_link.py          268   ← 挂载 + vendor 软链 + CLI 同步
agent_skills.py        208   ← 注入 skill 到 prompt
mcp_catalog.py         214   ← MCP 目录（和 skill_catalog 模式重复）
skill_settings.py      139   ← 配置读写
skill_groups.py        150   ← 组展开
skill_extract.py       102   ← 提取
skill_display_names.py  61   ← 常量映射
adapter_skill_registry.py 110 ← 适配器注册
adapter_mcp_registry.py    60 ← MCP 注册
```

Skill 系统本质做三件事：

1. 注册/查询 catalog（1 个文件）
2. 挂载/同步（1 个文件）
3. 注入 prompt（1 个文件）

3 个文件足够。剩下 9 个主要因为 catalog 和 MCP 各自独立了一套 registry、skill_groups、提取逻辑，结构互相复制。

**建议**：合并到 3 个文件（~600 行），砍掉 ~1,500 行重复架子。

`catalog.yaml`：27 个 entry 里 14 个指向同一个 `product-methodology/SKILL.md`，仅 `/api/skills/matrix` 审计用。运行时边界是 `agents_registry.json` 的 `skills[]`。

### 5.2 Workflow 系统：6 个文件 / ~1,400 行

```
workflow_loader.py     300    ← 载入 workflow YAML
workflow_bootstrap.py  231    ← 创建项目时预填 task
workflow_suggest.py    431    ← 推荐 workflow
workflow_validate.py   196    ← 校验 DAG
workflow_collaboration.py 129 ← 协作
workflow_capability_bind.py 113 ← 能力绑定
```

**`workflow_suggest.py`（431 行）特别膨胀**：主体是 8 个 `_*_tasks()` 工厂函数，每个返回硬编码 Python 任务列表（~40 行/个）。这些任务模板应该存在 YAML 配置里，而不是 Python 代码里。

验证命令：

```bash
grep -n "^def _" backend/common/workflow_suggest.py
```

**建议**：把任务模板移到 `business/templates/workflow_suggestions.yaml`，`workflow_suggest.py` 精简到 ~30 行（只做匹配逻辑）。

### 5.3 Loop 系统：3 个文件 / ~1,583 行

```
loop_runtime.py              1,167  ← 整个代码库最长的文件之一
loop_discussion_runtime.py     273
loop_discussion_dispatch.py    143
```

**`loop_runtime.py`（1,167 行）比核心状态机 `process.py`（670 行）还多 500 行。** loop 只是「重复执行一批任务直到条件满足」的辅助机制，不应该比 DAG 状态机复杂。

问题在 4 个 parse 函数（~60 行）+ 一堆 resolve/seed 辅助函数堆积。核心逻辑（执行 loop、判断跳转）大概 300 行，剩下是做数据结构转换的辅助代码。

**建议**：精简到 ~400 行，把辅助函数内联或合并。

### 5.4 `group_manager.py` — 2,529 行

| 功能 | 大致行数 |
|------|:--------:|
| 群组 CRUD（创建、删除、解散、恢复） | ~400 |
| 成员管理（添加、删除、排序） | ~150 |
| 圆桌调度（创建轮次、设置、查询） | ~800 |
| 消息管理（清除、预处理、提及解析） | ~300 |
| 搜索 / 列表 / 配置 | ~400 |
| 工具函数 | ~400 |

这是 **4 个不同职责写在 1 个文件里**。`process.py`（670 行）只做一件事（DAG 调度），`group_manager.py`（2,529 行）做四件事。

**建议**：拆成 `group_crud.py`（CRUD）+ `group_roundtable.py`（圆桌）+ `group_messages.py`（消息），每文件 ~800 行。

### 5.5 `server.py` — 992 行

`backend/hub/api/server.py` 是 FastAPI 入口。路由注册 + SSE + 模板渲染混在同一个文件。

**建议**：按职责拆成 `server.py`（启动 + 中间件）+ 剩余路由下沉 `routes/`。

### 5.6 双 Agent Registry（有意重复，可收敛文档）

| 模块 | 职责 |
|------|------|
| `common/agent_registry.py` (~106 行) | 内核只读：task_type map、prompt 上下文 |
| `hub/services/agent_registry.py` (~461 行) | Hub CRUD：skills/mcp/task_types 写回 JSON |

读同一 `agents_registry.json`，**不是死代码**。`list_available_agent_ids()` 等函数字面重复，长期可抽 `registry_io.py`。

### 5.7 task_type 建议双模块

- `task_type_suggest.py` — 从描述推导 task_type（Workflow 页）
- `agent_task_type_suggest.py` — 从 Agent 职责推导 task_types

职责不同，保留；可共享 `_norm()` / rules 加载减少重复。

---

## 6. 功能重复

### 6.1 三个「Skill 路由」系统

| 系统 | 路径 | 有没有 UI 管理 |
|------|------|:--------------:|
| `agents_registry.json` → `skills[]` | 运行时决定 agent 能用哪些 skill | ✅ 有 |
| `catalog.yaml` | task_type → router path | ❌ 无 UI，手改 |
| `prompt_templates.yaml` | 每 task_type 硬编码 prompt | ✅ 有 |

`agents_registry.json` 是唯一运行时生效的边界。`catalog.yaml` 的作用是供 `/api/skills/matrix` 审计用。

**建议**：删除 `catalog.yaml`。审计功能改为直接扫 `business/skills/` 目录。

### 6.2 task_type 注册表拆在 4 个文件里

| 文件 | 行数 | 内容 |
|------|:----:|------|
| `templates.yaml` | 1（`{}`） | FormatSpec、delivery_profile（**空的**） |
| `prompt_templates.yaml` | ~180 | 每种 task_type 的 execute/review prompt |
| `delivery_profiles.yaml` | ~45 | 过程产物规范（light_v1/all_v1） |
| `prompt_injections.yaml` | ~42 | profile 级 prompt 块 |

同一个 task_type（比如 `research`）的信息散在 3 个地方。

**建议**：P3 合并成 `task_types.yaml`，每个 task_type 一条完整条目包含 prompt + 格式 + 验收标准。

### 6.3 adapter/ 与 adapters/ 命名撞车

```
backend/adapter/      ← 协议定义 + registry（~318 行）
backend/adapters/     ← 具体实现（opencode/claude/stub）（~1,160 行）
```

功能上没有重复，但命名容易混淆。

**建议**：改成 `backend/adapter-core/` 或直接在文档里注明区别。

---

## 7. 精简前后对比

| 指标 | 当前 | 精简后 |
|------|:----:|:------:|
| 后端生产代码 | 28,253 行 / 155 文件 | ~20,000 行 / ~90 文件 |
| 后端测试 | 13,439 行 | 基本不变 |
| frontend-v2 | ~7,300 行 | 不变 |
| frontend v1 | ~8,349 行 | **0 行**（删） |
| 死代码 | ~1,200 行 | **0 行** |
| orphan API | ~170 行 | **0 行** |
| regression 快照（git tracked） | ~95k | **0 文件**（git rm --cached） |
| Skill 管理文件 | 12 文件 / 2,136 行 | ~3 文件 / ~600 行 |
| Workflow 管理文件 | 6 文件 / 1,400 行 | ~3 文件 / ~500 行 |
| `group_manager.py` | 2,529 行 | 拆 3 文件 / 各 ~800 行 |
| `loop_runtime.py` | 1,167 行 | ~400 行 |
| `server.py` | 992 行 | ~500 行（拆后） |
| task_type 配置文件 | 4 个 | 1 个（P3） |

---

## 8. 精简顺序（风险从低到高）

### Phase 1：删死代码（安全，无影响）

顺序：

1. 把 `quality_gate.py` 的 4 个活符号迁入 `gate.py`，删 `quality_gate.py`
2. 删 `config.py`、`logger.py`、`event_handler.py`、`workspace_events.py`、`project_group_discussion.py`、`recurring_trigger.py`
3. 从 `delivery_profiles.yaml` 和 `Profile` 类中删 `inject_catalog` 字段
4. 改 test 指向 `loop_discussion_*`（替代 `project_group_discussion` shim）

验证：

```bash
grep -rn "from common.<name>" backend/
pytest backend/common/tests/
```

### Phase 2：删遗留物（低风险）

顺序：

1. 删 `frontend/` 目录 + `classic_v1_ui` 路由
2. 删 3 个 orphan API 路由文件
3. `git rm --cached` regression 快照
4. `codegraph sync` 清 stale 索引

### Phase 3：精简膨胀模块（中等风险）

顺序：

1. 将 `workflow_suggest.py` 的 8 个硬编码任务模板迁入 YAML 配置
2. 合并 `skill_*.py` 到 3 个文件
3. 精简 `loop_runtime.py` 到 ~400 行
4. 拆分 `group_manager.py`
5. 拆分 `server.py`

### Phase 4：合并注册表（低影响，长期）

顺序：

1. 填充 `templates.yaml`（或废弃 FormatSpec 注册表）
2. 合并 templates + prompt_templates + delivery_profiles + prompt_injections → `task_types.yaml`
3. 删 `catalog.yaml`（审计功能改为扫目录）

---

## 9. 必须保留的模块

| 模块 | 文件 | 原因 |
|------|------|------|
| 编排主干 | `process.py`, `agent_port.py`, `gate.py`, `store.py` | DAG 状态机 + 交卷 + Gate |
| Loop/群讨论 | `loop_runtime.py`, `loop_discussion_*` | workflow loop + 项目群对齐 |
| 项目 Hook | `kernel_project_hooks.py`, `workflow_collaboration.py` | 建群 + loop 讨论 |
| 后台调度 | `JobSupervisor`, `project_runtime.py` | kernel 并发槽 + orphan 扫描 |
| CLI 适配 | `adapters/opencode`, `adapters/claude` | 生产执行面 |
| Skill/MCP 链 | `skill_link.py`, `agent_skills.py`, `adapter_*_registry` | 挂载 + prompt 注入 |
| 记忆 | `agent_memory.py`（含 before/after_turn） | DM 记忆注入 |
| 群圆桌 | `roundtable_runtime.py`, `deliverable_guarantee.py` | 群聊 + 交卷保障 |
| 经验 | `experience.py` | `task_pipeline` / `agent_transport` 引用 |

---

## 10. 验证命令速查

```bash
# 死代码 import 检查
grep -rn "from common.quality_gate\|from common.config\|from common.logger" backend/ --include="*.py"

# orphan API 前端引用
grep -rn "channels\|/api/jobs\|workspace/events" frontend-v2/src/

# Skill catalog 审计
grep -rn "catalog.yaml" backend/ business/

# 最大文件
wc -l backend/base/group_manager.py backend/common/loop_runtime.py backend/hub/api/server.py

# 全库 pytest
pytest backend/common/tests/ -q
```
