# Workflow Profiles（PGD 阶段闸门工作流）

本目录定义 **Phase-Gated Deliberation（PGD）** 通用项目执行模式：章程 → 需求会诊 → 方案会诊 → 交付 → 验收。每个 profile 是一份 **可实例化的任务 DAG 种子**，供内核跳过即兴 `task_plan`，直接按组织流程跑项目。

## 模式说明

| 概念 | 含义 |
|------|------|
| **阶段（phase）** | 需求 / 方案 / 交付 / 验收；阶段内 task 全部 `completed` 且决策记录通过 Gate，视为阶段锁定 |
| **会诊** | 多角色对同一上游 artifact 并行产出评审（`architecture-review` / `test-plan` 等） |
| **仲裁** | `main` 产出 `decision-record`：采纳表 + 阻塞项（🔴）必须清零 |
| **一致** | 非「全员点赞」，而是 **必选角色已评审 + 无开放 🔴 + 定稿 artifact 存在** |

## 目录

| 文件 | 适用场景 |
|------|----------|
| `software-delivery.yaml` | 软件功能/平台改造（含 myteam 自升级） |
| `content-campaign.yaml` | 内容/SEO/营销战役（无代码部署链） |
| `hotfix.yaml` | 紧急修复（压缩版软件交付） |

## 角色 roster（自动准备）

指定 `--workflow` 或 Hub 选择工作流时，内核会调用 `workflow_bootstrap.ensure_workflow_ready`：

1. 从 `business/templates/pgd-agents.json` 合并各角色 `task_types` 到 `agents_registry.json`
2. 自动创建缺失的 workspace（`auto_create_agent`）
3. 运行时 `plan_gate` 能力边界校验

**无需手工配 registry**；首次跑 PGD 项目即可自动就绪。

| Profile | roster |
|---------|--------|
| software-delivery | main, product, arch, frontend, qa |
| content-campaign | main, product, research, content |
| hotfix | main, product, arch, qa |

### 推荐 task_types 映射（software-delivery）

| agent | task_types |
|-------|------------|
| main | strategy, decision-record, code-deployment |
| product | strategy, research, requirements, acceptance-report |
| arch | system-design, architecture-review, code-writing, code-review |
| frontend | system-design, architecture-review, code-writing |
| qa | test-plan, architecture-review, code-review, code-testing |

### 推荐 task_types 映射（content-campaign）

| agent | task_types |
|-------|------------|
| main | strategy, decision-record |
| product | strategy, research, architecture-review, acceptance-report |
| research | research, architecture-review |
| content | content, architecture-review, publish-post |

## 用法

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

# 软件交付（默认开启同行评审）
venv/bin/python3 backend/common/run_kernel.py myteam-upgrade-0608 \
  --workflow software-delivery \
  --goal "修复多Agent并发、DAG时间线、Token计量；全角色对齐后合入" \
  --review \
  --budget 300000

# 内容战役
venv/bin/python3 backend/common/run_kernel.py seo-q3-campaign \
  --workflow content-campaign \
  --goal "Q3 GEO 内容集群：调研→策略→10篇内容→发布验收" \
  --budget 150000
```

指定 `--workflow` 时：**跳过** `team_config` / `task_plan`，直接使用 profile 中的 roster 与 task DAG。`--goal` 会注入各 task 的 `description` 前缀。

## 与内核的关系

- **Strategy 层（本目录）**：阶段划分、角色、task 依赖、交付 `task_type`
- **System 层（kernel）**：`execute` + 确定性 Gate + 可选 `peer_review` + Store 真相
- **扩展**：二期可在内核增加 `deliberate` 原语，将「并行评审→仲裁」收成一轮 API；当前用显式 DAG 节点表达

## 新增 workflow

1. 复制现有 yaml，改 `id` / `roster` / `tasks`
2. 优先复用 `requirements`、`decision-record`、`architecture-review`、`system-design`、`acceptance-report`
3. 新 `task_type` 须先写入 `business/templates/templates.yaml`
4. 本地校验：`PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_workflow_loader.py -q`
