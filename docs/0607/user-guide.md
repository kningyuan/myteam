# myteam 用户指南

## 概述

myteam 是一个**多智能体协作平台**。你给它一个目标（goal），它自动组队、拆解任务、串行驱动多个 AI agent 协作完成，最终交付成果。

### 为什么需要 myteam？

单个 AI 助手能做的事情有限。复杂任务需要多角色协作——调研、分析、执行、评审——myteam 自动编排这一切。

---

## 核心概念

### 项目（Project）

项目是 myteam 的基本执行单元。每个项目对应一个目标，包含一组按依赖关系排列的任务。

**生命周期**：`pending` → `in_progress` → `completed` / `failed` / `cancelled`

**为什么重要**：所有工作都在项目上下文中完成，交付物按项目组织。

### Agent

Agent 是具备特定角色的 AI 工作者。每个 agent 有自己的身份定义、技能描述和工作空间。

预置 agent 包括：

| Agent | 角色 | 擅长 |
|-------|------|------|
| main | 协调者 | 组队、拆任务、分诊决策 |
| researcher | 调研专家 | 信息收集、调研报告 |
| developer | 开发专家 | 代码工程交付 |
| product | 产品专家 | 需求分析、方案对比 |
| seo | SEO 专家 | SEO 策略、内容优化 |
| … | … | … |

每个 agent 有独立的工作空间（`business/workspaces/workspace-{agent_id}/`），包含身份定义、触发目录和交付物目录。

### 任务（Task）

任务是项目中的最小工作单元。一个任务由**一个 agent** 执行，产出一份**交付物**。

每个任务有明确的类型（task_type），决定了交付物的结构和质量门禁：

| task_type | 交付物 | 典型用途 |
|-----------|--------|---------|
| `research` | 调研报告（含背景、来源、发现、结论） | 行业调研、技术选型 |
| `strategy` | 策略文档（含分析、方案、建议） | 决策文档、方案设计 |
| `seo-plan` | SEO 方案（含关键词、技术、内容、预估） | SEO 策略规划 |
| `code-writing` | 代码项目（含工程交付物） | 功能开发 |

### DAG（任务依赖图）

任务之间可以有依赖关系。比如「调研」完成之后才能开始「策略规划」。系统自动按拓扑序执行——一个任务完成后，它的下游任务才会启动。

**为什么重要**：保证每个 agent 拿到的是完整的前置输入，不会因为缺少依赖而产出低质量结果。

### 交付物（Deliverable）

每个任务执行完毕后，agent 产出的成果物称为交付物。交付物文件保存在 `business/tasks/project/{project_id}/deliverables/{task_id}/` 下。

交付物可通过 Hub 的项目页面直接浏览和下载。

### 门禁（Gate）

每个任务完成后，系统自动执行质量门禁检查：
- 格式检查：交付物结构是否符合模板要求
- 内容检查：是否包含必需章节和关键信息
- 长度检查：是否达到最低字数要求

门禁不通过的任务会触发重试或分诊。

### 分诊（Triage）

任务失败时，main agent 会进行分诊决策：
- **retry**：重试当前任务
- **reassign**：换一个 agent 执行
- **abort**：中止项目

---

## 工作流

### 单次执行（one_shot）

一次完整的 goal → 组队 → 拆任务 → 串行执行 → 交付的流程。适合一次性的调研、分析、写作任务。

```bash
python backend/common/run_kernel.py my-project \
  --goal "调研 GEO 优化方案" \
  --mode one_shot
```

### 周期执行（recurring）

按周期重复执行，每个周期基于上一周期结果迭代。适合持续监控、周期性报告等场景。

```bash
python backend/common/run_kernel.py my-project \
  --goal "跟踪竞品动态" \
  --mode recurring \
  --max-cycles 5
```

### 断点续跑

项目因网络中断、token 耗尽等原因中断后，系统支持从中断点继续执行，已完成的任务不会重跑。

---

## 运行模式

### 命令行（CLI）

直接使用 `run_kernel.py` 执行，适合 CI/CD、脚本、远程运行：

```bash
export MYTEAM_ROOT="$PWD" PYTHON_PATH="$PWD/backend"
venv/bin/python3 backend/common/run_kernel.py my-project --goal "..."
```

### 浏览器（Hub）

启动 Web 界面查看项目和交付物：

```bash
./run.sh start
# 访问 http://localhost:8765
```

Hub 提供：
- 实时项目进度（SSE 推送）
- 任务状态和耗时
- 交付物浏览和下载
- Agent 管理
- 可观测性面板