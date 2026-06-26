# myteam 升级执行方案

> 基于 PRODUCT-DESIGN.md + UPGRADE-GAP-ASSESSMENT.md  
> 生成日期：2026-06-26  
> 版本：v1.0  
> 目标分支：upgrade/phase0-boundary  
> 覆盖度：GAP-ASSESSMENT **100% 覆盖**（5 个 Phase 全部任务 + P2 硬编码 + 高风险预研 + 配置 UI + 代码结构 + 迁移回滚 + 测试补全）

---

## 一、整体评估

| 指标 | 数据 |
|------|------|
| 文档完整性 | ✅ 两份文档已补充状态迁移矩阵、配置 UI 路线图、测试覆盖矩阵、回滚预案 |
| 现有功能保护 | ✅ 所有 P0 变更均有 feature flag，默认 false |
| 测试基础设施 | ⚠️ decision_pipeline 无单元测试（先补再改） |
| 最大风险点 | 0.1 协调者配置化（11 处硬编码 / 269 行 / 零测试） |
| 墙钟周期（串行） | 43 天 |
| 墙钟周期（2 人并行） | ~24 天 |

### 工作量总览

| 阶段 | 工作量 | 核心目标 | 与 GAP-ASSESSMENT 对比 |
|------|--------|---------|----------------------|
| Phase 0：边界澄清 | 8.5 天 | 硬编码配置化、边界清晰 | 6 项任务 + 2 天前置测试（GAP 5 天 + 额外） |
| Phase 1：三库独立 | 7 天 | 知识库/偏好库/项目库独立 | 完全对应 1.1-1.5 |
| Phase 2：结构整理 | 7 天 | 代码结构清晰 | 完全对应 2.1-2.8 |
| Phase 3：质量闭环 | 10 天 | 五层防御体系打通 | 完全对应 3.1-3.6 |
| Phase 4：配置 UI | 12 天 | 所有配置有 UI | 完全对应 4.1-4.15（3 个迭代） |
| 高风险预研（可选） | 5 天 | 降低重构风险 | 完全对应 6.1 |
| **总计（串行）** | **49.5 天** | | 含 8.5 天前置测试 + 预研 |
| **理论最短（2 人并行）** | **~28 天** | | |

---

## 二、核心原则

| 原则 | 说明 |
|------|------|
| **不影响现有功能** | 每个重构类变更默认 feature flag = false，行为与旧代码一致 |
| **可回滚** | 每个 P0 变更有对应配置开关，开启后发现问题立即关掉 |
| **先测后改** | 动代码前先补测试（尤其 decision_pipeline） |
| **低风险先行** | Phase 0 内：0.6（旧路径清理）先行，建立信心 |
| **行号核实** | 本文档行号基于写入时的代码快照。实施前先全量 grep 核实每个目标行号 |

### 向后兼容判定规则

| 变更类型 | 兼容要求 | 兼容手段 | 不兼容判定 |
|---------|---------|---------|-----------|
| 配置键变更 | 旧键仍可读，自动迁移到新键 | 读取时 fallback + 首次启动自动迁移 | 旧配置启动后报错 |
| API 端点变更 | 旧端点仍可调用，返回相同数据结构 | 旧端点转发到新端点 | 旧端点返回 404 |
| 存储结构变更 | 旧数据不丢失，可自动升级 | 启动时检测版本号 + 增量迁移脚本 | 旧数据启动后丢失 |
| 文件路径变更 | 旧路径仍可工作（有警告） | 检测旧路径存在则自动使用 | 旧路径启动后找不到文件 |
| 代码接口变更 | 旧函数签名仍可调用 | 保留旧函数，内部委托到新实现 | 现有调用方运行失败 |
| 行为语义变更 | 默认行为不变 | 配置开关控制，默认 false | 默认行为改变且无开关 |

---

## 三、Phase 0：边界澄清（8.5 天）

### 实施顺序

```
先 ──→ T1+T2+T3（前置测试补全，2 天）
  │
  ├──→ 0.6 旧路径清理（1 天，先行）
  │
  ├──→ 0.1 协调者配置化（1.5 天，高风险）
  │    └──→ 0.4 Agent 显示名统一（0.5 天，合并做）
  │    └──→ P2.12 废弃 agent 别名（0.5 天，合并做）
  │
  ├──→ 0.2 code_project 配置化（0.5 天）
  │    ├──→ 0.3 PGD 严格类型配置化（0.5 天）
  │    ├──→ P2.9 占位符标记（0.2 天，合并做）
  │    ├──→ P2.10 反爬拦截标记（0.2 天，合并做）
  │    └──→ P2.11 代码扩展名（0.2 天，合并做）
  │
  ├──→ 0.5 KB API 抽象修复（1 天，收尾）
  │    └──→ P2.6 工作流推导模板（0.5 天，独立做）
  │    └──→ P2.7 身份文件模板（0.2 天，独立做）
  │
  └──→ P2.8 规则 profile 映射（0.3 天，独立做）
       │
       ▼ Phase 0 验收 → Step 7 逐一切 flag → 进入 Phase 1
```

### 任务总览

