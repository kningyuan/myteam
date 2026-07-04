name: 技术评估与选型
description: 多维度并行技术调研到最终评审定稿
version: "2.0"
tasks:
  - id: research-market
    name: 市场调研
    agent: research
    task_type: research
    reviewer: product
    description: 调研目标技术的市场adoption情况，GitHub stars趋势，企业使用案例
    dependencies: []
  - id: research-tech
    name: 技术深度调研
    agent: arch
    task_type: system-design
    reviewer: main
    description: 调研目标技术核心架构和特性，性能基准，安全性，兼容性
    dependencies: []
  - id: research-competing
    name: 竞品对比调研
    agent: research
    task_type: competitive-analysis
    reviewer: product
    description: 调研目标技术的主要竞品，从功能性能生态三个维度对比
    dependencies: []
  - id: synthesis-compare
    name: 综合对比分析
    agent: product
    task_type: strategy
    reviewer: main
    description: 基于三份并行调研报告做综合对比分析，产出技术选型对比矩阵
    dependencies: [research-market, research-tech, research-competing]
  - id: plan-iterate
    name: 方案迭代完善
    loop: plan_improve_round
    dependencies: [synthesis-compare]
  - id: final-review
    name: 最终评审定稿
    agent: main
    task_type: section-review
    description: 对最终方案做全面评审，输出最终技术评估报告
    dependencies: [plan-iterate]
loops:
  - id: plan_improve_round
    max_rounds: 3
    min_rounds: 1
    default_body: draft
    bodies:
      draft:
        - id: work
          name: 撰写方案初稿
          agent: product
          task_type: strategy
          description: 基于综合对比分析结果撰写技术选型方案初稿
          dependencies: []
        - id: assess
          name: 评估方案初稿
          agent: main
          task_type: section-review
          description: 评估方案初稿质量，输出标记 ITERATION: PASS 或 ITERATION: CONTINUE 或 ITERATION: STOP
          dependencies: [work]
      revise:
        - id: work
          name: 修订方案
          agent: product
          task_type: strategy
          description: 根据评审反馈修订方案
          dependencies: []
        - id: assess
          name: 评估修订稿
          agent: main
          task_type: section-review
          description: 评估修订稿是否解决了上一轮问题，输出标记 ITERATION: PASS 或 ITERATION: CONTINUE 或 ITERATION: STOP
          dependencies: [work]
    assess:
      ref: assess
      inputs:
        - kind: goal
        - kind: phase.deliverable
          phase: work
    transition:
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: PASS"
        action: exit
        outcome: complete
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: STOP"
        action: exit
        outcome: needs_review
      - when: deliverable_marker
        task: assess
        marker: "ITERATION: CONTINUE"
        action: continue
        next_body: revise
      - when: exhausted
        action: exit
        outcome: needs_review
    on_pass: complete
    on_exhaust: needs_review
options:
  review_enabled: true
  split_enabled: true
  parallel_enabled: true
  max_parallel: 3---
name: Workflow 创建器
description: 将Agentic Workflow YAML转换为myteam完整配置，是sop-to-workflow的后续步骤。
---
# workflow-creator — 创建 myteam Workflow

> **你是配置工程师，不是设计师。**
> 读取 `business/agentic-workflows/<id>.yaml`，生成 myteam 完整配置。
> **禁止**修改 Agentic Workflow YAML（那是 sop-to-workflow 的产出）

---

## 何时启用

- 用户说"创建workflow"
- 用户说"把agentic workflow转成myteam配置"
- sop-to-workflow 完成后提示使用本 skill
- 用户有现成的 Agentic Workflow YAML 想要转换

---

## 前置条件

1. `business/agentic-workflows/<id>.yaml` 文件存在
2. YAML 格式有效，包含必填字段：id, name, steps, agents

---

## 幂等性规则

**重复运行处理**：
- 如果 `business/workflows/<id>.yaml` 已存在 → 提示用户选择：覆盖 / 跳过 / 取消
- 如果 `templates.yaml` 中已有对应 task_type → 跳过添加，仅提示已存在
- 如果 `agents_registry.json` 中 agent 已有该 task_type → 跳过添加，仅提示已存在

**覆盖模式**：
- 备份原文件为 `<filename>.bak.<timestamp>`
- 生成新配置
- 验证失败时自动从备份恢复

---

## 工作流程

### Step 0: 幂等性检查

```bash
# 检查 workflow 是否已存在
ls business/workflows/<workflow-id>.yaml 2>/dev/null

# 检查 task_type 是否已注册
grep -q "<task-type>" business/templates/templates.yaml 2>/dev/null
```

