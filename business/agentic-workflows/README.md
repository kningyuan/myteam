# Agentic Workflows

这个目录存放 Agentic Workflow YAML 文件，是 SOP 到 myteam workflow 的中间格式。

## 什么是 Agentic Workflow？

Agentic Workflow 是一种结构化的流程定义格式，用于：
1. 描述人类 SOP（标准操作流程）
2. 作为 myteam workflow 的输入
3. 通过 `sop-to-workflow` skill 生成
4. 通过 `workflow-creator` skill 转换为 myteam 配置

## 文件格式

```yaml
id: <workflow-id>           # 唯一标识，kebab-case
version: "1.0"              # 版本号
name: <workflow-name>       # 显示名称
description: <description>  # 流程描述

metadata:                   # 元信息
  source_sop: "<sop摘要>"   # 原始 SOP 描述
  created_at: "2026-06-25"  # 创建日期
  domain: "<domain>"        # 所属领域

inputs:                     # 输入定义
  - name: <input-name>
    type: string
    description: "<描述>"
    required: true

steps:                      # 执行步骤
  - id: step-<name>
    name: <步骤名称>
    description: |
      【范围】<做什么/不做什么>
      【输入】<输入>
      【交付】<交付物>
      【质量】<质量标准>
    agent: <agent-id>       # 执行角色
    task_type: <task-type>  # 任务类型
    depends_on: []          # 依赖关系
    inputs: []              # 输入
    outputs: []             # 输出
    quality_gate: {}        # 质量门禁

outputs:                    # 输出定义
  - name: <final-output>
    type: file
    format: markdown
    description: "<描述>"
```

## 使用流程

```
1. 用户描述 SOP
   ↓
2. sop-to-workflow skill 生成 Agentic Workflow YAML
   ↓
3. workflow-creator skill 读取 YAML
   ↓
4. 生成 myteam 完整配置：
   - business/templates/templates.yaml
   - business/config/agents_registry.json
   - business/workflows/<workflow-id>.yaml
   ↓
5. 创建项目时选择 workflow
```

## 示例

查看 `sop-to-workflow/SKILL.md` 中的示例。

## 相关 Skill

- `sop-to-workflow`: 将人类SOP转换为Agentic Workflow YAML
- `workflow-creator`: 将Agentic Workflow YAML转换为myteam配置
- `workflow-design`: 设计期方法论（已有skill）
