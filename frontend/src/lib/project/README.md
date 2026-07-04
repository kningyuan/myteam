# lib/project — 项目编排视图

项目执行 / 任务 DAG 的纯派生逻辑（从后端 ProjectEvent 派生前端视图结构）。

## 核心文件

- `project-labels.ts` — 任务状态 / 类型 / 执行阶段标签与图标
- `project-exec.ts` — 任务级执行过程派生（根任务 / 子任务 / 交互分组）

## 依赖关系

依赖：`@/lib/api/projects`（类型）。
被依赖：`sections/ProjectsSection`、`sections/ExecuteSection`、`components/project/*`。

## 测试

暂无。涉及较重的 ProjectEvent 结构，后续可补 `project-exec` 的分组派生单测。