**如果已存在**，提示用户：

```text
⚠️ 发现已有配置：
- Workflow: business/workflows/<workflow-id>.yaml
- Task Type: <task-type> 已在 templates.yaml 中注册

请选择操作：
1. 覆盖 - 删除旧配置，重新生成
2. 跳过 - 保留现有配置，不执行转换
3. 取消 - 终止本次操作
```

等待用户确认后继续。

---

### Step 1: 读取 Agentic Workflow

```bash
# 列出可用的 agentic workflows
ls business/agentic-workflows/*.yaml

# 读取指定文件
read business/agentic-workflows/<workflow-id>.yaml
```

**验证清单**：
- [ ] YAML 格式有效
- [ ] 包含 `id` 字段
- [ ] 包含 `name` 字段
- [ ] 包含 `steps` 数组（≥2个步骤）
- [ ] 每个 step 有 `agent` 和 `task_type`

---

### Step 1.5: 用户确认

读取 Agentic Workflow 后，展示摘要并等待用户确认：

```text
📋 Agentic Workflow 摘要：
- ID: <workflow-id>
- 名称: <workflow-name>
- 步骤数: <N>
- 参与角色: [agent1, agent2, ...]
- Task Types: [type1, type2, ...]

步骤链：
1. <step-1-name> → <agent-1> (<task-type-1>)
2. <step-2-name> → <agent-2> (<task-type-2>)
...

确认转换为 myteam 配置？(y/n)
```

**等待用户确认后**才继续下一步。如果用户选择 n，终止流程。

---

### Step 2: 生成 templates.yaml 条目

为每个 step 的 `task_type` 生成 templates.yaml 条目。

**读取现有 templates.yaml**：
```bash
read business/templates/templates.yaml
```

**生成规则**：

```yaml
# 对于每个 step，添加到 templates.yaml
<task-type>:
  display_name: <step-name>
  deliverable_template:
    required_heading_level: 2
    sections:
    - name: <output-name>
      description: <output-description>
      required: true
  check_rules:
    required_sections:
    - <output-name>
    min_length: <quality_gate.min_length 或 500>
  task_type: <task-type>
  outcome_kind: artifact
```

**Task Type 命名规则**：
- 使用 lowercase + kebab-case
- 如果多个 step 使用相同 task_type，只创建一个条目
- 示例：`competitive-analysis`, `product-research`, `acceptance-report`

---

### Step 3: 更新 agents_registry.json

给相关 agent 添加新 task_type 的支持。

**读取现有配置**：
```bash
read business/config/agents_registry.json
```

**更新规则**：

```json
{
  "agents": {
    "<agent-id>": {
      "task_types": [
        // 现有 types...
        "<new-task-type>"
      ]
    }
  }
}
```

**Agent 映射验证**：
| Agentic Workflow agent | myteam agent_id | 状态 |
|------------------------|-----------------|------|
| research | research | ✅ 已存在 |
| product | product | ✅ 已存在 |
| developer | developer | ✅ 已存在 |
| qa | qa | ✅ 已存在 |
| arch | arch | ✅ 已存在 |
| 其他 | 需要创建 | ⚠️ 提示用户 |

---

### Step 4: 生成 workflow YAML

将 Agentic Workflow 转换为 myteam workflow 格式。

**输出路径**：`business/workflows/<workflow-id>.yaml`

**转换规则**：

```yaml
id: <workflow-id>
name: <workflow-name>
version: "1.0"
description: <workflow-description>
tasks:
  - id: <step-id>
    agent_id: <agent-id>
    task_type: <task-type>
    template_id: <task-type>  # 与 task_type 相同
    name: <step-name>
    description: <step-description>
    dependencies:
      - <depends-on-step-id>  # 从 depends_on 转换
```

**依赖关系处理**：
- `depends_on: []` → `dependencies: []`
- `depends_on: [step-research]` → `dependencies: [step-research]`

---

### Step 4.5: 备份与回滚

**生成前备份**：
```bash
# 备份原文件
timestamp=$(date +%Y%m%d_%H%M%S)
cp business/templates/templates.yaml "business/templates/templates.yaml.bak.${timestamp}" 2>/dev/null
cp business/config/agents_registry.json "business/config/agents_registry.json.bak.${timestamp}" 2>/dev/null
cp business/workflows/<workflow-id>.yaml "business/workflows/<workflow-id>.yaml.bak.${timestamp}" 2>/dev/null
```

