---
name: Git工作流方法论
description: Git工作流方法论：分支策略、提交规范、Code Review流程、冲突解决与发布管理，产出团队Git协作规范。
---
# Git工作流方法论

## 任务描述
制定团队 Git 协作规范，覆盖分支策略、提交规范、Code Review 流程、冲突解决与发布管理。

## 分支策略（Git Flow 简化版）

| 分支 | 命名 | 来源 | 合并到 | 生命周期 |
|------|------|------|--------|----------|
| main | `main` | - | - | 永久 |
| develop | `develop` | main | main(发布时) | 永久 |
| feature | `feature/xxx` | develop | develop | 临时 |
| hotfix | `hotfix/xxx` | main | main + develop | 临时 |
| release | `release/vX.Y` | develop | main + develop | 临时 |

### 分支规则
- `main` 分支始终可部署，受保护，只接受 PR 合并
- `develop` 分支为日常集成分支
- feature 分支命名：`feature/JIRA-123-add-login`
- 单个 feature 分支存活不超过 7 天
- 合并前必须 rebase 到最新 develop

## 提交规范（Conventional Commits）

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 列表

| Type | 语义 | 示例 |
|------|------|------|
| feat | 新功能 | `feat(auth): 添加OAuth登录` |
| fix | Bug修复 | `fix(api): 修复分页偏移` |
| docs | 文档 | `docs(readme): 更新安装步骤` |
| style | 格式 | `style(css): 统一缩进` |
| refactor | 重构 | `refactor(auth): 抽取token校验` |
| perf | 性能 | `perf(db): 添加索引` |
| test | 测试 | `test(auth): 补充登录用例` |
| chore | 杂项 | `chore(deps): 升级fastapi` |

### 规则
- subject 不超过 50 字，用中文描述
- body 解释"为什么"而非"做了什么"（diff 已说明做了什么）
- footer 标注 Breaking Change 或关联 Issue
- 一个提交只做一件事，不混合功能

## Code Review 流程

### 提交 PR 前
1. `git rebase -i` 整理提交历史（squash/fixup）
2. 本地跑通测试（`pytest` / `npm test`）
3. 自查清单：
   - [ ] 代码能跑
   - [ ] 测试覆盖了核心逻辑
   - [ ] 无 console.log / print 残留
   - [ ] 无硬编码密钥/密码
   - [ ] 命名清晰可读

### Review 检查清单
| 维度 | 检查项 |
|------|--------|
| 功能 | 是否实现了PR描述的目标？边界条件是否覆盖？ |
| 设计 | 是否遵循现有架构？是否过度设计？ |
| 可读性 | 命名是否清晰？函数是否过长？注释是否必要？ |
| 测试 | 是否有测试？测试是否有意义？ |
| 安全 | 输入是否校验？权限是否检查？ |
| 性能 | 是否有N+1查询？是否有不必要的循环？ |

### Review 礼仪
- 24小时内完成 Review
- 区分"必须改"(blocking) 和"建议改"(non-blocking)
- 用 `suggestion` 代码块给出修改建议
- 对事不对人，评论代码不评论人

## 冲突解决
1. `git fetch origin` 获取最新
2. `git rebase origin/develop` 变基到最新
3. 解决冲突：保留双方必要改动，删除冲突标记
4. `git add` + `git rebase --continue`
5. 冲突复杂时，两人结对解决

## 必选章节
- 分支策略与命名规范
- 提交规范（含 type 列表和示例）
- Code Review 流程与检查清单
- 冲突解决流程
- 发布管理流程

## Gate 规则
- 须有分支命名规范，不能只写"用feature分支"
- 提交规范须有 type 列表和示例
- Code Review 须有检查清单
- 须有冲突解决的具体步骤
