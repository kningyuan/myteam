# myteam 升级测试方案

> **文档类型**：测试策略与计划（Test Plan）
> **测试日期**：2026-06-06/07（两轮执行）
> **测试基线**：分支 `upgrade/continued`，commit `0dedb7a` + 修复增量
> **基干文档**：myteam-upgrade-comprehensive-plan.md / myteam-upgrade-design-spec.md / changelist-upgrade-implementation.md
> **测试负责人**：测试专家 (tester)

---

## 1. 测试概述

### 1.1 测试目标

对 myteam 升级项目（R0–R3）进行系统性验收测试，确认：

1. **需求完整性**：已实现功能是否覆盖产品规格定义的需求
2. **设计一致性**：实现是否符合设计规格书的接口契约和数据模型
3. **工程质量**：测试门禁是否满足、代码质量是否达标
4. **功能正确性**：核心 API 和前端功能是否正常工作

### 1.2 测试范围

| 阶段 | 范围 | 优先级 |
|------|------|--------|
| **R0** | 测试回归修复、CI 脚本、FastAPI lifespan 迁移、交付物 API 修复 | P0 |
| **R1** | Demo 目录化、CLI 友好错误、Hub 建项/启项/空态、交付物闭环、友好错误格式 | P0 |
| **R2** | WorkspaceEvent 模型与投影、频道 API、Job Supervisor、Agent Runtime、事件处理链 | P0 |
| **R3** | DAG 可视化、时间线 UI、Onboarding、Chat/Groups UX、成本可视化、Agent/设置页、前端模块化、亮色主题 | P1 |
| **R4** | 未实现，不做测试 | — |

### 1.3 测试策略

| 层级 | 工具 | 覆盖目标 | 速度目标 |
|------|------|----------|----------|
| 自动化单元测试 | pytest | Store CRUD、Gate 校验、契约验证、事件映射 | <30s |
| 自动化集成测试 | pytest + httpx | API 路由、错误响应、数据流 | <20s |
| API 端点实测 | curl + Hub 运行 | 真实 API 可达性和响应格式正确性 | 即时 |
| 前端代码审查 | grep / 静态分析 | 功能连线、模块化约束、设计系统 | — |
| 差异分析 | diff 规格 vs 实现 | 需求覆盖、接口一致性 | — |

### 1.4 测试环境

```bash
# 环境要求
export MYTEAM_ROOT="/Users/user/myteam"
export PYTHONPATH="$MYTEAM_ROOT/backend"
VENV: /Users/user/myteam/venv (Python 3.13)
Hub: http://localhost:8765

# 运行单元测试
venv/bin/python3 -m pytest backend -q --tb=short

# 运行 Hub 测试 API
./run.sh start
```

### 1.5 测试门禁

| 关卡 | 条件 | 状态 |
|------|------|------|
| PR 提交 | `pytest backend -q` 全绿 | ✅ 205 passed / 8.46s |
| R0→R1 | pytest <60s 全绿 | ✅ 8.46s |
| R1→R2 | Demo 跑通 + 交付物可预览 | ❌ Demo task_plan 失败（CLI 未配） |
| R2→R3 | WorkspaceEvent API 可用 + job 可取消 | ⚠️ 部分通过 |
| R3→R4 | §14.5 页面清单可演示 | ❌ 缺少 DAG/时间线 tab |

---

## 2. 测试用例清单

### 2.1 R0 — 工程可信底座

| ID | 优先级 | 类型 | 描述 | 预期结果 | 关联需求 |
|----|--------|------|------|----------|----------|
| T-R0-1 | P0 | 自动化 | `pytest backend -q` 全量通过 | 205 passed, <60s | R0-1 |
| T-R0-2 | P0 | 自动化 | SSE endpoint 有 timeout 保护 | 测试不挂起 >30s | R0-1 |
| T-R0-3 | P0 | 自动化 | `test_deliverable_read` 通过 | 路径对齐 | R0-2 |
| T-R0-4 | P0 | 自动化 | `test_deliverable_file_read` 通过 | Store monkeypatch | R0-2 |
| T-R0-5 | P1 | 代码审查 | 启动无 DeprecationWarning | lifespan 替代 on_event | R0-4 |
| T-R0-6 | P1 | 代码审查 | CI 脚本存在 | scripts/test.sh 可执行 | R0-3 |