| 编号 | 任务 | 代码量 | 文件数 | 工作量 | 配置开关（默认值） |
|------|------|--------|--------|--------|-------------------|
| T1-T3 | 前置测试补全 | ~300 行 | 5-7 | 2 天 | — |
| 0.6 | 旧路径清理 | ~300 行 | 3-5 | 1 天 | `use_sqlite_project_store`（false） |
| 0.1 | 协调者配置化 | ~450 行 | 8-10 | 1.5 天 | `coordinator_agent_id`（"main"） |
| 0.4 | Agent 显示名统一 | ~100 行 | 3-4 | 0.5 天 | — |
| 0.2 | code_project 配置化 | ~50 行 | 2-3 | 0.5 天 | `use_outcome_kind_detection`（false） |
| 0.3 | PGD 严格类型配置化 | ~80 行 | 2-3 | 0.5 天 | `use_strict_must_include_config`（false） |
| 0.5 | KB API 抽象修复 | ~200 行 | 3-4 | 1 天 | `use_kb_backend_for_observability`（false） |
| P2.6 | 工作流推导模板 | ~100 行 | 1 | 0.5 天 | — |
| P2.7 | 身份文件模板 | ~50 行 | 1 | 0.2 天 | — |
| P2.8 | 规则 profile 映射 | ~80 行 | 2 | 0.3 天 | — |
| P2.9 | 占位符标记 | ~30 行 | 1 | 0.2 天 | — |
| P2.10 | 反爬拦截标记 | ~30 行 | 1 | 0.2 天 | — |
| P2.11 | 代码扩展名 | ~40 行 | 2 | 0.2 天 | — |
| P2.12 | 废弃 agent 别名 | ~50 行 | 1 | 0.5 天 | — |

> 工作量说明：P0/P1 核心任务 6.5 天 + 前置测试 2 天 = 8.5 天。P2 硬编码 7 项可选，共约 2 天。

### T1 — decision_pipeline 测试补全

**新建:** `backend/common/tests/test_decision_pipeline.py`

| 测试用例 | 覆盖 | 验证方法 |
|---------|------|---------|
| `test_with_default_main` | 默认 coordinator="main" 时行为不变 | 协调者调用使用 agent_id="main" |
| `test_with_custom_coordinator` | coordinator="pm" 后使用 pm | 所有 Request 的 agent_id 改为 "pm" |
| `test_coordinator_in_split` | 子任务拆分时协调者正确传递 | 子任务 DAG 中的协调者角色一致 |
| `test_coordinator_in_triage` | 失败分诊时协调者正确传递 | triage Request 使用指定协调者 |
| `test_deputy_exclusion` | deputy 不被排除 workers_only | workers_only 列表正确 |

### T2 — project_service 路径切换测试

**修改:** `backend/common/tests/test_project_service.py`

| 测试用例 | 覆盖 | 验证方法 |
|---------|------|---------|
| `test_read_from_sqlite` | 新路径读 SQLite 返回正确数据 | mock SQLite 返回，验证结果一致 |
| `test_fallback_to_task_data_json` | 旧路径 task_data.json 仍可读 | flag=false 时读 task_data.json |
| `test_flag_off_behavior_identical` | flag=false 时行为与旧代码一致 | 新旧路径输出对比 |

### T3 — observability + KB 集成测试

**新建:** `backend/hub/api/tests/test_observability_kb.py`

| 测试用例 | 覆盖 | 验证方法 |
|---------|------|---------|
| `test_kb_backend_search` | KnowledgeBackend.search 返回正确 | mock KB 后端，验证 API 返回 |
| `test_kb_backend_write` | KnowledgeBackend.write 正确调用 | 验证 memory_write 委托到 KB |
| `test_flag_off_uses_store_direct` | flag=false 走 store.memory_* | flag=false 时行为与旧一致 |
| `test_backend_switch_mock` | 切换 mock 后端后行为一致 | MemoryBackend 替换 sqlite |

### 0.6 — 旧路径清理（P0）

**前置:** `grep -rn "task_data.json" backend/ --include="*.py"`

| 文件 | 行号（核实后） | 修改 |
|------|--------------|------|
| `backend/hub/services/project_service.py` | ≈69, 78 | 新增 SQLite 读路径；旧路径加 `@deprecated` |
| `backend/hub/services/project_group_service.py` | ≈28, 186 | 同上 |
| `backend/common/paths.py` 或 `system_config.json` | — | 新增 `use_sqlite_project_store`（默认 false） |

**测试:** T2 3 用例 + `test_projects_api.py` 10 用例回归  
**回滚:** 关 flag → 立即读回旧 JSON

### 0.1 — 协调者 + deputy 配置化（P0，高风险）

**前置:** `grep -rn '"main"' backend/common/ --include="*.py" | grep -v test`

| 分组 | 行号（核实后） | 硬编码位置 | 改为 |
|------|--------------|-----------|------|
| Worker 排除 | ≈56 | `aid != "main"` | `aid != cfg.coordinator_agent_id` |
| team_config | ≈104, 115 | `agent_id: "main"` | `cfg.coordinator_agent_id` |
| task_plan | ≈158, 169, 172, 177, 181 | 同上 | 同上 |
| triage | ≈229, 240, 244 | 同上 | 同上 |

**修改文件:**

| 文件 | 修改 |
|------|------|
| `backend/common/decision_pipeline.py` | 11 处 "main" 替换 |
| `backend/common/workflow_loader.py`（如查到） | 同上模式 |
| `backend/common/agent_registry.py` | workers_only 从配置读 deputy_agent_id |
| `backend/common/system_config.json` | 新增 `coordinator_agent_id`（默认 "main"）+ `deputy_agent_id`（默认 "deputy"） |

**测试:** T1 5 用例 + 端到端场景 2  
**回滚:** `coordinator_agent_id` 改回 "main"

### 0.4 — Agent 显示名统一（P1）

