# Hub 2.0（React + Vite + shadcn 风格组件）

默认生产 UI。经典版 `frontend/` 已归档（源码保留，默认不再对外提供）。

## 开发

```bash
# 终端 1：Hub API
cd .. && ./run.sh start

# 终端 2：Vite dev（proxy /api → 8765）
cd frontend && npm install && npm run dev
# 打开 http://localhost:5173/v2/
```

## 生产构建

```bash
npm run build
cd .. && ./run.sh restart
# 打开 http://127.0.0.1:8765/  （自动进入 /v2/）
```

Hub 在 `frontend/dist` 存在时：`/` 302 → `/v2/`，并挂载 `/v2` SPA。

临时恢复经典版：`MYTEAM_V1_UI=1 ./run.sh start`，访问 http://127.0.0.1:8765/classic/

## 工程架构

### 技术栈

React 19 + Vite 8 + TypeScript 6 + Tailwind CSS v4 + Radix UI / shadcn 风格组件。SPA，`BrowserRouter basename="/v2"`。

### 目录分层

```
src/
├── pages/          顶层路由页面（Dashboard / Settings，极薄分发器）
├── sections/       一级功能大区（9 个：Chat/Groups/Projects/Execute/Manage/...）
├── components/     组件（按业务域分子目录：chat/layout/manage/project/workflow/skills/mcp/ui）
│   └── ui/         shadcn 原子组件（button/card/dialog/input/select/tabs/table 等 15 个）
├── lib/
│   ├── api/        后端对接层（client.ts 传输 + 10 个领域文件 + barrel index）
│   ├── ports/      可插拔端口抽象（ChatPort/ProjectsPort 接口 + Hub 默认实现）
│   ├── chat/       对话领域逻辑（SSE 流管理、标签、群聊实时）
│   ├── project/    项目领域逻辑（执行树、标签）
│   ├── dataRefresh.ts  跨页面资源缓存失效总线
│   └── utils.ts    cn() 类名合并等工具
├── hooks/          自定义 hooks（useResourceQuery / useAgentChat / use-column-width / ime）
├── assets/         静态资源
└── test/           测试 setup（jest-dom + cleanup）
```

### 数据流

```
UI(sections/components)
  ↓ 调用
hooks(useResourceQuery → fetcher)
  ↓ 调用
lib/ports(ChatPort/ProjectsPort 接口)
  ↓ 委托
lib/api/*.ts(领域函数)
  ↓ 调用
lib/api/client.ts(hubFetch → fetch / SSE 流)
  ↓ HTTP
后端 Hub API(/api/...)
```

**资源失效机制**：mutation（create/delete/update）调 `invalidateResources(key)` → 订阅该 key 的 `useResourceQuery` 自动 silent 重拉。`dashboard` 对 `projects/groups/agents/workflows` 四个 key 做级联失效。

### 与后端的类型契约

前端 TS 类型手写定义在各 `lib/api/*.ts` 顶部，与后端 Pydantic 模型手工对齐。后端 `backend/common/tests/test_fe_hub_route_contract.py` 校验前端 API 路径与 Hub 路由表对齐（防漂移）。

## 测试

### 运行

```bash
npm test              # 单次运行
npm run test:watch    # watch 模式
```

### 测试分层

| 层级 | 文件 | 用例数 | 覆盖内容 |
|------|------|--------|---------|
| **传输层** | `lib/api/client.test.ts` | 21 | hubFetch（成功/失败/init 透传）、isAbortError、readStreamWithAbort（正常/空/已取消）、parseSseDataLines（单事件/多事件/remainder/非data行/[DONE]）、parseSseLineBuffer |
| **资源失效总线** | `lib/dataRefresh.test.ts` | 13 | subscribe/invalidate、多订阅者、unsubscribe、错误隔离、dashboard 级联（4 个依赖 key → dashboard）、级联去重 |
| **API 领域层** | `lib/api/agents.test.ts` | 19 | listAgents/getAgentDetail/getAgentBackendConfig/saveAgentWorkspaceFile/updateAgentManage/createAgent/deleteAgent/updateAgentConfig/applyModelToAllAgents/suggestAgentId — 验证路径/method/payload/invalidate 触发 |
| **API 领域层** | `lib/api/projects.test.ts` | 15 | listProjects（title→name 映射/workflow_label→meta）、getProject（overview→detail 映射）、runProject/cancelProject/deleteProject（path/method/invalidate）、getProjectOverview/getProjectCost/getTaskDetail、projectWorkflowLabel（纯函数）、listMemory/createMemory（query 参数构建） |
| **Hook** | `hooks/useResourceQuery.test.tsx` | 8 | 初始加载、错误处理、reload()、invalidate 触发 silent 重拉（无 loading 闪烁）、不同 key 不触发、dashboard 级联不误触发、unmount 清理订阅 |

共 5 个测试文件、76 个用例。配置：vitest + jsdom + @testing-library/react。

### 测试约束

- mock `fetch`（`vi.stubGlobal`），不发起真实 HTTP 请求
- `afterEach` 自动 cleanup + restoreAllMocks + localStorage.clear
- 不依赖后端服务器运行