### 2.2 R1 — 产品闭环

| ID | 优先级 | 类型 | 描述 | 预期结果 | 关联需求 |
|----|--------|------|------|----------|----------|
| T-R1-1 | P0 | 代码审查 | `business/demo/` 目录含 goal.txt | 目录存在、文件可读 | R1-1 |
| T-R1-2 | P0 | 代码审查 | CLI 支持 `--demo` 读取目录化 goal | run_kernel 含 _read_demo_goal() | R1-1 |
| T-R1-3 | P0 | 代码审查 | `_friendly_traceback` 覆盖 5 类错误 | FileNotFoundError/CalledProcessError/RuntimeError 等 | R1-2 |
| T-R1-4 | P0 | API 实测 | `POST /api/init` 返回 success=true | 200 + `{"success": true}` | R1-3 |
| T-R1-5 | P0 | API 实测 | `POST /api/demo` 返回 project_id | 200 + `{"project_id": "...", "started": true}` | R1-3 |
| T-R1-6 | P0 | API 实测 | `POST /api/projects/run` 创建并启动项目 | 200 + project_id | R1-3 |
| T-R1-7 | P0 | API 实测 | `POST /api/projects/run` 空 goal 返回错误 | 400 + 错误提示 | R1-3 |
| T-R1-8 | P0 | 代码审查 | `APIError` 类存在 + `ERROR_CODES` 定义 | 统一错误格式 | R1-5 |
| T-R1-9 | P0 | API 实测 | 不存在项目查询返回 404 | 404 + 错误信息 | R1-5 |
| T-R1-10 | P0 | API 实测 | Deliberable API 可访问 | 返回 deliverable 数据结构 | R1-4 |

### 2.3 R2 — Agent Workspace 一体化

| ID | 优先级 | 类型 | 描述 | 预期结果 | 关联需求 |
|----|--------|------|------|----------|----------|
| T-R2-1 | P0 | 代码审查 | `workspace_event` 表存在 store.py | 含 id/type/source/target/payload/metadata/visibility/timestamp | R2-1 |
| T-R2-2 | P0 | 代码审查 | `append_workspace_event` / `list_workspace_events` 方法 | CRUD 完整 | R2-1 |
| T-R2-3 | P0 | API 实测 | `GET /api/workspace/events` 返回事件列表 | 200 + events 数组 | R2-1 |
| T-R2-4 | P0 | 代码审查 | `_map_to_workspace_event` 覆盖 ≥16 种 run_event kind | 映射完整 | R2-1a |
| T-R2-5 | P0 | API 实测 | `GET /api/workspace/channels` 返回频道列表 | 200 + channels 数组 | R2-2 |
| T-R2-6 | P0 | API 实测 | `POST /api/workspace/channels` 创建频道 | 201 + channel_id | R2-2 |
| T-R2-7 | P0 | 代码审查 | `job` 表和 `agent_runtime` 表存在 | schema 符合设计 | R2-3 |
| T-R2-8 | P0 | API 实测 | `GET /api/jobs` 返回 job 列表 | 200 + jobs 数组 | R2-3 |
| T-R2-9 | P0 | API 实测 | `GET /api/obs/agents` 返回 agent 运行时状态 | 200 + agents 数组 | R2-3 |
| T-R2-10 | P0 | API 实测 | `POST /api/projects/{id}/cancel` 可访问 | 项目存在时返回 200 | R2-3 |
| T-R2-11 | P0 | 代码审查 | `EventPipeline` 类存在 + 4 种内置处理器 | register/dispatch 模式 | R2-4 |

### 2.4 R3 — 体验与可视化升级

