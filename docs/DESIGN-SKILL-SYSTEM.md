# myteam Agent Skill 体系与自我升级机制

> **版本**：2026-06-10  
> **状态**：权威设计（执行指南）  
> **目标**：提升 Agent **任务执行质量**；建立可审计、可回归的 **自我升级** 闭环  
> **原则**：Kernel 冻结；Skill / ledger / catalog 在 Business 层演进；Workflow 不写死 Skill 路径

**关联文档**

| 文档 | 作用 |
|------|------|
| [DESIGN-AGENT-DELIVERY.md](./DESIGN-AGENT-DELIVERY.md) | A/B 层边界、ALL playbook |
| [DESIGN-DELIVERY-TEMPLATES.md](./DESIGN-DELIVERY-TEMPLATES.md) | task_type vs template_id、Gate vs Review |
| [WORKFLOW_TASK_TYPE_MATRIX.md](./WORKFLOW_TASK_TYPE_MATRIX.md) | workflow × task_type 覆盖 |
| [EXPERIENCE_LEDGER_RUNBOOK.md](./EXPERIENCE_LEDGER_RUNBOOK.md) | ledger → KB 操作 |
| [FRAMEWORK-FREEZE.md](./FRAMEWORK-FREEZE.md) | 不可改动的内核 |
| [business/skills/README.md](../business/skills/README.md) | Skill 作者规范 |

---

## 0. 一句话定义

**Skill 体系** = 让 Agent 在每次 `execute` 时知道「怎么做好这类任务」；**自我升级** = 把一次运行的过程证据（ledger / verify / 交付物）沉淀为「下次更好」的可复用知识，且 **不自动污染生产 Skill**。

```text
Workflow(DAG) → execute → [Prompt 壳 + Skill Router + Means + Ledger hints] → 交付物
                                    ↓ 成功后
                         ledger → KB → 下次 hints
                         completed → skill draft (L3) → 人工合并 → catalog
```

---

## 1. 设计目标与验收

| 维度 | 达成标准 | 不承诺 |
|------|----------|--------|
| **执行质量** | 每条主 workflow 的 task 行有 task_type +（推荐）Skill +（可选）delivery_template；Gate/Review FAIL 率可定位到 Skill/Means 缺口 | LLM 零失误 |
| **可复用** | 同 task_type 第二次 RUN 可观测 **experience hints** 注入；ledger 非 stub | 跨 task_type 自动泛化 |
| **可升级** | 项目 completed 可生成 `auto-*` Skill 草案；人工审核后合入 `catalog.yaml` | Agent 自主改生产 SKILL.md |
| **可回归** | 每条 workflow LIVE REG 绿 → 对应 Skill 版本 tag + REG 记录 | 无人值守无限自进化 |

**总验收句**：主 workflow REG LIVE 3/3 + Matrix 100% 覆盖 + 至少 1 条 task_type 证明「第二次 RUN hints 生效」。

---

## 2. 架构：三层 + 两环

### 2.1 三层职责（与 Kernel 边界）

```text
┌─────────────────────────────────────────────────────────────────┐
│ A · Kernel（冻结）                                               │
│   Process · TaskPipeline · Gate · AgentPort · Store              │
│   职责：何时跑、重试几次、Gate 客观校验、状态机                    │
├─────────────────────────────────────────────────────────────────┤
│ A · 策略注册表（配置，非 Skill）                                  │
│   templates.yaml · delivery_templates/*.yaml · prompt_templates  │
│   delivery_profiles.yaml · prompt_injections.yaml                │
│   职责：章节结构、Gate 规则、execute 壳文案、过程套餐               │
├─────────────────────────────────────────────────────────────────┤
│ B · Agent Skill 体系（本文）                                      │
│   skills/<task_type>/SKILL.md  · catalog.yaml  · means/          │
│   playbooks/ALL.md  · experience/ledger  · workspaces/           │
│   职责：怎么做、用什么脚本、踩坑记录、身份约束                      │
└─────────────────────────────────────────────────────────────────┘
```