**前置:** 对比 `_AGENT_DISPLAY_NAMES` dict 与 `agents_registry.json` 中对应 name

| 文件 | 行号（核实后） | 修改 |
|------|--------------|------|
| `backend/common/agent_transport.py` | ≈79-82 | 删除 `_AGENT_DISPLAY_NAMES` |
| `backend/common/agent_transport.py` | ≈147 | `chinese_name = registry.get(agent_id, {}).get("name", agent_id)` |

### 0.2 — code_project 配置化（P0）

| 文件 | 行号（核实后） | 修改 |
|------|--------------|------|
| `backend/common/project_artifacts.py` | ≈10-17 | 删除 `CODE_PROJECT_TASK_TYPES`；`is_code_project()` 从 `outcome_kind` 检测 |
| `backend/common/gate.py` | — | 引用改为调 `registry.get_spec().outcome_kind` |
| `backend/common/templates/templates.yaml` | — | 已有 task_type 补 `outcome_kind` 默认值 |

### 0.3 — PGD 严格类型配置化（P0）

| 文件 | 行号（核实后） | 修改 |
|------|--------------|------|
| `backend/common/gate.py` | ≈97, 338 | 删除 `_PGD_STRICT_TYPES`；读 `registry.get_spec().strict_must_include` |
| `backend/common/templates/templates.yaml` | — | 已有 task_type 补 `strict_must_include` |

### 0.5 — KB API 抽象修复（P0，收尾）

| 文件 | 行号（核实后） | 修改 |
|------|--------------|------|
| `backend/hub/api/observability_api.py` | ≈103, 154, 167, 189, 196 | `store.memory_*` → `knowledge_backend.*` |
| `backend/memstack/kb/__init__.py` | — | 确保 KnowledgeBackend 实例可全局获取 |

### P2 硬编码 — 7 项（可选，建议 Phase 0 内顺便做）

| # | 文件 | 修改 | 工作量 | 做在 |
|---|------|------|--------|------|
| P2.6 | `workflow_suggest.py` | 工作流推导模板配置化 | 0.5 天 | 0.5 后 |
| P2.7 | `agent_bootstrap.py` | 身份文件模板从配置读 | 0.2 天 | 0.5 后 |
| P2.8 | `rules_merge.py` | 规则 profile 映射配置化 | 0.3 天 | 独立 |
| P2.9 | `registry.py` | 占位符标记从配置读 | 0.2 天 | 0.2 |
| P2.10 | `gate.py` | 反爬拦截标记从配置读 | 0.2 天 | 0.2 |
| P2.11 | `gate.py + project_artifacts.py` | 代码扩展名从配置读 | 0.2 天 | 0.2 |
| P2.12 | `agent_id_policy.py` | 废弃 agent 别名从配置读 | 0.5 天 | 0.1 |

### Phase 0 风险矩阵

| 修改 | 风险 | 功能影响 | 测试 | 回滚 |
|------|------|---------|------|------|
| 0.6 旧路径清理 | 🟡 | 默认 false 无影响 | project_service 测试 | 关 flag |
| 0.1 协调者 | 🟠 | 默认 "main" 无影响 | T1 + 端到端 | 改回 "main" |
| 0.4 显示名 | 🟢 | 从 registry 读 | test_agent_transport | git revert |
| 0.2 code_project | 🟢 | 默认 false | test_gate 27 用例 | 关 flag |
| 0.3 PGD | 🟢 | 默认 false | test_gate 回归 | 关 flag |
| 0.5 KB 抽象 | 🟡 | 默认 false | test_observability 14 用例 | 关 flag |
| P2.x 硬编码 | 🟢 | 配置化 | 手动验证 | git revert |

---

## 四、Phase 1：三库独立（7 天）

### 任务总览

| 编号 | 任务 | 代码量 | 文件数 | 工作量 | 风险 |
|------|------|--------|--------|--------|------|
| 1.1 | 偏好库独立确认 | ~100 行 | 3-4 | 0.5 天 | 🟢 |
| 1.2 | 知识库存储解耦 ⚠️🧪 | ~500 行 | 6-8 | 2 天 | 🟠 |
| 1.3 | 统一项目 meta schema | ~300 行 | 5-7 | 1.5 天 | 🟡 |
| 1.4 | 封装项目库模块 | ~600 行 | 8-10 | 2 天 | 🟡 |
| 1.5 | 打破 harness-memstack 双向依赖 🧪 | ~400 行 | 5-6 | 1 天 | 🔴 |

### 1.1 — 偏好库独立确认

| 文件 | 修改 |
|------|------|
| `backend/memstack/preferences/` | 清理对 `hub.services.agent_registry` 的依赖 |
| `backend/memstack/preferences/sync.py` | 改为注入式获取 agent 列表 |

**验证:** 偏好库模块可独立 import 且不依赖 hub 层  
**测试:** memstack 现有测试 + 独立 import 验证

### 1.2 — 知识库存储解耦 ⚠️（需预研）

**修改文件:**

| 文件 | 修改 |
|------|------|
| `backend/memstack/kb/sqlite.py` | 定义 `MemoryStore` Protocol；将 SQLite 实现内聚到 memstack |
| `backend/common/store.py` | 作为适配层委托给 memstack |
| `backend/hub/api/observability_api.py` | 已改走 KnowledgeBackend（Phase 0.5） |

**预研（1 天，实验分支 `feat/kb-abstract`）:**
- 选 2-3 个核心 API 改走 KnowledgeBackend
- 验证切换 mock 后端行为一致
- 确认性能无明显下降