| ID | 优先级 | 类型 | 描述 | 预期结果 | 关联需求 |
|----|--------|------|------|----------|----------|
| T-R3-1 | P0 | 代码审查 | `dag-renderer.js` 存在 | SVG 渲染、6 种状态色 | R3-1 |
| T-R3-2 | P1 | 前端审查 | `renderDAG()` 被 app.js 调用 | 功能实际连线 | R3-1 |
| T-R3-3 | P0 | 代码审查 | `timeline.js` 存在 | 12 种事件类型、中文标签 | R3-2 |
| T-R3-4 | P1 | 前端审查 | `renderTimeline()` 被 app.js 调用 | 功能实际连线 | R3-2 |
| T-R3-5 | P1 | API 实测 | `GET /api/status` 返回 initialized/trends | 完整状态信息 | R3-3 |
| T-R3-6 | P0 | 前端审查 | @mention 逻辑存在 | mentionActive/mentionFilter | R3-4 |
| T-R3-7 | P0 | 前端审查 | thinking section collapsible | 折叠/展开 toggle | R3-4 |
| T-R3-8 | P0 | 代码审查 | budgetBar 函数存在 | 预算告警条 | R3-5 |
| T-R3-9 | P1 | 前端审查 | Agent 抽屉编辑可取消 | showConfirm 实现 | R3-6 |
| T-R3-10 | P1 | 前端审查 | `tokens.css` 存在且含设计变量 | 57 个 token + 19 个 light 变量 | R3-7 |
| T-R3-11 | P1 | 代码审查 | app.js 行数 < 800 | 模块化后入口文件 | R3-7 |
| T-R3-12 | P1 | 代码审查 | style.css 行数 < 600 | 拆分后单文件 | R3-7 |
| T-R3-13 | P1 | 代码审查 | `[data-theme=light]` 变量完整 | light 主题覆盖 | R3-8 |
| T-R3-14 | P0 | 代码审查 | 前端显示删除二次确认 | showConfirm + danger | R3-9 |

---

## 3. 测试方法

### 3.1 自动化测试

全量 pytest 作为第一道防线，验证 Store CRUD、Gate 校验、契约验证、SSE 流等基础功能。

```bash
# 执行全量测试
cd /Users/user/myteam
export PYTHONPATH="$PWD/backend"
venv/bin/python3 -m pytest backend -q --tb=short
```

### 3.2 API 端点实测

Hub 启动后，使用 curl 对关键端点进行真实请求测试，验证：
- HTTP 状态码
- 响应体结构
- 错误格式一致性
- 参数过滤支持

### 3.3 代码审查

对设计规格 §4 中定义的每个模块进行静态分析：
- 接口签名是否匹配设计规格
- 数据模型是否匹配设计规格
- 功能是否实际连线（声明 vs 调用）
- 文件行数约束是否满足

### 3.4 差异分析

对比「changelist-upgrade-implementation.md」中的完成声明与实际代码，识别：
- 声明完成但未实现的项
- 实现与设计规格的不一致
- 缺失的测试覆盖率

---

## 4. 风险与限制

| 风险 | 说明 | 影响 |
|------|------|------|
| **Demo 无法完整跑通** | task_plan 失败（CLI 未正确配置），E2E 验收阻塞 | 影响 R1→R2 门禁验证 |
| **前端功能未连线** | DAG/timeline 渲染函数定义但未从 app.js 调用 | 产品规格 §5.2 的 DAG/时间线 tab 不可用 |
| **Job Supervisor 未实现** | 仍使用内存 `_KERNEL_RUNS`，无持久化 job 管理 | R2-3 核心功能缺失 |
| **无 R2/R3 测试** | workspace_event、job、agent_runtime 均无 pytest | 回归风险高 |
| **错误格式不统一** | 部分端点仍返回旧 FastAPI `{"detail":...}` 格式 | 前端统一错误处理困难 |

---

## 5. 测试交付物

| 交付物 | 说明 |
|--------|------|
| 本文件 | 测试方案（范围、策略、用例清单） |
| myteam-upgrade-test-record.md | 测试记录（逐项执行结果） |
| myteam-upgrade-test-results.md | 测试详细结果（缺陷与质量报告） |