---
name: SOP 转 Workflow
description: 将人类SOP通过多轮对话转换为Agentic Workflow YAML，是workflow-creator的前置步骤。
---
# sop-to-workflow — 将人类 SOP 转换为 Agentic Workflow

> **你是 SOP 翻译官，不是执行者。**
> 产出：`business/agentic-workflows/<id>.yaml`
> **禁止**直接创建 myteam workflow（那是 workflow-creator 的事）

---

## 何时启用

- 用户说"我要把XX流程做成workflow"
- 用户说"我有一个SOP想转换"
- 用户描述了一个重复执行的业务流程
- 用户说"创建workflow"但没有现成的Agentic Workflow YAML

---

## 工作流程

### Phase 1: 自由描述（1轮）

引导用户自由描述 SOP：

```text
请用你习惯的方式描述这个流程：
1. 这个流程的目标是什么？
2. 涉及哪些角色/参与者？
3. 大致的步骤有哪些？
4. 最终产出是什么？
```

**规则**：
- 不要打断用户，让其自由描述
- 记录所有提到的信息
- 如果用户描述过于简短，再追问

---

### Phase 2: 结构化追问（2-4轮）

根据用户描述，按以下维度追问。**每个维度最多问2个问题**，避免过度打扰。

#### 维度 1: 输入输出

```text
关于输入输出：
- 这个流程需要哪些输入材料？
- 每个步骤的产出分别是什么？
- 最终交付物的格式要求？（Markdown/Word/PDF/其他）
```

#### 维度 2: 角色分工

```text
关于角色分工：
- 每个步骤由谁执行？（research/product/developer/qa/其他）
- 有没有审批/评审环节？
- 角色之间如何交接？
```

#### 维度 3: 质量标准

```text
关于质量标准：
- 什么情况下算"做完了"？
- 有哪些验收标准？
- 报告需要包含哪些章节？
```

#### 维度 4: 异常处理

```text
关于异常处理：
- 如果某个步骤失败了怎么办？
- 有没有重试机制？
- 有哪些特殊情况需要额外处理？
```

---

### Phase 2.5: 可行性判断

在 Phase 2 结束后，评估 SOP 是否可转换为 workflow。

**检查项**：

| 检查项 | 最低要求 | 不满足时处理 |
|--------|----------|--------------|
| 步骤数量 | ≥ 2 步 | 提示用户补充步骤 |
| 执行角色 | 至少识别 1 个 | 使用默认值 `product` |
| 输入输出 | 至少 1 个输入 | 提示用户补充 |
| 质量标准 | 可选 | 使用默认值 `min_length: 500` |

**复杂度评估**：

```text
复杂度评分：
- 步骤数 × 10
- 角色数 × 5
- 输入数 × 3
- 输出数 × 3

总分：
- < 30 → 简单流程（可直接转换）
- 30-60 → 中等流程（需确认）
- > 60 → 复杂流程（建议拆分）
```

**如果复杂度 > 60**，提示用户：

```text
⚠️ 检测到复杂流程：
- 步骤数：<N>
- 角色数：<M>
- 复杂度评分：<score>

建议：
1. 拆分为多个子流程
2. 或者继续但接受较简单的配置

请选择：
1. 继续转换（使用简化配置）
2. 拆分流程（需要更多描述）
3. 取消
```

---

### Phase 3: 完成度评判

检查以下字段是否完整：

| 字段 | 必填 | 检查方式 |
|------|------|----------|
| name | ✅ | 流程名称 |
| description | ✅ | 流程描述 |
| steps | ✅ | 至少2个步骤 |
| agents | ✅ | 每个步骤有执行者 |
| inputs/outputs | ✅ | 每步有输入输出 |
| quality_gates | ✅ | 每步有质量标准 |
| dependencies | ⬜ | 步骤间依赖关系 |
| parallel | ⬜ | 可并行的步骤 |

**判定规则**：
- 必填字段全部完成 → 进入 Phase 4
- 缺少关键信息 → 针对性追问（不要重复已问过的）
- 用户明确表示"就这样" → 用默认值填充可选字段

**默认值**：
- 无明确 agent → 使用 `product`
- 无质量标准 → 使用 `min_length: 500`
- 无依赖关系 → 假设串行执行

