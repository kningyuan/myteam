---
name: Workflow 设计
description: 设计期方法论：读懂 Goal 与角色后产出可校验的 workflow YAML，确保 loop 切分、重试与交付模板对齐。
---
# workflow-design — 为项目设计 Workflow

> **你是蓝图作者，不是执行者。**  
> 产出：`business/workflows/<id>.yaml`（+ 必要时新建 `delivery_templates/`、`business/inputs/<bundle>/`）。  
> **禁止**在 YAML 里写 `skills:`、禁止写「Read xxx/SKILL.md」。

**与 `coordination-methodology` 的分工**：本 skill 用于 **跑起来之前** 定 DAG；项目运行中的多 agent 编排用 coordination。

---

## 何时启用

- 用户要「设计 / 新建 / 改版 workflow」
- 新项目选 workflow 前，现有 YAML 与 Goal 明显不匹配
- 评审 workflow：FAIL 范围过大、Hub 无法按步 pause/retry

---

## 核心原则（先记住再动手）

| 层 | 放什么 | 不放什么 |
|----|--------|----------|
| **Workflow YAML** | step id、agent、`task_type`、dependencies、`template_id`、四段 description | 章节 bullet 全文、python 命令、skill 列表、业务 verify 硬规则 |
| **项目 Goal** | 最终 Done、读者、成功标准（启动时注入各步 description 前缀） | 逐步操作说明 |
| **business/inputs/** | 只读材料：术语、参考稿、模版 docx、**可选** outline | step 列表、loop 规则 |
| **delivery_template** | L1 结构门：文件在不在、壳齐不齐 | 内容好不好 |
| **Agent skills** | 方法论 + 工具（管理页挂载） | workflow 不管 |

**Loop 单元** = 一步可独立验收的交付承诺（Done + 主交付物 + ≤3 个输入 + 可单步 retry）。

---

## Step 0 — 项目勘察（必做，先于 YAML）

向用户确认或自行读取以下内容，填 `intake-template.md`（可复制到回复）：

### 0.1 交付物与 Done

```text
【项目 Done】<最终 artifact，含路径/格式>
【读者/用途】<谁用、干什么>
【Out of scope】<明确不做>
【成功标准】<如：step-review 末行 REVIEW: PASS + deliverables/xxx.docx>
```

### 0.2 盘点现有资产

| 查什么 | 路径 / 命令 |
|--------|-------------|
| 已有 workflow 可参考 | `business/workflows/*.yaml` |
| 项目输入包 | `business/inputs/<bundle>/`（无则规划新建） |
| 交付模版 | `business/delivery_templates/*.yaml` |
| 合法 task_type | `business/templates/templates.yaml` 顶层 key |
| 可用 agent | `business/templates/pgd-agents.json` + 用户是否已建 workspace |

勘察命令（在 `myteam/` 根目录）：

```bash
PYTHONPATH=backend venv/bin/python3 -c "
from common.workflow_loader import list_workflows
from common.task_type_store import list_task_types_for_api
print('workflows:', list_workflows())
print('task_types:', sorted(t['task_type'] for t in list_task_types_for_api()))
"
```

### 0.3 选 Archetype

| 项目形态 | Pattern | 典型 step 链 |
|----------|---------|--------------|
| 单一交付物多轮打磨 | `patterns/work-review-round.yaml` | work → review |
| 文档：图 + 多章 + 合并 + 评审 | `patterns/doc-plan-static.yaml` | deck → ch* → merge → review |
| 研发：设计 → 实现 → 测 → 评 | 自研（参考 registry 中 code-* / system-design） | 按域拆 |
| 与上都不像 | 自研 | 仍遵守 Loop 六条 |

**默认**：`split_enabled: false`，章节/子任务 **写进 YAML**，不靠运行时 evaluate 拆。

### 0.4 角色与 task_type 对齐

每一步：`agent` 必须在 roster 存在，且该 agent 的 `task_types`（registry）**包含**本步 `task_type`。

常用映射（task_type 在内核；执行方法论在 agent 挂载的 `*-methodology`）：

| task_type | 典型 agent | 备注 |
|-----------|------------|------|
| `deck-build` | product | 图 / pptx |
| `section-authoring` | product | 章节 md、方案正文 |
| `section-review` | main | 轮末评审；末行 `REVIEW: PASS` / `FAIL` |
| `system-design` / `architecture-review` | arch | |
| `code-writing` / `code-deliverable` | developer, frontend | |
| `code-review` / `code-testing` | qa, arch | |
| `research` / `requirements` / `strategy` | product | |

评审步：`task_type` 固定用内核已注册的 `section-review`；main 宜挂载 `quality-review`（探针式评审）+ `coordination-methodology`。

---

## Step 1 — 拆 Loop 单元卡

每个 step 一张卡（≥5/6 条 Loop 六条才进 YAML，见 `checklist.md`）：

| 字段 | 说明 |
|------|------|
| `id` | 稳定 id：`step-deck`、`ch3`、`step-merge`、`step-review` |
| **Done** | 一句话 |
| **主交付物** | `deliverables/` 下固定文件名 |
| **输入** | 上游 step 或 `business/inputs/<bundle>/…` |
| `agent` / `task_type` / `template_id` | 与 0.4 一致 |

**章节从哪来**：在 **YAML 里静态列出** ch1…chN（id、name、dependencies）。  
**每章写什么**：写在 step 的【质量】或可选 `inputs/<bundle>/outline.md`；**不要**单独维护与 YAML 重复的「章节大纲」除非用户已有且愿同步。

---

## 同 Agent 多步：会不会浪费 Token？

**会。** 当前内核里，每一步是一次独立 `execute` 交互：

| 机制 | 实际行为 |
|------|----------|
| 会话 | **每步新 CLI session**；仅**同一步**门禁重试才复用 session |
| 上下文 | 下游只注入**直接依赖**的 `summary` + `ref` 路径，**不**注入上游全文 |
| Workspace | 每步独立 `_parallel/{project}/{task_id}` cwd（并行安全） |
| Prompt | 每步重载 rules、skill 指引、本步 description |

因此 product 连跑 ch1→ch8 = 8 次冷启动，这是用 **Hub 可 pause/retry 粒度** 换 **token 经济性** 的刻意取舍。

### 设计时怎么权衡（不必二选一）

**仍拆成多步**（适合：章节差异大、常单章 FAIL、要按章改稿）：

1. **首步沉淀 brief**：`step-brief` 产出 `deliverables/project-brief.md`（术语、读者、约束）；后续章【输入】只写 brief + 上一章 md + 图，**勿每章重复 Goal 全文**  
2. **描述递减**：ch1 写全【输入】；ch2+ 只写「读 outline→chN + 依赖 ch(N-1)」，不复制模版路径  
3. **依赖链最短**：章与章 `dependencies` 串行即可；不必每章依赖 step-deck（除非该章真要用图）  
4. **交付物即记忆**：agent 读 `deliverables/*.md`，不靠对话历史；内核已按此设计  

**合并为少步**（适合：同质写作、很少单章失败、更在意预算）：

| 策略 | 粒度 | 代价 |
|------|------|------|
| 按批 `ch-batch-1`（1–4 章） | 中 | 一批 FAIL 整批重写 |
| 单步 `all-sections` + 内部清单 | 粗 | 失去按章 pause/retry |
| 外粗内细：1 步写全部 md，merge 单独一步 | 中 | 写作步失败成本高 |

**经验法则**：  
- 需要 **按章改稿 / 按章验收** → 多步值得  
- 只是 **同一 agent 连写相似段落** 且很少失败 → 考虑 2–3 个 batch 步  
- **review 步** 保持独立（不同 agent、不同 task_type），不要并入写作步  

### 内核侧（已知方向，workflow 先按现状设计）

- 同 agent、同轮、有依赖的串行步 **链式 session**（未默认开启）  
- 项目级 `PROJECT_CONTEXT.md` 由内核维护、后续步只追加 delta  

设计 workflow 时按**上表**选粒度；不要为「看起来专业」拆出 10+ 同质冷启动步。

**与另一 agent 碰撞后的分层共识**（详见 `docs/context-propagation.md`）：

- **设计期主杠杆**：`step-brief`、描述递减、按需 batch（不增内核、不每章插 dec）
- **`decision-record` 步**：仅用于 **异质 handoff**（如图→首章、全章→merge），**不要** ch1→ch2 同质章间逐步插入
- **交付物格式**：work 步宜含 `## 决策` 段（方案 A），与 B 可并用
- **内核 backlog**：链式 session / 增强 upstream — workflow 文档可写方向，SKILL 不写「已实现」

```text
下一步与上一步同质？（如 ch2 接 ch1）
  ├─ 是 → 依赖链 + 上章 deliverable + 描述递减
  └─ 否 → 轻量：## 决策 段；重量：插入 decision-record
冷启动 > 预算？ → batch / brief，而不是逐步加 dec
```

## Step 2 — 写 YAML

1. 复制 `patterns/` 最接近的 archetype → `business/workflows/<workflow-id>.yaml`  
2. `id` 与文件名 stem 一致；`version` 从 `1.0` 起，改版递增  
3. 顶层 `tasks` 仅 **loop 锚点**（通常 `task-1` + `loop: <loop_id>`）  
4. `loops[].bodies.default` 放全部执行步  
5. `options`：`review_enabled: false`；loop 内显式 review 步；`split_enabled: false`（默认）

### description 四段（逐步必填）

```text
【范围】做什么 / 不做什么
【输入】上游 step 或 business/inputs/<bundle>/文件
【交付】deliverables/… 固定路径
【质量】Done 的可执行表述（给评审读，非 grep 硬规则）
```

### YAML 红线

| 允许 | 禁止 |
|------|------|
| agent + task_type + dependencies + template_id | skills、强制 Read SKILL |
| `REVIEW: PASS` / `FAIL` transition | description 写「必须含 XX 组件」类 verify |
| 静态 ch1…chN | 一大步 + `split_enabled: true` 代替设计 |

### Loop transition（评审收口）

```yaml
transition:
  - when: deliverable_marker
    task: step-review
    marker: "REVIEW: PASS"
    action: exit
    outcome: complete
  - when: deliverable_marker
    task: step-review
    marker: "REVIEW: FAIL"
    action: continue
    next_body: default
  - when: exhausted
    action: exit
    outcome: needs_review
```

---

## Step 3 — 对齐 delivery_template（L1）

有 `template_id` 的步：

1. 打开 `business/delivery_templates/<id>.yaml`  
2. `check_rules` / 必需文件与【交付】一致  
3. 缺 template → **先补 template 或去掉 template_id**（勿空挂）

无 template 时：L1 仅依赖内核 gate 默认规则；评审步承担 L2。

---

## Step 4 — 适配 inputs（可选但推荐）

为项目建输入包，**不**替代 YAML：

```text
business/inputs/<bundle>/
  README.md          # 本包用途、源文件表
  outline.md         # 可选：每章写作要点（无则写在各步【质量】）
  架构说明.md        # 可选：作图术语
  scripts/           # 可选：项目专有构建脚本
```

规则：

- **路径写进 workflow description 的【输入】**，不写进 skill  
- 合并/构建命令写在 `inputs/.../scripts/` 或 `officecli` skill；**不要**塞进 outline  
- Goal 里指定的模版 docx 路径 → 在【输入】引用，agent 执行阶段再读

---

## Step 5 — 校验（必须执行）

```bash
PYTHONPATH=backend venv/bin/python3 -c "
from common.workflow_loader import load_workflow
from common.workflow_bootstrap import ensure_workflow_ready
wid = '<workflow-id>'
p = load_workflow(wid)
body = p.loops[0].bodies.get('default', []) if p.loops else []
print('version', p.version, 'loop_steps', len(body), [s.get('id') for s in body])
ensure_workflow_ready(wid, backend='claude')
print('ensure_workflow_ready: ok')
"
```

失败 → 修 YAML（常见：agent 无 task_type、template_id 不存在、依赖环、loop 体为空）。

---

## Step 6 — 交付给用户

1. `business/workflows/<id>.yaml` + version 变更说明  
2. Loop 单元表（id / Done / 交付物 / 依赖）  
3. 新建/修改的 `delivery_templates/`、`business/inputs/<bundle>/` 列表  
4. `checklist.md` 自评（≥14/18 + 三问全 Y）  
5. **提醒**（不代写 registry）：各 agent 在「管理」挂载的 methodology / `quality-review` / `officecli`  

---

## 放行模型（设计时要写进 transition）

| 层 | 机制 | 标志 |
|----|------|------|
| L0 提交 | agent 交 deliverable | 文件落盘 |
| L1 结构 | delivery_template / gate | 路径、壳 |
| L2 质量 | `section-review` 步 + `quality-review` 方法论 | `REVIEW: PASS` / `FAIL` |
| L3 衔接 | 评审步核对上下游术语/图 | 写在 review【质量】，非脚本 |

---

## 当前 skill 生态（设计时引用）

| Skill | 设计期 | 运行期 |
|-------|--------|--------|
| `workflow-design` | ✅ 本 skill | — |
| `coordination-methodology` | 多 agent 编排边界 | main |
| `product-methodology` 等 | 知道存在即可 | 各角色执行 |
| `quality-review` | 评审步该输出什么 | main 挂载 |
| `officecli` | 知 docx/pptx 步存在即可 | product 等挂载 |

**task_type 在内核；skill 在管理页。** Workflow 只保证 task_type 与 agent 能力匹配。

---

## 反模式

- 用 `章节大纲.md` 代替 YAML 里的 step 列表（大纲只能补充【质量】，不能定义 DAG）  
- 把 python/venv 命令写进 inputs 或 outline  
- `split_enabled: true` 掩盖设计期未切步  
- 评审步无 `REVIEW: PASS/FAIL` transition  
- 为省事先抄别项目 YAML 却不改 inputs/template/章节数  

---

## 参考

| 文件 | 用途 |
|------|------|
| `patterns/work-review-round.yaml` | 两轮 work–review |
| `patterns/doc-plan-static.yaml` | 图 + 静态章 + merge + review |
| `checklist.md` | 打分与三问 |
| `intake-template.md` | Step 0 填空 |
| `docs/README.md` | 多 agent 讨论协作规范 |
| `docs/context-propagation.md` | 同 agent 多 step：共识 / 冲突 / TBD |
| `business/workflows/区块链产品规划-完善.yaml` | 静态多章完整样例 |
| `business/workflows/方案完善.yaml` | 通用 work–review |
