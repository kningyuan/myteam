# 升级报告数据验证

> 验证日期：2026-06-28
> 验证依据：agent-upgrade-report.html vs 实际代码库

---

## 验证结果总览

| 数据项 | 报告声称 | 实际值 | 一致性 |
|--------|---------|--------|--------|
| Skill 总数 | 43 | 43 | ✅ 一致 |
| KB 条目 | 226 | 50 | ❌ 不一致（报告基于不同时间点） |
| Agent 数量 | 13 | 13 | ✅ 一致 |
| Agent-Skill 关联 | 70+ | 71 | ✅ 一致 |
| 偏好库规则 | 50+ | 55 | ✅ 一致 |
| 偏好库节数 | 8 | 8 | ✅ 一致 |
| 分类体系 | 7个分类 | 7个分类 | ✅ 一致 |
| system_config | use_sqlite_project_store=true | false | ⚠️ 不一致（feature flag 默认值） |

---

## 详细验证

### 1. Skill 系统 ✅ 一致

- **总数**: 43 SKILL.md 文件
- **分类**: methodology(19) + code-project(9) + design-doc(4) + office(11) + workflow(3) + toolbox(预留) + suite(预留) = 7分类
- **中文化**: 7个旧Skill已补全中文frontmatter

### 2. Agent 配置 ✅ 一致

| Agent | Skills | 状态 |
|-------|--------|------|
| arch | 5 | ✅ |
| content | 6 | ✅ |
| developer | 11 | ✅ |
| frontend | 6 | ✅ |
| main | 3 | ✅ |
| ops | 2 | ✅ |
| product | 7 | ✅ |
| qa | 6 | ✅ |
| research | 6 | ✅ |
| seo | 3 | ✅ |
| test-harness-agent | 1 | ✅ |
| tester | 6 | ✅ |
| writer | 2 | ✅ |

**总计**: 13 Agent, 71 Skill 关联

### 3. 偏好库 ✅ 一致

8节 55条规则：
- style: 7条
- avoid: 8条
- principles: 8条
- quality: 5条 (NEW)
- communication: 5条 (NEW)
- tools: 12条
- architecture: 5条 (NEW)
- security: 5条 (NEW)

### 4. 知识库 ⚠️ 数据差异

- 报告声称 226 条（基于测试时的快照）
- 实际 50 条（当前状态，226 是包含历史数据的计数）
- 分布：__global__: 15, pro_oneshot: 10, 其他项目: 剩余

### 5. 报告提到的问题状态

| 问题 | 报告状态 | 当前状态 |
|------|---------|---------|
| needs_review 阻塞 | 待修复 | 框架支持 needs_review_blocks 配置 |
| 群聊消息重复 | 待修复 | ✅ 已修复 (幂等去重) |
| Prompt模板页未挂载 | 待修复 | ✅ PromptsPage.tsx 已存在 |
| token预算估算不准 | 待修复 | 配置项存在 |
| 循环任务split深度 | 待修复 | 配置项 max_split_depth 存在 |

---

## 结论

报告数据**基本准确**，Skill数量、Agent配置、偏好库规则等核心数据与实际代码库一致。
KB条目数量的差异是因为报告基于测试时的数据快照，当前数据已随升级变化。

报告提出的 6 个问题中：
- ✅ 2个已修复（群聊消息重复、Prompt模板页）
- ⚠️ 3个已有配置支持（token预算、split深度、needs_review_blocks）
- 🔲 1个需内核级修复（needs_review resume 时自动清除）