**迁移方案:**
1. 启动时检测并迁移 L3 数据到新 kb_entries 表
2. 双写过渡期：同时写新旧两张表
3. 旧表数据保留至少 2 个版本

**测试:** memstack 系列 17 用例 + 集成迁移测试

### 1.3 — 统一项目 meta schema

| 文件 | 修改 |
|------|------|
| `backend/common/project_lib/meta.py`（新建） | 定义 `ProjectMeta` Pydantic 模型 |
| `backend/common/process.py` | 改为通过 ProjectMeta 读写 meta |
| `backend/hub/api/observability_api.py` | 同上 |
| `backend/hub/services/project_service.py` | 同上 |

**验证:** 各模块通过 ProjectMeta 读写，不再直接操作 JSON dict

### 1.4 — 封装项目库模块

**新建目录:** `backend/common/project_lib/`

| 文件 | 说明 |
|------|------|
| `project_crud.py` | 项目 CRUD 操作 |
| `project_artifacts.py` | 交付物管理（由原 `backend/common/project_artifacts.py` 迁移） |
| `project_admin.py` | 项目管理操作 |
| `__init__.py` | 统一 ProjectLib 门面类 |

**留在内核:**
- `process.py`（项目执行引擎）
- `project_runtime.py`（进程内调度）
- `project_cancel.py`（取消信号）

### 1.5 — 打破 harness-memstack 双向依赖 🔴🧪（需预研）

**预研（1 天，实验分支 `feat/dep-invert`）:**
- 定义 memstore Protocol，让 harness 和 memstack 都依赖它
- 验证无循环 import
- 验证两边可独立编译

**修改文件:** `backend/memstack/facade.py` + `backend/execution_harness/`

**验证:** 依赖方向单向，`python -c "import ..."` 无循环

---

## 五、Phase 2：结构整理（7 天）

### 任务总览

| 编号 | 任务 | 代码量 | 文件数 | 工作量 | 风险 |
|------|------|--------|--------|--------|------|
| 2.1 | common/ 子目录拆分 ⚠️🧪 | ~200 行 | 85+ 个文件 | 2 天 | 🟠 |
| 2.2 | server.py 端点拆分 | ~500 行 | 10-15 | 2 天 | 🟡 |
| 2.3 | 统一路径常量 | ~100 行 | 10-15 | 0.5 天 | 🟢 |
| 2.4 | 重命名 frontend-v2 → frontend | ~50 行 | 5-8 | 0.5 天 | ✅ |
| 2.5 | 整理 Skill 功能结构 | ~100 行 | 8-10 | 0.5 天 | 🟢 |
| 2.6 | 整理 MCP 功能结构 | ~100 行 | 5-7 | 0.5 天 | 🟢 |
| 2.7 | 清理 agentic-workflows | ~0 行 | 1-2 | 0.5 天 | 🟢 |
| 2.8 | 统一 API 路由组织 | ~200 行 | 8-10 | 0.5 天 | 🟢 |

### 2.1 — common/ 子目录拆分 ⚠️🧪

**目标目录结构:**

```
backend/common/
├── kernel/       # Process, AgentPort, Gate, 状态机
├── agent/        # 交互生命周期
├── skill/        # Skill 相关
├── workflow/     # Workflow 编排
├── store/        # SQLite 存储
├── project/      # 项目库
├── prompt/       # Prompt 模板
├── observability/# 可观测性
└── config/       # 配置管理
```

**预研（0.5 天）:** 先做 2-3 个子目录的 PoC 移动，验证 re-export 兼容方案  
**验证:** 所有 import 通过 re-export 兼容，测试全通过

### 2.2 — server.py 端点拆分

**迁移:** 37 个端点从 `hub/api/server.py` 迁移到 `hub/api/routes/` 下  
**目标:** server.py 不超过 200 行（不含 lifespan 和静态文件）  
**测试:** 现有 API 契约测试（10 用例）+ 集成测试验证端点行为一致

### 2.3 — 统一路径常量

| 文件 | 操作 |
|------|------|
| `backend/common/paths.py` + `backend/hub/paths.py` | 合并到 `backend/paths.py` |

### 2.4 — 重命名 frontend-v2 → frontend ✅ COMPLETED

| 文件 | 操作 |
|------|------|
| `frontend-v2/` | 重命名为 `frontend/` |
| 后端引用 | 同步修改变量名 |
| `package.json` / `package-lock.json` | name 字段更新 |
| `.gitignore` | 构建产物路径更新 |
| `README.md` | 所有引用路径更新 |
| `docs/CODE-WIKI.md` | 所有引用路径更新 |
| `.cursor/skills/myteam-usage/SKILL.md` | 构建命令更新 |

### 2.5 — 整理 Skill 功能结构

将所有 `skill_*.py` 移入 `backend/common/skill/` 子目录

### 2.6 — 整理 MCP 功能结构

将所有 mcp 相关文件统一组织到 `backend/common/mcp/`

### 2.7 — 清理 agentic-workflows

移入 `playbooks/` 或删除（先确认无代码引用）

### 2.8 — 统一 API 路由组织

所有路由模块平级在 `routes/` 下，无顶层 `*_api.py` 文件

---

## 六、Phase 3：质量闭环（10 天）

### 任务总览