**硬边界**（违反则不是 Skill）：

- Skill **不得**定义 DAG、重试策略、Interaction 契约、Gate 实现
- Skill **不得**写「改 state.db / 跳过 Gate」
- Workflow YAML **不得**写 `【Skill】` 或硬编码 `business/skills/...` 路径（自选写在 `plan.md`）

### 2.2 质量两环

| 环 | 机制 | 判什么 | 谁负责 |
|----|------|--------|--------|
| **客观环** | Gate + delivery_profile 过程校验 | 章节齐、文件在、verify.log 有记录、非 stub | Kernel（确定性） |
| **主观环** | Agent 自评 + peer_review | 论述是否合理、能否交付 | Agent（Skill 教它怎么自评/评审） |

Skill 的职责：让 Agent **一次做对客观环**，并 **诚实暴露** 主观环缺口（`known_gaps`、Review FAIL 标记）。

---

## 3. Skill Pack 标准结构

每个 **task_type**（或 workflow 共享包）对应一个 Skill Pack，推荐目录：

```text
business/skills/<pack-id>/
  SKILL.md              # Router：必读入口（内核按 task_type 注入路径）
  scripts/              # 探针、构建、verify（可执行、可 REG）
  checklists/           # 发布前/交卷前清单（人类+Agent 可读）
  templates/            # 交付物/过程文件模板
  references/           # 长文档、平台说明（可选）
```

**Means**（重工具）可放在 `business/means/<name>/`，由 `catalog.yaml` 的 `means_root` 引用（如 `diagram-build`）。

### 3.1 SKILL.md 必备章节

| 章节 | 内容 | 质量作用 |
|------|------|----------|
| **Frontmatter** | `name`, `task_type`, `description`, 可选 `workflows`, `agents` | Hub / 检索 / 文档化 |
| **先读** | 共享包链接（如 product-operations、xhs-operations） | 避免重复、统一红线 |
| **输入材料** | 必读文件表（路径 + 用途） | 减少漏读上游 |
| **执行步骤** | 编号步骤，对齐 ALL（align → 执行 → verify → 交卷） | 可执行、可审计 |
| **必跑脚本** | 命令 + 期望 exit code | 可 REG、可复现 |
| **红线** | 禁止行为（占位、改 docx、矛盾原稿） | Review/Gate 前置约束 |
| **PATCH 改稿**（可选） | Work–Review 循环下的定点修改规则 | discuss 链质量 |

示例（生产级）：`business/skills/product-planning/SKILL.md`、`business/skills/xhs-operations/SKILL.md`。

### 3.2 Skill 来源与采纳策略

**Skill 不必全部从零自研。** 优先从外部成熟实践取材，再按 myteam 边界决定是直接用、改后用，还是自己做。

#### 3.2.1 常见来源

| 来源 | 示例 | 适用 |
|------|------|------|
| **工具官网 / 官方文档** | CLI/API 用法、最佳实践、限制说明 | means 脚本、publish-post、diagram-build |
| **GitHub 开源仓库** | Agent skill 库、prompt 模板、自动化脚本 | 新 task_type 冷启动、探针/verify 参考 |
| **社区 Skill / Agent 库** | Cursor Skills、agency-agents 等 | 人格/步骤/清单的**素材**，非原样运行 |
| **一次成功 RUN 抽提** | `auto-*` 草案、ledger | L3 候选，仍须 L4 人工合入 |

已有先例：`business/agent-catalog/` 对外部 agent 人格做 **只读 vendor**（见该目录 README）；Skill Pack 可同样把上游放在 `references/`，myteam 差异写在 `SKILL.md`。

#### 3.2.2 三条路径（必选其一）