---

### Phase 4: 生成 Agentic Workflow YAML

将对话内容转换为 Agentic Workflow YAML 格式，保存到 `business/agentic-workflows/<id>.yaml`。

#### ID 生成规则

```python
# 从名称生成 ID
name = "竞品分析"
workflow_id = "competitive-analysis"  # kebab-case

name = "产品PRD评审"
workflow_id = "prd-review"
```

#### Agent 映射规则

| 用户描述 | agent_id |
|----------|----------|
| 研究员/调研/收集信息 | research |
| 产品/分析/写报告 | product |
| 开发/实现/写代码 | developer |
| 测试/评审/QA | qa |
| 架构/设计 | arch |
| 运维/部署 | ops |

#### YAML 生成模板

```yaml
id: <workflow-id>
version: "1.0"
name: <workflow-name>
description: <workflow-description>

metadata:
  source_sop: "<用户原始描述摘要>"
  created_at: "<当前日期>"
  domain: "<领域>"

inputs:
  - name: <input-name>
    type: string
    description: "<描述>"
    required: true

steps:
  - id: step-<name>
    name: <步骤名称>
    description: |
      【范围】<做什么/不做什么>
      【输入】<输入>
      【交付】<交付物>
      【质量】<质量标准>
    agent: <agent-id>
    task_type: <task-type>
    inputs:
      - <input-name>
    outputs:
      - name: <output-name>
        type: file
        format: markdown
    quality_gate:
      type: check_sections
      required_sections:
        - <section-1>
        - <section-2>
      min_length: 500

outputs:
  - name: <final-output>
    type: file
    format: markdown
    description: "<描述>"
```

---

### Phase 5: 确认与迭代

展示生成的 YAML 给用户确认：

```text
已生成 Agentic Workflow：
- 文件：business/agentic-workflows/<id>.yaml
- 步骤数：<N>
- 参与角色：[agent1, agent2, ...]

内容预览：
1. <step-1-name> → <agent-1>
2. <step-2-name> → <agent-2>
...

请确认：
1. 步骤是否完整？
2. 角色分配是否正确？
3. 质量标准是否合理？
```

**用户确认后**，提示下一步：

```text
Workflow 已准备好。下一步：
1. 使用 workflow-creator skill 创建 myteam 配置
2. 或者先手动调整 YAML
```

**如果用户选择调整**，进入迭代循环：

```text
请告诉我需要修改的内容：
- 修改步骤名称/描述？
- 调整角色分配？
- 添加/删除步骤？
- 修改质量标准？
```

根据用户反馈修改 YAML，重新展示确认。

---

### 异常处理

**场景 1: 用户描述过于模糊**

```text
您的描述信息不足，无法生成完整的工作流。请补充以下信息：
1. 这个流程的目标是什么？
2. 涉及哪些角色？
3. 大致步骤有哪些？

或者输入 "取消" 终止本次操作。
```

**场景 2: 无法识别执行角色**

```text
无法确定某些步骤的执行角色。请告诉我：
- <步骤名称> 应该由谁执行？（research/product/developer/qa/其他）

或者使用默认角色：product
```

**场景 3: YAML 生成失败**

```text
生成 Agentic Workflow 时出错：
- 错误：<error_message>

可能原因：
- YAML 格式错误
- 文件权限不足
- 目录不存在

请检查后重试，或输入 "取消" 终止。
```

**场景 4: 用户中途放弃**

```text
已保存当前进度：
- 文件：business/agentic-workflows/<id>.yaml（草稿）

如需继续，可：
1. 重新描述 SOP 继续编辑
2. 直接使用 workflow-creator 转换现有 YAML
3. 删除草稿：rm business/agentic-workflows/<id>.yaml
```

---

## 输出格式

产出文件存放在 `business/agentic-workflows/<id>.yaml`。

文件格式参考：`business/agentic-workflows/README.md`（如有）

---

## 红线

| 允许 | 禁止 |
|------|------|
| 生成 Agentic Workflow YAML | 直接创建 myteam workflow |
| 追问用户补充信息 | 假设用户未提供的信息 |
| 使用默认值填充可选字段 | 省略必填字段 |
| 保存到 `business/agentic-workflows/` | 保存到其他目录 |
