# myteam 问题清单

> 生成日期：2026-06-28
> 排查范围：内核可靠性、前端页面、后端API、数据一致性
> 排查方法：代码审查 + SQLite 数据验证 + 前端路由核查

---

## 问题总览

| 严重度 | 数量 | 说明 |
|--------|------|------|
| P0 | 2 | 影响核心功能，用户直接可感知 |
| P1 | 4 | 影响可靠性，断点续跑/任务调度异常 |
| P2 | 3 | 功能缺失/代码卫生，不影响主流程 |
| **合计** | **9** | |

---

## P0 — 立即修复

### #1 项目列表API硬编码任务数为0

- **位置**：`backend/hub/services/project_service.py:50-54`
- **现象**：`_sqlite_list_projects` 返回所有项目的 `task_count=0, progress=0, current_task_id=None, executor_pid=None`，全部硬编码
- **根因**：SQLite 路径未查询 task 表计算任务数和进度，对比 `task_data.json` 路径的 `_summarize`（行 124-138）正确计算
- **影响**：前端项目列表页对所有项目恒显示 0 任务、0% 进度，用户无法了解项目执行状态
- **修复方案**：在 `_sqlite_list_projects` 中增加 task 表查询，计算 `task_count`、`completed` 数量、`progress` 百分比、`current_task_id`（取 `in_progress` 状态的任务）
- **验证方式**：调用 `GET /api/projects`，确认返回的 `task_count` 和 `progress` 与 SQLite 实际数据一致

### #2 PromptsPage 未挂载路由

- **位置**：`frontend/src/App.tsx:31-53`（无 `/prompts` 路由）；`frontend/src/pages/PromptsPage.tsx:27`（完整页面组件已存在）
- **现象**：Prompt 模板/注入管理页面已完整实现（含 `handleDeleteTemplate` 行 102、`handleDeleteInjection` 行 159，调用 `/api/prompt-templates` 与 `/api/prompt-injections`），但全仓无任何文件 import 它，也无对应 `PromptsSection`
- **根因**：页面组件已创建但未在 App.tsx 路由中挂载
- **影响**：Prompt 模板和注入管理功能在 UI 中完全不可达，用户无法管理提示词模板
- **修复方案**：在 `App.tsx` 中增加 `/prompts` 路由导入 PromptsPage，或在导航栏增加入口；后端 API 已完整（`prompt_templates_api.py` + `prompt_injections_api.py` 均有完整 CRUD）
- **验证方式**：启动 Hub 后访问 `/prompts` 路径，确认页面正常加载

---

## P1 — 尽快修复

### #3 triage split 绕过 max_split_depth 限制

- **位置**：`backend/common/plan_expansion.py:45-101`（`apply_split()` 不检查深度）+ `backend/common/process.py:328-333, 482-486, 500-505`（triage 路径直接调 apply_split）
- **现象**：`max_split_depth` 配置存在（`process_types.py:34`，默认 2），但仅在 evaluate 路径生效（`plan_expansion.py:110, 156`）。triage 驱动的 split 走 `apply_split()`，调用前无任何深度判断
- **根因**：`apply_split()` 方法本身不检查 `max_split_depth`，triage 链式 split（子任务失败→再 triage split）可递归超出限制
- **影响**：任务树无限膨胀，仅靠 token budget 兜底。违背"无论 agent 怎么判都收敛"的硬底承诺
- **修复方案**：在 `apply_split()` 开头增加 `if depth >= self.config.max_split_depth: return` 检查
- **验证方式**：构造 triage 链式 split 场景，确认超过 max_split_depth 后不再拆分

### #4 resume 丢失运行时标志

- **位置**：`backend/common/run_kernel.py:232-234` + `backend/hub/services/project_launch.py:143-148` + `backend/common/kernel_config.py:90-119`
- **现象**：resume 时只传 `mode / token_budget / backend` 三项，不读回 `review_enabled`、`split_enabled`、`needs_review_blocks`、`skill_extract` 标志。这些标志在首跑时写入了 `proj_meta["launch"]`（`process.py:113-120`），但 resume 时从未读回
- **根因**：`kernel_config.process_from_defaults` 根本不处理 `needs_review_blocks` 字段，`ProcessConfig` 该字段恒为默认 False
- **影响**：原运行用 workflow 设了 `needs_review_blocks=True` 或 `--review`/`--split`，续跑后全部回退到默认（False/关闭），行为与首次运行不一致
- **修复方案**：`resume_project` 从 `proj_meta["launch"]` 读回所有标志，传入 `kernel_configs_for_run`；`process_from_defaults` 增加 `needs_review_blocks` 字段处理
- **验证方式**：以 `--review` 启动项目，pause 后 resume，确认续跑仍保持 review 行为

### #5 recurring 项目 resume 不恢复循环

- **位置**：`backend/common/process.py:190`
- **现象**：`resume()` 直接调 `_dispatch`，不调 `_run_recurring`。paused 的 recurring 项目续跑只完成当前周期剩余 DAG，不会启动后续新周期
- **根因**：resume 逻辑未区分 one_shot 和 recurring 模式
- **影响**：recurring 项目断点续跑后只完成当前周期，后续周期不会自动启动，与"续跑"语义有偏差
- **修复方案**：`resume()` 检测 `mode == "recurring"` 且当前周期 DAG 已完成时，调用 `_run_recurring` 启动下一周期
- **验证方式**：recurring 项目 pause 在周期边界，resume 后确认新周期自动启动

### #6 群聊去重仅在持久化层