| 路径 | 何时选 | 产出形态 | 注意 |
|------|--------|----------|------|
| **直接采纳** | 上游步骤/脚本与 myteam Gate、ALL、license 完全兼容 | 原样放入 `scripts/` 或 `references/`，SKILL.md 指向即可 | 记录 URL、版本、许可；REG 须绿 |
| **改造采纳** | 有可用骨架，但 task_type 章节、证据格式、红线与 myteam 不一致 | 上游进 `references/`，**改写**执行步骤与脚本适配 templates.yaml | **不回写**上游；裁掉越界能力（同 agent-catalog 激活规则） |
| **自我实现** | 无合适外部源、许可冲突、或需深度耦合 myteam 配置贯通 | 完整 Skill Pack + means | 仍可在 `references/` 留「灵感来源」链接 |

```text
发现外部 Skill / 文档 / 仓库
        ↓
  许可与红线可接受？
   否 → 自我实现（或放弃）
   是 ↓
  与 task_type Gate + delivery_profile 对齐？
   是 → 直接采纳（+ references/UPSTREAM.md）
   否 → 改造采纳（列差异表 → 改 SKILL/scripts → REG）
        ↓
  L4：decision-record 写明来源 URL + 采纳路径 + 改动摘要
```

#### 3.2.3 溯源与 frontmatter（推荐）

在 `SKILL.md` frontmatter 或 `references/UPSTREAM.md` 记录：

```yaml
# SKILL.md 可选字段
upstream:
  - url: https://github.com/org/repo/path
    rev: v1.2.0          # tag / commit / 访问日期
    license: MIT
    adoption: adapted    # direct | adapted | self
    notes: 裁掉 GTM 章节；verify 改为 myteam pytest 命令
```

**禁止**：未审阅许可即复制进生产 `SKILL.md`；把外部人格/步骤原样覆盖 myteam 角色边界或 Gate 规则。

### 3.3 catalog.yaml 条目

```yaml
- id: diagram-build
  task_types: [diagram-build]
  description: brief → draw.io → PNG
  router: business/skills/diagram-build/SKILL.md
  means_root: business/means/diagram-build
  execution: business/means/diagram-build/EXECUTION.md
  probe: business/means/diagram-build/scripts/probe.sh
  verify: business/means/diagram-build/scripts/verify_diagram.py
  means:
    - id: brief_to_drawio
      script: business/means/diagram-build/scripts/brief_to_drawio.py
  deliverables: [diagram.drawio, diagram.png]
```

**规则**：

- 一个 `task_type` 在 catalog 中 **至少一条** router（或文档标注「registry 直驱」）
- 多 Agent 共用 task_type 时，用 **共享包**（如 `product-operations`）+ 各 task_type 薄 router
- `publish-post` 按平台拆 router（`xhs-operations` / `zhihu-operations`），由 Agent 名册 + workflow 决定谁跑哪条

### 3.4 delivery_profile 与 Skill 的配合

| profile | 过程产物 | Skill 侧要求 |
|---------|----------|--------------|
| `none` | 无 | 仅 deliverable；适合 research 等轻量 |
| `light_v1` | align.md + verify.log | SKILL 写清 align 四节 + verify 记录格式 |
| `all_v1` | align + plan + verify + ledger + trace | SKILL 写清 catalog 自选、means 探针、ledger 填写 |

绑定在 `templates.yaml` 的 `delivery_profile` 字段（**按 task_type，不按 agent**）。

内核行为（已实现）：

- attempt 1：`scaffold_process_artifacts` 复制模板
- execute prompt：`PromptComposer` + `prompt_injections.yaml` + Skill 路径 + `append_experience_hints`
- Gate：`check_process_artifacts` 校验过程文件非 stub
- 成功：`promote_ledger_to_memory`

---

## 4. 执行时 Skill 如何进入 Agent

```text
render_execute_intent(task)          # templates.yaml + task.description
  + build_worker_prompt()            # 章节/Gate 摘要/submit 命令
  + prompt_injections.yaml           # delivery_profile / task_type 块
  + 【任务类型执行指引】SKILL.md 路径   # agent_transport._task_type_skill_path
  + append_experience_hints()        # KB 中 ledger 摘要
  + retry_feedback（若 Gate 失败）     # 上一轮 rule/expected/actual
```

代码锚点：

