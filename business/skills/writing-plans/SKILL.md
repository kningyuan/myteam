---
name: writing-plans
description: 有规格或需求的多步骤任务，动代码前使用——产出精确到文件路径和验证步骤的实施计划
---

# 编写计划

> 来源：obra/superpowers (MIT)，适配 myteam。

## 概述

编写全面实施计划，假设工程师对代码库零上下文且品味存疑。记录他们需要知道的一切：每个任务触及哪些文件、代码、测试、可能需查阅的文档、如何测试。DRY、YAGNI、TDD、频繁提交。

假设他们是熟练开发者，但几乎不了解我们的工具链或问题域。

## 范围检查

如果规格覆盖多个独立子系统，建议拆分为多个计划——每个子系统一个。每个计划应独立产出可工作、可测试的软件。

## 文件结构

定义任务前，先映射将创建或修改哪些文件，每个文件负责什么：
- 设计清晰边界和良好定义接口的单元，每个文件一个明确职责
- 一起变更的文件放一起，按职责拆分而非技术层
- 现有代码库中遵循既有模式

## 任务粒度（2-5分钟一步）

```
"写失败测试" - 一步
"运行确认失败" - 一步
"写最小实现使测试通过" - 一步
"运行测试确认通过" - 一步
"提交" - 一步
```

## 计划文档头

```markdown
# [功能名] 实施计划

> **给 agentic worker：** 使用 subagent-driven-development 或 executing-plans 逐任务实现。

**目标：** [一句话描述构建什么]
**架构：** [2-3句方法]
**技术栈：** [关键技术/库]
```

## 任务结构

````markdown
### 任务 N: [组件名]

**文件：**
- 创建: `exact/path/to/file.py`
- 修改: `exact/path/to/existing.py:123-145`
- 测试: `tests/exact/path/to/test.py`

- [ ] **步骤1: 写失败测试**
```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **步骤2: 运行测试确认失败**
运行: `pytest tests/path/test.py::test_name -v`
预期: FAIL

- [ ] **步骤3: 写最小实现**
```python
def function(input):
    return expected
```

- [ ] **步骤4: 运行测试确认通过**
运行: `pytest tests/path/test.py::test_name -v`
预期: PASS

- [ ] **步骤5: 提交**
```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## 禁止占位符

每步必须包含工程师需要的实际内容。这些是**计划失败**：
- "TBD"、"TODO"、"稍后实现"
- "添加适当的错误处理"（无具体代码）
- "为上述写测试"（无实际测试代码）
- "类似任务N"（重复代码——工程师可能乱序阅读任务）
- 描述做什么但不展示怎么做（代码步骤必须有代码块）
- 引用未在任何任务中定义的类型/函数/方法

## 自审

写完计划后，用新眼光检查：
1. **规格覆盖**：规格每个章节/需求，能指向实现它的任务吗？列出缺口
2. **占位符扫描**：搜索红旗模式，修复
3. **类型一致性**：后期任务中的类型/方法签名/属性名与早期任务定义的匹配吗？

发现问题就地修复。规格需求无任务？添加任务。

## myteam 红线

- 执行前必须 Read 本 SKILL.md 全文
- 计划须精确到文件路径和验证命令
- 每步须含实际代码，禁止占位符（与 USER.md avoid 一致）
- 遵循 TDD：先写失败测试，再实现
- Gate 验收时，`设计方案`章节须含分步骤实施计划
