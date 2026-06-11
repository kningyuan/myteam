# Workflow Profiles（声明式任务 DAG）

本目录定义 **可实例化的任务 DAG 种子**，供内核跳过即兴 `task_plan`，直接按组织流程跑项目。

## 当前磁盘上的 workflow（2026-06-10）

| 文件 | `id` | 场景 |
|------|------|------|
| `GitHub项目调研.yaml` | `GitHub项目调研` | 产品/架构/工程化三视角并行调研 + 汇总 |
| `GEO优化.yaml` | `GEO优化` | GEO 审计 → 改稿 → 验证 |
| `内容运营.yaml` | `内容运营` | 调研 → 内容 → 发布（通用；知乎/小红书请用专用 workflow） |
| `知乎运营.yaml` | `知乎运营` | 调研 → 成稿 → 知乎专栏发布留痕；Skill 包 `business/skills/zhihu-operations/` |
| `小红书运营.yaml` | `小红书运营` | 调研 → 成稿 → 小红书笔记发布留痕 |
| `系统研发.yaml` | `系统研发` | 需求 → 架构 → 前后端并行 → 评审 → 测试 → 部署 → 验收 |
| `方案编制.yaml` | `方案编制` | 调研 → 需求 → 策略 → 技术方案 → 定稿 → 验收 → 决策 |
| `myteam系统升级.yaml` | `myteam系统升级` | 配置盘点 → 前端接口对照 → 方案 → **前后端并行修复** → 测试 → 验收 |
| `数据分析.yaml` | `数据分析` | 需求 → 分析 → 报表 → 验收 |
| `产品独立交付.yaml` | `产品独立交付` | product 一人闭环：product-research → PRD → 策略 → PPT → 验收 → 决策 |
| `可信数据空间-产品规划完善.yaml` | `可信数据空间-产品规划完善` | 对照原 docx 提取稿：缺口分析 → 第三章定稿 → 验收 |

辅助文件：`tier-l3-free-goal.txt`（自由规划 goal 模板）。

框架已封板，**新增业务场景 = 在本目录加 yaml**，无需改内核。见 [`docs/FRAMEWORK-FREEZE.md`](../../docs/FRAMEWORK-FREEZE.md)。

## 与内核的关系

| 层 | 职责 |
|----|------|
| **本目录（Strategy）** | 阶段划分、角色 roster、task 依赖、`options`（parallel/review/split） |
| **Kernel** | `execute` + Gate + 可选 peer_review + Store |
| **Skill** | `business/skills/<场景>/SKILL.md` — 单步怎么做 |

指定 `--workflow` 或 Hub 选择工作流时：

1. `workflow_bootstrap.ensure_workflow_ready` 合并 `pgd-agents.json` 能力、自动创建 workspace
2. **跳过** `team_config` / `task_plan`
3. `plan_gate` 校验 agent 能力与 DAG 结构
4. Hub 与 CLI 均合并 workflow `options` 到 `ProcessConfig`

## 用法

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

venv/bin/python3 backend/common/run_kernel.py my-project \
  --workflow GitHub项目调研 \
  --goal "https://github.com/org/repo — 三视角调研" \
  --budget 1000000 --backend claude
```

`--goal` 注入各 task `description` 中的【项目目标】占位。

## Hub 编辑页「自动推导」

`POST /api/workflows/suggest` 调用 `workflow_suggest.py`（**确定性关键词**，无 LLM），产出草稿 DAG。保存前请人工核对与名册能力是否一致。

复杂 SOP 建议：**手写 yaml + Skill**，或运行时走自由规划（`task_plan` LLM）。

## 新增 workflow（使用层标准步骤）

1. 复制现有 yaml，改 `id` / `description` / `roster` / `tasks`
2. 新 `task_type` 须先写入 `business/templates/templates.yaml`
3. 配套 `business/skills/<场景>/SKILL.md`（推荐）
4. 校验：`PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_workflow_loader.py -q`
5. 可选：在 `scripts/regression/` 加发版门禁脚本

### description 写法（只写变量）

```text
【对象】具体调研对象（链接见【项目目标】）
【视角】本步视角
【范围】README/docs only
【输入】只读 t-xxx 交付物
```

格式条款、交卷步骤在 `prompt_templates.yaml`，勿在 description 重复。

## options 字段

| 字段 | 含义 |
|------|------|
| `parallel_enabled` | 同波次无依赖任务真并行 |
| `max_parallel` | 单波次并发上限 |
| `review_enabled` | 完成后同行评审 |
| `split_enabled` | 派发前 `evaluate` 拆分子任务 |
| `skill_extract_enabled` | 项目完成后 skill 草案（scaffold） |