**验证失败回滚**：
```bash
# 如果验证失败，从备份恢复
mv "business/templates/templates.yaml.bak.${timestamp}" business/templates/templates.yaml
mv "business/config/agents_registry.json.bak.${timestamp}" business/config/agents_registry.json
mv "business/workflows/<workflow-id>.yaml.bak.${timestamp}" business/workflows/<workflow-id>.yaml
```

---

### Step 5: 验证配置

运行验证命令确保配置有效：

```bash
PYTHONPATH=backend venv/bin/python3 -c "
from common.workflow_loader import load_workflow
from common.registry import get_spec

try:
    profile = load_workflow('<workflow-id>')
    print('✅ Workflow 加载成功')
    print(f'   步骤数: {len(profile.tasks)}')
    for t in profile.tasks:
        spec = get_spec(t['task_type'])
        status = '✓' if spec else '✗'
        print(f'   {t[\"id\"]}: task_type={t[\"task_type\"]} {status}')
except Exception as e:
    print(f'❌ 加载失败: {e}')
"
```

**验证检查项**：
- [ ] Workflow YAML 格式有效
- [ ] 所有 agent 存在
- [ ] 所有 task_type 已注册
- [ ] Agent 的 task_types 包含分配的类型
- [ ] 依赖关系有效

---

### Step 6: 输出结果

```text
✅ myteam Workflow 创建完成：

配置文件：
- business/workflows/<workflow-id>.yaml
- business/templates/templates.yaml (已更新)
- business/config/agents_registry.json (已更新)

Workflow 概览：
- ID: <workflow-id>
- 名称: <workflow-name>
- 步骤数: <N>
- 参与角色: [agent1, agent2, ...]
- Task Types: [type1, type2, ...]

步骤链：
1. <step-1-name> → <agent-1> (<task-type-1>)
2. <step-2-name> → <agent-2> (<task-type-2>)
...

下一步：
1. 在 UI 创建项目时选择 workflow: <workflow-id>
2. 或使用 API: POST /api/projects/run { "workflow": "<workflow-id>", "goal": "..." }
```

---

## 配置生成示例

### 输入：Agentic Workflow

```yaml
id: competitive-analysis
name: 竞品分析
steps:
  - id: step-research
    name: 信息收集
    agent: research
    task_type: competitive-analysis
    depends_on: []
  - id: step-analysis
    name: 对比分析
    agent: product
    task_type: competitive-analysis
    depends_on: [step-research]
  - id: step-report
    name: 报告撰写
    agent: product
    task_type: competitive-analysis
    depends_on: [step-analysis]
```

### 输出 1: templates.yaml 条目

```yaml
competitive-analysis:
  display_name: 竞品分析
  deliverable_template:
    required_heading_level: 2
    sections:
    - name: 竞品概览
      description: 填写「竞品概览」章节
      required: true
    - name: 能力对比矩阵
      description: 填写「能力对比矩阵」章节
      required: true
    - name: 优劣势分析
      description: 填写「优劣势分析」章节
      required: true
    - name: 差异化机会
      description: 填写「差异化机会」章节
      required: true
  check_rules:
    required_sections:
    - 竞品概览
    - 能力对比矩阵
    - 优劣势分析
    - 差异化机会
    min_length: 500
  task_type: competitive-analysis
  outcome_kind: artifact
```

### 输出 2: agents_registry.json 更新

```json
{
  "research": {
    "task_types": ["research", "competitive-analysis"]
  },
  "product": {
    "task_types": ["competitive-analysis", "product-research", ...]
  }
}
```

### 输出 3: workflow YAML

```yaml
id: competitive-analysis
name: 竞品分析
version: "1.0"
description: 对指定竞品进行多维度对比分析
tasks:
  - id: step-research
    agent_id: research
    task_type: competitive-analysis
    template_id: competitive-analysis
    name: 信息收集
    description: 收集各竞品的基础信息
    dependencies: []
  - id: step-analysis
    agent_id: product
    task_type: competitive-analysis
    template_id: competitive-analysis
    name: 对比分析
    description: 建立对比矩阵，识别差异化机会
    dependencies:
      - step-research
  - id: step-report
    agent_id: product
    task_type: competitive-analysis
    template_id: competitive-analysis
    name: 报告撰写
    description: 输出最终竞品分析报告
    dependencies:
      - step-analysis
```

---

## 红线

| 允许 | 禁止 |
|------|------|
| 读取 Agentic Workflow YAML | 修改 Agentic Workflow YAML |
| 生成 templates.yaml 条目 | 删除现有 templates.yaml 条目 |
| 更新 agents_registry.json | 删除 agent 已有 task_type |
| 生成 workflow YAML | 跳过验证步骤 |
| 验证配置有效性 | 忽略验证错误 |
