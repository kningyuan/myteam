---
name: requesting-code-review
description: 完成任务、实现重大功能或合并前使用——派发代码审查子agent，在问题级联前捕获
---

# 请求代码审查

> 来源：obra/superpowers (MIT)，适配 myteam。

## 核心原则

```
早审查，勤审查
```

派发代码审查子agent，在问题级联前捕获。审查者获得精确构造的上下文——不是你的会话历史。这让审查者聚焦工作产品，而非你的思考过程。

## 何时请求审查

**强制：**
- 子agent驱动开发中每个任务后
- 完成重大功能后
- 合并到 main 前

**可选但有价值：**
- 卡住时（新视角）
- 重构前（基线检查）
- 修复复杂bug后

## 如何请求

**1. 获取 git SHA：**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # 或 origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. 派发代码审查子agent：**
构造审查上下文，包含：
- **描述**：构建了什么的简要总结
- **计划或需求**：应该做什么
- **BASE_SHA**：起始提交
- **HEAD_SHA**：结束提交

**3. 处理反馈：**
- Critical 问题立即修复
- Important 问题继续前修复
- Minor 问题记录稍后处理
- 审查者错误时用技术理由反驳

## 反馈分级处理

| 级别 | 处理 |
|------|------|
| Critical（阻塞性） | 立即修复，破坏功能/安全 |
| Important（重要） | 继续前修复 |
| Minor（次要） | 记录，稍后处理 |
| 误判 | 用技术理由反驳 |

## 红旗

**绝不：**
- 因为"简单"跳过审查
- 忽略 Critical 问题
- 带未修复 Important 问题继续
- 与有效技术反馈争论

**审查者错误时：**
- 用技术推理反驳
- 展示证明其有效的代码/测试
- 请求澄清

## 与工作流集成

- **子agent驱动开发**：每个任务后审查，问题复合前捕获
- **执行计划**：每个任务或自然检查点后审查
- **临时开发**：合并前审查，卡住时审查

## myteam 红线

- 执行前必须 Read 本 SKILL.md 全文
- code-deliverable/coding 任务完成后须自评（quality_status）
- review 任务须派发审查，区分 blocking/non-blocking
- Gate 验收时，`测试结果`章节须含审查反馈处理记录
- 与 verification-before-completion 配合：审查反馈须验证后再声称修复