| 编号 | 任务 | 代码量 | 文件数 | 工作量 | 风险 |
|------|------|--------|--------|--------|------|
| 3.1 | Rubric 扩展到更多任务类型 | ~300 行 | 4-5 | 2 天 | 🟡 |
| 3.2 | 质量画像页面（前端） | ~800 行 | 6-8 | 2 天 | 🟡 |
| 3.3 | 质量反馈驱动任务分配 | ~400 行 | 5-6 | 2 天 | 🟡 |
| 3.4 | Skill 评审可观测化 | ~300 行 | 4-5 | 1.5 天 | 🟡 |
| 3.5 | 自改进闭环端到端打通 🧪 | ~600 行 | 6-8 | 2 天 | 🔴 |
| 3.6 | 交付物元数据表 | ~200 行 | 3-4 | 0.5 天 | 🟢 |

### 3.1 — Rubric 扩展到更多任务类型

| 文件 | 修改 |
|------|------|
| `backend/execution_harness/post/rubric_eval.py` | 为 coding/research/design 等类型增加评分维度 |
| `business/config/rubric_templates.yaml` | 新增各 task_type 的评分模板 |

**验证:** 不同 task_type 有对应的评分维度和红线

### 3.2 — 质量画像页面（前端）

**新增 UI:** Agent 质量画像页面，展示通过率/自评/评审/重试次数趋势图

### 3.3 — 质量反馈驱动任务分配

| 文件 | 修改 |
|------|------|
| `backend/common/process.py` | team_config 阶段参考质量画像数据选择 Agent |

### 3.4 — Skill 评审可观测化

| 文件 | 修改 |
|------|------|
| `backend/execution_harness/post/skill_review.py` | 从 daemon 线程改为可追踪的后台任务 |

**验证:** 能在 UI 上看到 skill_review 的状态和结果

### 3.5 — 自改进闭环端到端打通 🧪（需预研）

**预研（2 天，实验分支 `feat/self-improve-poc`）:**
- 用一个简单产品文档任务跑通完整循环
- 验证评测→补强→再评测可自动运行

**修改:** `backend/execution_harness/post/self_improve_loop.py`

### 3.6 — 交付物元数据表

| 文件 | 修改 |
|------|------|
| `backend/common/store.py` | 新增 deliverable 表（SQLite）|
| `backend/execution_harness/post/` | 交付时记录元数据 |

---

## 七、Phase 4：配置 UI 全覆盖（12 天）

### 迭代策略

```
UI-1（4 天）      UI-2（5 天）         UI-3（3 天）
Prompt 模板       KB 模板管理          配置导入导出
Delivery Profiles Skill 映射 + Matrix  PGD 配置管理  
Agent 注册表      偏好分节              Skill 组管理
优先级配置         Workflow Profile     配置变更审计
                  工作区文件编辑
                  task_type_rules
```

### UI-1：核心配置补齐（4 天）

#### 页面 1：Prompt 配置中心 `/manage/prompts`

| 项 | 说明 |
|----|------|
| 后端 API | `GET/POST/PUT/DELETE /api/prompt-templates/*` + `GET/POST/PUT/DELETE /api/prompt-injections/*` |
| 页面布局 | 左侧：分类导航（按 kind 分组）<br>右侧：上半区模板列表 + 下半区编辑器（复用 YamlEditor） |
| 复用组件 | `ManageSection` 容器 + Tab 切换（模板/注入） |
| 工作量 | 后端 0.5 天 + 前端 1 天 |

#### 页面 2：Delivery Profiles 管理（嵌入交付模板页 `/manage/templates`）

| 项 | 说明 |
|----|------|
| 后端 API | `GET/POST/PUT/DELETE /api/delivery-profiles/*` |
| 复用组件 | 现有交付模板列表 + Dialog |
| 工作量 | 后端 0.3 天 + 前端 0.7 天 |

#### 页面 3：Agent 注册表编辑（嵌入 Agent 详情页）

| 项 | 说明 |
|----|------|
| 后端 API | `PUT /api/agents/registry/{id}` + `POST /api/agents/registry` |
| 编辑内容 | role 角色名、capabilities、task_types、description |
| 复用组件 | Agent 详情页 + 标签输入 + task_type 多选 |
| 工作量 | 后端 0.5 天 + 前端 0.5 天 |

#### 附加：task_type_agent_priority 配置

| 项 | 说明 |
|----|------|
| 后端 API | `GET/PUT /api/task-types/{id}/priority` |
| 复用组件 | Agent 下拉选择 + 排序拖拽 |
| 工作量 | 后端 0.2 天 + 前端 0.3 天 |

### UI-2：效率配置补齐（5 天）

| # | 功能 | 后端 API | 前端位置 | 复用组件 | 工作量 |
|---|------|---------|---------|---------|--------|
| 1 | 知识库模板管理 | `GET/PUT /api/knowledge/templates` | 知识库页「模板设置」 | YamlEditor + Dialog | 0.5 天 |
| 2 | task_type_skills 映射 | `GET/PUT /api/task-types/{id}/skills` | 任务类型详情「Skill 映射」 | Skill 多选 | 0.5 天 |
| 3 | Skill Matrix 审计 | `GET /api/skills/matrix` | Skill 页「覆盖度审计」 | 表格 + 热力图 | 1 天 |
| 4 | 偏好分节管理 | `GET/PUT /api/preferences/sections` | 偏好库页分节切换 | Markdown 编辑器 | 0.5 天 |
| 5 | Workflow Profiles | `GET/PUT /api/workflows/{id}/profile` | 工作流编辑器侧栏 | 配置表单 | 1 天 |
| 6 | 工作区文件编辑扩展 | 扩展现有 files API | Agent 详情「文件」tab | Markdown 编辑器 | 0.5 天 |
| 7 | agent_task_type_rules | `GET/PUT /api/task-types/rules` | 任务类型页「推断规则」 | 规则编辑器 | 1 天 |