- `backend/common/agent_transport.py` — Skill 路径与 hints
- `backend/common/prompt_injections.py` — 可配置注入
- `backend/common/experience.py` — ledger 检索
- `backend/common/task_pipeline.py` — Gate 重试与 feedback

**Agent 侧动作链**（Skill 必须写清楚）：

1. 读 SKILL.md（及共享包）
2. 填 align.md（若 profile 要求）
3. 执行 means / 写 deliverable
4. 写 verify.log（探针 exit code）
5. 填 ledger.entry.yaml（lesson）
6. `submit_result.py` 交卷

---

## 5. 经验层（L1 进化 · 已实现）

### 5.1 ledger  Schema

`business/experience/schema/ledger.entry.yaml`：

```yaml
task_id: t-deck
task_type: deck-build
lesson:
  worked: 先列 slide 大纲再填内容
  failed: wps 未启动时 build 会 hang
  next_time: 先跑 check_wps_ready.sh
chosen:
  skills: [deck-build]
  means: [wps_deck]
probes:
  - command: bash business/skills/wps-deck/scripts/check_wps_ready.sh
    exit_code: 0
```

### 5.2 沉淀与注入

| 阶段 | 动作 | 模块 |
|------|------|------|
| 任务成功 | 读 `ledger.entry.yaml`，非 stub 则 `kb.write(tags=[task_type, ledger])` | `promote_ledger_to_memory` |
| 下次 execute | 检索同 project 再跨 project，追加「同类任务经验」块 | `append_experience_hints` |

**人工边界**（产品决策）：ledger **不自动改** SKILL.md；只作 prompt 短提示。

### 5.3 运营节奏（Q-2）

每完成一条 **workflow LIVE REG**：

1. 检查失败任务的 ledger / verify.log / gate_failed
2. 更新对应 `SKILL.md` 一节（步骤、红线、脚本）
3. 写 1 条真实 ledger 样例到 `business/experience/examples/`（可选）
4. 重跑 REG 3×

---

## 6. 自我升级机制（L0–L4）

分级定义：**自动化程度递增，生产写入权限递减**。

| 级别 | 名称 | 触发 | 产出 | 是否进生产 |
|------|------|------|------|------------|
| **L0** | 运行态 | 每次 execute | retry_feedback、verify.log | 仅当次任务 |
| **L1** | 经验提示 | 任务 success + ledger | KB hints | 是（prompt 注入） |
| **L2** | Skill 人工修订 | REG 后人工 | 更新 SKILL.md / scripts | 是（需 PR） |
| **L3** | 草案抽提 | 项目 `completed` | `skills/auto-<project>-<task>/SKILL.md` | **否**（草案） |
| **L4** | 审核合入 | 人工 + REG | catalog 新版本、tag | 是（显式发布） |

### 6.1 L3 自动抽提（已实现）

- 模块：`backend/common/skill_extract.py`
- 触发：`Process._maybe_extract_skills`（`skill_extract_enabled` 为 true 时）
- 候选：`skill-extract` 任务 completed，或 `research` 类 completed 任务
- 产出：交付物前 500 字 + 元数据 → `auto-*/SKILL.md`

**禁止**：草案自动替换 `business/skills/<task_type>/SKILL.md` 或自动改 catalog。

### 6.2 L4 合入流程（推荐 SOP）

```text
1. Hub / 文件系统发现 auto-* 草案（或外部仓库候选）
2. 负责人 diff 草案 vs 现行 SKILL.md；若来自外部，先核对 license 与 §3.2 采纳路径
3. 提取可合并段落 → 编辑正式 SKILL.md + scripts（改造采纳时保留 references/UPSTREAM.md）
4. 更新 catalog.yaml description / means（若需要）
5. pytest + REG CHECK_ONLY + 目标 workflow LIVE 1 次
6. git commit；可选打 skill-<pack-id>@YYYYMMDD
7. 删除或归档 auto-* 目录
```

### 6.3 self-upgrade Workflow（规划中）