- **位置**：`backend/hub/services/` 下无去重逻辑；去重在 `backend/common/group_message_store.py:186-243`（60s 窗口相同内容跳过写入）
- **现象**：`group_broadcast.py:29-41`（publish 仅扇出，无去重）、`notify_service.py:169-211`（直接调 send_group_message，无幂等键）、`project_group_service.py:170-178`（无去重）
- **根因**：去重逻辑只在持久化层，services 层和路由层无幂等逻辑
- **影响**：不防重复 Agent 路由/调度（`notify_via_project_group` 用 `route_only=True` 重复投递仍会重复触发 Agent）
- **修复方案**：在 `notify_service.notify_via_project_group` 增加幂等键检查（基于 `group_id + task_id + event_type` 短窗口去重）
- **验证方式**：同一事件多次触发通知，确认 Agent 只被调度一次

---

## P2 — 后续修复

### #7 Skill 分类无法删除

- **位置**：`backend/hub/api/skills_api.py`（无 DELETE `/api/skills/categories/{category_id}`）+ `frontend/src/components/skills/SkillCategoryManageDialog.tsx:176-202`（无删除按钮）
- **现象**：分类管理只有创建（POST）和编辑（PATCH），无删除。对比 Skill 个体删除正常（DELETE `/api/skills/library/{skill_id}` 在行 180）
- **影响**：分类管理功能不完整，无法删除无用分类
- **修复方案**：后端增加 DELETE `/api/skills/categories/{category_id}`（删除前检查是否有 member）；前端 `SkillCategoryManageDialog` 增加删除按钮和确认对话框
- **验证方式**：创建测试分类后删除，确认分类和 member 关联正确清理

### #8 7 个 pages 为死代码

- **位置**：`frontend/src/pages/` 目录
- **涉及文件**：`AgentsPage.tsx`、`GroupsPage.tsx`、`ProjectsPage.tsx`、`ProjectDetailPage.tsx`、`GroupChatPage.tsx`、`TaskTypesPage.tsx`、`WorkflowsPage.tsx`
- **现象**：这 7 个页面已被 `sections/` 组件内联覆盖，全仓无任何文件 import 它们（除 DashboardPage 和 SettingsPage 外）
- **影响**：代码卫生问题，不影响功能，但增加维护成本
- **修复方案**：删除这 7 个文件，或标记为 `@deprecated` 并添加注释指向对应的 Section 组件
- **验证方式**：删除后 `npm run build` 确认无编译错误

### #9 _use_sqlite_store 仅模块加载时初始化

- **位置**：`backend/hub/services/project_service.py:24-34`
- **现象**：`_use_sqlite_store` 标志在模块加载时从 `system_config` 读取一次，缓存于 `_USE_SQLITE_FLAG_INITED`，运行时修改配置不生效
- **影响**：运行时修改 `system_config.json` 的 `use_sqlite_project_store` 需重启进程才能生效
- **修复方案**：改为每次调用 `list_projects` 时读取配置，或增加配置变更后的刷新机制
- **验证方式**：运行时修改配置后立即调用 API，确认行为切换

---

## 已确认正常的设计行为（非 bug）

| 项目 | 说明 |
|------|------|
| needs_review 不清除 | D18 设计，needs_review 是成功终态，不阻塞项目完成（`needs_review_blocks` 默认 False） |
| recurring 零进度保护 | 存在且有效（`process.py:278-280`），本周期无任何任务到达 completed/needs_review 即停止 |
| token budget resume 恢复 | 正确恢复并多层检查（AgentPort 交互级 + 派发级 + 规划级） |
| 知识库 CRUD | 完整（GET/POST/PUT/DELETE） |
| 偏好库 CRUD | 完整（GET/PUT 整文档，单文档无单条删除属设计如此） |
| Prompt 模板/注入 CRUD | 完整（含 DELETE） |
| agent_task_type_rules CRUD | 完整（含 DELETE） |

---

## 数据一致性核查

| 数据项 | 升级报告声称 | 验证报告声称 | 实际值（2026-06-28） | 说明 |
|--------|-------------|-------------|---------------------|------|
| Skill 总数 | 43 | 43 | 43 | 一致 |
| KB 条目总数 | 226 | 50 | 246 | 升级报告为快照数据，验证报告查的可能是 global 条目(15)，实际 memory 表 246 行 |
| Agent 数量 | 13 | 13 | 13 | 一致 |
| Agent-Skill 关联 | 70+ | 71 | 71 | 一致 |
| 偏好库规则数 | 50+ | 55 | 55 | 一致 |
| 偏好库节数 | 8 | 8 | 8 | 一致 |
| 分类体系 | 7 | 7 | 7 | 一致 |
| use_sqlite_project_store | true | false | true | 验证报告查时可能读到默认值，当前确实是 true |

---

## 修复优先级建议

1. **立即修**：#1 项目列表API硬编码0 — 前端项目页完全看不到进度
2. **立即修**：#2 PromptsPage 挂载路由 — 已实现的页面不可用
3. **尽快修**：#3 triage split 深度限制 — 防止任务树无限膨胀
4. **尽快修**：#4 resume 标志恢复 — 断点续跑行为不一致
5. **尽快修**：#6 群聊去重上提到 services 层 — 防重复 Agent 调度
6. **尽快修**：#5 recurring resume 恢复循环 — 循环任务断点续跑
7. **后续修**：#7 Skill 分类删除 API+UI
8. **后续修**：#9 _use_sqlite_store 动态读取
9. **后续修**：#8 清理死代码 pages