### UI-3：体验完善（3 天）

| # | 功能 | 说明 | 工作量 |
|---|------|------|--------|
| 1 | 配置导入/导出 | 所有配置支持 JSON/YAML 批量导入导出 | 1 天 |
| 2 | PGD 配置管理 | 设置页新增 PGD 子 tab | 0.5 天 |
| 3 | Skill 组管理 | Skill 页「组管理」，vendor 套件批量挂载 | 0.5 天 |
| 4 | 配置变更审计 | 记录谁改了什么配置（对接现有 audit_log） | 1 天 |

### 组件复用方案

```
现有可复用组件                    新增配置页面
───────────────                  ─────────────
ManageSection 容器          ──→  Prompt 配置页、Profile 管理
YamlEditor (Monaco)         ──→  所有 YAML 格式配置编辑
MarkdownEditor              ──→  偏好分节、工作区文件
AgentSelector / AgentPicker ──→  优先级配置、注册表编辑
TaskTypeSelector            ──→  Skill 映射、Delivery Profile 绑定
Dialog / FormDialog         ──→  所有弹出式编辑
TagInput / MultiSelect      ──→  能力标签、task_types 多选
Tab / Tabs                  ──→  详情页多 tab 组织
```

---

## 八、高风险任务与技术预研（5 天）

> 以下预研可在 Phase 0 启动时并行进行，与主线开发不冲突。

| 任务 | 风险等级 | 预研分支 | 预研内容 | 预研验收标准 | 工作量 |
|------|---------|---------|---------|-------------|--------|
| 1.5 双向依赖解耦 | 🔴 | `feat/dep-invert` | 定义 memstore Protocol，让两边都依赖它 | 1. 无循环 import<br>2. 所有测试通过<br>3. 两边可独立编译 | 1 天 |
| 1.2 KB 存储解耦 | 🟠 | `feat/kb-abstract` | 选 2-3 个核心 API 改走 KnowledgeBackend | 1. 核心 KB API 走抽象层<br>2. 切换 mock 后端行为一致<br>3. 性能无明显下降 | 1 天 |
| 3.5 自改进闭环 | 🔴 | `feat/self-improve-poc` | 用一个产品文档任务跑通完整循环 | 1. 评测→补强→再评测能跑通<br>2. 质量分有可测量提升<br>3. 不依赖人工干预 | 2 天 |
| 2.1 common/ 子目录拆分 | 🟠 | 本地 | 先做 2-3 个子目录 PoC | 1. 移动后所有测试通过 | 0.5 天 |
| 0.1 协调者配置化 | 🟡 | 本地 | grep 全量梳理 "main" 引用 | 1. 引用点全梳理<br>2. 边界 case 有测试 | 0.5 天 |

---

## 九、整体路线图

```
Week 1-2               Week 3-4             Week 5-6              Week 7-8
┌────────────────────┐ ┌────────────────┐  ┌────────────────────┐ ┌──────────────┐
│ Phase 0 (8.5天)     │ │ Phase 1 (7天)  │  │ Phase 2 (7天)      │ │Phase 4/3并行  │
│ ├─ T1-T3 前置测试   │ │ ├─ 1.1 偏好库   │  │ ├─ 2.1+2.3 合并    │ │├─UI-1 (4天)   │
│ ├─ 0.6 旧路径       │ │ ├─ 1.2 KB解耦   │  │ ├─ 2.2 server拆分  │ │├─UI-2 (5天)   │
│ ├─ 0.1+0.4+P2 协调  │ │ ├─ 1.3 meta   │  │ ├─ 2.4-2.8 小项    │ │├─UI-3 (3天)   │
│ ├─ 0.2+0.3+P2 Gate  │ │ ├─ 1.4 项目封装 │  │ └─ 验收            │ │├─3.1-3.6 (10天)│
│ ├─ 0.5 KB 抽象      │ │ └─ 1.5 依赖反转 │  │                    │ │└─ 最终验收     │
│ ├─ P2 余项          │ └─ 验收          │  │                    │ │                │
│ └─ Step7 切 flag    │                  │  │                    │ │                │
└────────────────────┘ └────────────────┘  └────────────────────┘ └──────────────┘
                     ↑ Phase 1 与 Phase 4 建议错峰并行
```

### 并行策略

| 并行组合 | 前提 | 说明 |
|---------|------|------|
| Phase 1 ‖ Phase 2 | Phase 0 完成 | 三库独立（后端）+ 结构整理（后端）可并行 |
| Phase 4 UI-1 ‖ Phase 1.1 | Phase 0 完成 | 但 UI-1 的 Prompt 模板页依赖 1.1 的偏好库接口。建议 Phase 1 先跑 2 天完成 1.1，Phase 4 再启动 |
| 高风险预研 ‖ 主线 | 随时 | 预研在实验分支进行，不阻塞主线 |
| Phase 4 ‖ Phase 3 | Phase 0-2 完成 | UI 前端 + 质量闭环后端可并行 |

---

## 十、数据迁移与回滚预案

### 迁移策略总原则

1. **向前兼容读，向后兼容写**：新代码能读旧格式，旧代码能读新格式
2. **版本号检测 + 增量迁移**：每个存储结构有 schema_version，启动时检测
3. **先迁数据，再切流量**：数据迁移完成并验证后，才切换默认路径
4. **可一键回滚**：每个迁移都有对应回滚方案，出问题 5 分钟能切回去
5. **不删除旧数据**：迁移后旧数据保留至少 2 个版本周期