`reg_l3_self_upgrade.py` 定义的 **self-upgrade** workflow（plan → execute → review → skill-extract）用于验证 **整条升级链**，尚未作为日常默认路径。建议任务编排：

```yaml
# business/workflows/self-upgrade.yaml（目标形态）
id: self-upgrade
tasks:
  - id: t-req
    task_type: requirements
    agent: product
  - id: t-arch
    task_type: architecture-review
    agent: arch
    dependencies: [t-req]
  - id: t-code
    task_type: code-writing
    agent: developer
    dependencies: [t-arch]
  - id: t-skill-extract
    task_type: skill-extract   # 或 research + 专用 template
    agent: arch
    dependencies: [t-code]
```

用途：**团队改 Skill 体系本身**时的 meta-project，不是业务交付默认 workflow。

---

## 7. task_type 覆盖策略

### 7.1 三类 task_type

| 类型 | 说明 | Skill 策略 | 示例 |
|------|------|------------|------|
| **Skill 驱动** | 有独立 router + 可选 means | 完整 Skill Pack + REG | product-planning, diagram-build, publish-post |
| **共享包驱动** | 多 type 共用 product-operations | 薄 router + 共享 SKILL | requirements, strategy, acceptance-report |
| **Registry 直驱** | 仅 templates.yaml Gate | catalog 标注直驱；prompt_injections 补块 | geo-*, data-analysis |

矩阵维护：`docs/WORKFLOW_TASK_TYPE_MATRIX.md` ↔ `business/skills/catalog.yaml`。

### 7.2 新建 task_type 检查清单

0. **评估外部来源**：检索目标工具官网 / GitHub / 社区 Skill；在 requirements 或 decision-record 中写明 **直接采纳 / 改造采纳 / 自我实现** 及 URL（见 §3.2）
1. 在 `business/templates/templates.yaml` 注册（`outcome_kind`, `delivery_profile`, Gate）
2. 创建 `business/skills/<task_type>/SKILL.md`
3. 在 `catalog.yaml` 增加条目
4. 在 `prompt_injections.yaml` 增加 execute 块（若需要）
5. 更新 Matrix；workflow 中引用该 task_type
6. 增加 pytest（Gate）+ REG 脚本或扩展现有 REG

### 7.3 Agent 与 task_type 关系

- **一个业务方向一个 Agent**（product, arch, research…）
- **差异用 task_type**，不用同一 task_type 绑多个 Agent 角色
- Agent 可执行任务列表：`agents_registry.json` 的 `task_types`；workflow 编辑器按此过滤

---

## 8. 质量度量与 Hub 可观测

### 8.1 任务级指标（Hub 2.0 已接）

| 指标 | 来源 | 用途 |
|------|------|------|
| Gate 失败明细 | run_event `gate_failed` | 改 Skill 步骤/模板 |
| fail_reason / fail_detail | task.meta | 端口/超时/门禁耗尽 |
| quality.score / known_gaps | response_snapshot | 主观环 |
| review passed/feedback | run_event `review_done` | Review Skill |
| verify.log | deliverables | 过程证据 |

API：`GET /api/obs/projects/{pid}/tasks/{tid}`

### 8.2 Skill 健康 KPI（建议纳入 REG 汇总）

| KPI | 计算 |
|-----|------|
| `gate_fail_rate` | gate_failed 次数 / execute 次数（按 task_type） |
| `gate_exhausted_rate` | fail_reason=gate_exhausted 任务数 |
| `needs_review_rate` | needs_review / 完成数 |
| `experience_hints_applied` | prompt 含「同类任务经验」次数 |
| `ledger_promoted_count` | promote 成功数 |
| `skill_drafts_pending` | `auto-*` 目录数 |

---

## 9. Skill 版本与发布

### 9.1 版本规则

- **生产 Skill**：随 git 版本；重大变更在 SKILL.md frontmatter 增加 `skill_version: "1.2"`
- **Means 脚本**：破坏性变更需 bump 并更新 verify 脚本期望
- **catalog.yaml**：`version: "0.2"` 全局；条目级可选 `since:` / `deprecated:`