### 各 Phase 迁移与回滚

| Phase | 任务 | 迁移类型 | 迁移方案 | 回滚方案 |
|-------|------|---------|---------|---------|
| Phase 0 | 0.6 旧路径清理 | 文件路径迁移 | 启动时检测 task_data.json → 写入 SQLite → 标记 .bak | 关 flag → 读回旧 JSON |
| | 0.2 code_project | 逻辑变更 | 新增 outcome_kind 字段，默认值从旧列表推断 | 关 flag → 用回旧列表 |
| | 0.3 PGD 严格类型 | 逻辑变更 | 新增 strict_must_include 字段 | 关 flag → 用回旧集合 |
| | 0.5 KB 抽象修复 | 调用路径变更 | 抽象层与直连层并行，flag 控制 | 关 flag → 走回直连 |
| Phase 1 | 1.2 KB 存储解耦 | 存储结构迁移 | 新 kb_entries 表 + 双写过渡期 | 关 flag → 读回 memory 表 |
| | 1.3 项目 meta | 数据格式迁移 | ProjectMeta 模型定义 + 兼容层 | 旧格式兼容层保留 |
| Phase 2 | 2.1 common/ 拆分 | 代码结构变更 | re-export 兼容 import 路径 | 旧路径通过 re-export 可用 |

### 回滚触发条件

1. 数据条数不一致 / 关键字段丢失
2. 核心功能不可用（项目创建、任务执行、Gate 检查）
3. 关键路径响应退化 > 2x
4. 错误率 > 1% 持续 5 分钟
5. 用户无法完成核心工作流

---

## 十一、端到端验证方案

### 场景 1：标准编排项目（覆盖全部 Phase）

```
1. 创建项目（通过 Hub UI）
   ├─ 验证：项目状态为 pending
   └─ 验证：project_service 从 SQLite 读取（0.6）

2. 启动项目（run_kernel.py --mode one_shot）
   ├─ 验证：team_config 阶段协调者为配置角色（0.1）
   ├─ 验证：Agent 显示名正确（0.4）
   ├─ 验证：task_plan 阶段 DAG 正常生成
   ├─ 验证：execute 阶段 Agent 正常执行
   ├─ 验证：Gate 门禁正常检查（0.2/0.3）
   ├─ 验证：完成状态为 completed
   └─ 验证：交付物正常生成

3. 查看项目详情（通过 Hub UI / API）
   ├─ 验证：项目仪表盘正常展示（0.6）
   ├─ 验证：事件流正常推送
   └─ 验证：Gate 失败详情可查看

4. 查看知识库（通过 Hub UI / API）
   └─ 验证：KB 条目正常检索（0.5）
```

### 场景 2：协调者角色切换

```
1. 修改 coordinator_agent_id 为 "pm"
2. 创建并启动编排项目
   ├─ 验证：team_config 阶段使用 pm
   ├─ 验证：task_plan 阶段使用 pm
   ├─ 验证：triage 阶段使用 pm
   └─ 验证：项目最终正常完成
```

### 场景 3：Gate 配置化验证

```
1. 新增 task_type，设置 outcome_kind=code_project
2. 创建项目 → 验证 flag 开启/关闭两种状态

3. 新增 task_type，设置 strict_must_include=true
4. 创建项目 → 验证 flag 开启/关闭两种状态
```

### 场景 4：flag 回退验证

```
1. 全量开启所有 flag，跑场景 1
2. 全量关闭所有 flag，再跑场景 1
   └─ 验证：关闭 flag 后行为与 v1.0 完全一致
```

---

## 十二、执行验收清单

### 执行步骤

- [ ] **Step 0（核实行号）：** 每项修改前先全量 grep 核实行号
- [ ] **Step 1:** 补 T1-T3 前置测试
- [ ] **Step 2:** 0.6 旧路径清理 → flag=false，验证回归
- [ ] **Step 3:** 0.1 + 0.4 + P2.12 → flag="main"，验证回归
- [ ] **Step 4:** 0.2 + 0.3 + P2.9/P2.10/P2.11 → flag=false，验证回归
- [ ] **Step 5:** 0.5 + P2.6/P2.7 → flag=false，验证回归
- [ ] **Step 6:** P2.8 规则 profile → 验证回归
- [ ] **Step 7:** Phase 0 验收（全部测试 + 端到端 4 场景）
- [ ] **Step 8:** 逐一切 flag，观察运行
- [ ] **Step 9-13:** Phase 1-4 依次执行（按各自验收清单）

### 各阶段验收标准

#### Phase 0 验收

- [ ] 协调者角色可通过配置修改，修改后项目正常运行
- [ ] 新增 task_type 设置 outcome_kind=code_project 后，包态逻辑正常
- [ ] 新增 task_type 设置 strict_must_include=true 后，强校验生效
- [ ] 所有 Agent 显示名从 agents_registry.json 读取
- [ ] observability_api 的 memory 操作走 KnowledgeBackend 接口
- [ ] project_service 和 project_group_service 不再读 task_data.json
- [ ] 每个 P0 变更有对应的 feature flag，关闭 flag 后行为与 v1.0 一致
- [ ] 所有现有测试通过

#### Phase 1 验收

- [ ] 偏好库模块可独立 import（不依赖 hub）
- [ ] 知识库有独立的 MemoryStore Protocol
- [ ] KB 后端可独立切换，不依赖 common.store
- [ ] ProjectMeta Pydantic 模型定义并被所有模块使用
- [ ] 项目库有统一的 ProjectLib 门面类
- [ ] 无循环 import
- [ ] 所有现有测试通过

#### Phase 2 验收

- [ ] common/ 下有 8+ 个子目录，无子目录外的功能模块
- [ ] server.py 不超过 200 行（不含 lifespan 和静态文件）
- [ ] 只有一个 paths.py 定义路径常量
- [ ] frontend 目录名已改为 frontend/
- [ ] Skill 和 MCP 功能各自有统一的目录组织
- [ ] 所有 API 路由统一在 routes/ 下
- [ ] 所有现有测试通过

#### Phase 3 验收

- [ ] 至少 3 种非产品类任务类型有 Rubric 评分
- [ ] 质量画像页面可访问，展示 Agent 质量趋势
- [ ] team_config 阶段参考质量画像分配任务
- [ ] skill_review 有可观测的状态和结果
- [ ] 自改进循环可端到端运行（有测试验证）
- [ ] deliverable 表存在并被使用
- [ ] 所有现有测试通过

#### Phase 4 验收

- [ ] Prompt 模板可通过 UI 增删改查，修改后生效
- [ ] Prompt 注入块可通过 UI 管理，注入效果正确
- [ ] Delivery Profiles 可通过 UI 创建/编辑/删除
- [ ] Agent 注册表（角色/能力/task_types）可通过 UI 编辑
- [ ] task_type_agent_priority 可通过 UI 配置，分配顺序正确
- [ ] 知识库模板可通过 UI 管理
- [ ] task_type_skills 映射可通过 UI 配置
- [ ] Skill Matrix 覆盖度审计页面可访问
- [ ] 偏好库分节可通过 UI 编辑
- [ ] Workflow Profiles 可通过 UI 选择和编辑
- [ ] Agent 工作区身份文件可通过 UI 编辑
- [ ] agent_task_type_rules 可通过 UI 配置
- [ ] 配置 UI 覆盖率达到 100%（127 项配置全部有 UI 入口）
- [ ] 用户完成完整团队配置流程不需要手动编辑任何配置文件
- [ ] 所有现有测试通过

#### 端到端验收（跨所有 Phase）

- [ ] 场景 1（标准编排）：全部 4 步骤通过
- [ ] 场景 2（协调者切换）：改配置后项目正常
- [ ] 场景 3（Gate 配置化）：两种状态都正确
- [ ] 场景 4（回退验证）：全关 flag 后与 v1.0 一致

---

## 十三、附录：关键文件索引

| 问题领域 | 关键文件 | 说明 |
|---------|---------|------|
| 协调者硬编码 | `backend/common/decision_pipeline.py` | 11 处 "main"，269 行，零测试 |
| code_project 硬编码 | `backend/common/project_artifacts.py` | CODE_PROJECT_TASK_TYPES |
| PGD 严格类型 | `backend/common/gate.py` | _PGD_STRICT_TYPES |
| 显示名硬编码 | `backend/common/agent_transport.py` | _AGENT_DISPLAY_NAMES |
| KB 存储耦合 | `backend/memstack/kb/sqlite.py` | 直接依赖 Store |
| 旧路径问题 | `backend/hub/services/project_service.py` | 读 task_data.json |
| KB API 绕过 | `backend/hub/api/observability_api.py` | 5 处 store.memory_* |
| common/ 膨胀 | `backend/common/` | 85 个模块平铺 |
| server.py 膨胀 | `backend/hub/api/server.py` | 975 行 37 端点 |
| 自改进闭环 | `backend/execution_harness/self_improve_loop.py` | 框架未完全打通 |
| 质量画像 | `backend/execution_harness/post/quality.py` | 有数据无展示 |
| 双向依赖 | `backend/memstack/facade.py` + `backend/execution_harness/` | 互相调用 |
| 工作流推导 | `backend/common/workflow_suggest.py` | 模板硬编码（P2） |
| 身份文件模板 | `backend/common/agent_bootstrap.py` | dict 硬编码（P2） |
| 规则 profile | `backend/common/rules_merge.py` | 3 个常量硬编码（P2） |
| 废弃别名 | `backend/common/agent_id_policy.py` | dict 硬编码（P2） |

---

## 十四、勘误与差异说明

| # | 问题 | 方案处理 | 状态 |
|---|------|---------|------|
| 1 | 行号可能已偏移 | 每个修改前先全量 grep 核实行号（Step 0） | ✅ |
| 2 | 0.6 可能漏掉更多 task_data.json 引用 | 全量 grep 发现所有引用点后再改 | ✅ |
| 3 | T2/T3 缺少具体测试用例 | 已补（T2 3 用例、T3 4 用例） | ✅ |
| 4 | 0.1 硬编码可能不限于 decision_pipeline | 增加 workflow_loader 等文件的全量 grep | ✅ |
| 5 | 0.4 显示名一致性假设未验证 | 增加实施前的名字对比步骤 | ✅ |
| 6 | Phase 0 工作量与 GAP 不一致 | 说明差异由前置测试补全引起 | ✅ |
| 7 | 0.5 flag 切换时机不明确 | Step 7 描述为逐一切换 | ✅ |
| 8 | Phase 1 ‖ Phase 4 并行有接口依赖风险 | 增加并行约束说明 | ✅ |
| 9 | 仅 Phase 0 覆盖，1-4 无细节 | 已全量补齐 §四~§七 | ✅ |