### 9.2 发布门禁

```bash
# Skill 变更最低门禁
venv/bin/python3 -m pytest backend/common/tests/test_gate.py backend/common/tests/test_experience.py -q
REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1
# 变更涉及的 workflow 跑 LIVE 1 次
```

---

## 10. 反模式（禁止）

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| Workflow 写死 Skill 路径 | 无法自选 means、难升级 | 写 task_type；Skill 在 catalog |
| 把 Gate 规则写进 Skill 当唯一真相 | 与 templates 分叉 | Gate 以 templates/template_id 为准 |
| Agent 自动 commit SKILL.md | 不可控质量 | L3 草案 + 人工 L4 |
| 空 ledger / 模板 ledger | hints 噪声 | is_stub 过滤 + 实质 lesson |
| 跳过 verify.log | 过程不可审计 | delivery_profile 强制 |
| 用 JSON 编辑 workflow 代替表单 | 人无法维护 | Hub 表单编辑器 |

---

## 11. 实施路线图

### Phase S0 — 覆盖审计（1 周）

- [x] Matrix 审计脚本 `scripts/audit_skill_matrix.py`
- [x] 每条主 workflow REG CHECK_ONLY 绿
- [x] Hub 任务质量卡片 + gate_failed 结构化

### Phase S1 — LIVE 证明 + Skill 迭代（2 周）

- [ ] `reg_discuss_loop` + `reg_p2_pm_pack` LIVE 3×
- [x] ledger 样例 `business/experience/examples/`
- [x] section-review / research Skill 增补

### Phase S2 — 升级链产品化（2–3 周）

- [x] 落地 `self-upgrade.yaml` workflow
- [x] Hub `/v2/skills` 草案列表 + diff 对照
- [ ] REG KPI 输出 `skill_drafts_pending` / `experience_hints_applied`

### Phase S3 — Means 与共享包整理（持续）

- [ ] `wps-deck` 等迁 means 规范；catalog means_root 统一
- [ ] `product-operations` 与各薄 router 分工文档化
- [ ] 平台 Skill（xhs/zhihu）登录脚本纳入 PRODUCTION_BASELINE

---

## 12. 附录 A — Prompt 注入配置示例

`business/templates/prompt_injections.yaml`（片段）：

```yaml
injections:
  execute:
    by_task_type:
      section-review:
        blocks:
          - |
            【评审重心】合理性 > 准确性 > 完整性；禁止以字数放行
            【PASS/FAIL】须写 REVIEW: PASS 或 REVIEW: FAIL
```

新增 task_type 指引：**只改 yaml**，不改 `agent_transport.py`。

---

## 13. 附录 B — ledger 最小可用示例

```yaml
task_id: t-publish
task_type: publish-post
lesson:
  worked: 先 check_xhs_login.sh 再发文
  failed: 未导出 cookie 导致发布页跳转登录
  next_time: login_xhs.sh 后立刻 verify_publish_deliverable.py
chosen:
  skills: [xhs-operations]
  means: []
outcome:
  status: success
  deliverables: [t-publish_deliverable.md, publish_screenshot.png]
```

---

## 14. 附录 C — 代码与路径索引

| 能力 | 路径 |
|------|------|
| Skill router 注入 | `backend/common/agent_transport.py` |
| Experience hints | `backend/common/experience.py` |
| Skill 草案 | `backend/common/skill_extract.py` |
| 过程 scaffold | `backend/common/deliverable_guarantee.py` |
| Prompt 注入 | `backend/common/prompt_injections.py` |
| Catalog | `business/skills/catalog.yaml` |
| ALL Playbook | `business/playbooks/ALL.md` |
| Ledger schema | `business/experience/schema/ledger.entry.yaml` |
| L3 REG | `scripts/regression/reg_l3_skill_extract.py` |
| Self-upgrade REG | `scripts/regression/reg_l3_self_upgrade.py` |

---

**维护者**：每次主 workflow LIVE REG 通过后，同步更新本文 Phase  checklist 与 Matrix。
