# T5 - Execute 单任务执行 测试

**测试模块**：Execute
**测试路径**：`/v2/execute`
**测试日期**：2026-06-27
**测试状态**：✅ 全部通过（4个Tab完整验证，finish沉淀功能正常）

---

## 测试用例

### T5.1 导航入口

| 项 | 详情 |
|----|------|
| **操作** | 查看主导航 |
| **预期** | 有「Execute」导航入口 |
| **实际** | 主导航第 5 项为「Execute」 |
| **结果** | ✅ 通过 |

---

### T5.2 任务列表

| 项 | 详情 |
|----|------|
| **操作** | 进入 Execute 页面，查看任务列表 |
| **预期** | 显示独立任务列表，含状态标识 |
| **实际** | 显示 6 个任务，状态标识清晰（✓ 完成 / EX 进行中） |
| **结果** | ✅ 通过 |

**任务列表内容**：

| 任务 ID | 状态 | 项目 |
|---------|------|------|
| t-eval-01 | ✓ done | sa-human |
| t-eval-02 | ✓ done | sa-human |
| t-research-01 | ✓ done | sa-q1 |
| t-research-02 | EX 进行中 | sa-q1 |
| t-research-02b | EX 进行中 | sa-q1 |
| t-pref-01 | EX 进行中 | ui-test |

---

### T5.3 新建任务弹窗

| 项 | 详情 |
|----|------|
| **操作** | 点击「新建任务」按钮 |
| **预期** | 弹出任务创建表单，字段完整 |
| **实际** | 弹窗正常，包含完整字段 |
| **结果** | ✅ 通过 |

**新建任务表单字段**：

| 字段 | 类型 | 说明 | 状态 |
|------|------|------|------|
| project_id | 文本输入 | 项目 ID（必填） | ✅ |
| task_id | 文本输入 | 任务 ID（必填） | ✅ |
| Agent | 下拉选择 | 执行角色（13 个角色可选） | ✅ |
| task_type | 下拉选择 | 任务类型（10+ 种类型） | ✅ |
| 意图 | 文本输入 | 任务意图描述 | ✅ |
| prepare | 按钮 | 准备任务 | ✅ |

**Agent 下拉选项**（13 个）：
- 研究员 (research)
- 项目经理 (main)
- 产品专家 (product)
- 前端研发 (frontend)
- 测试专家 (qa)
- 后端研发 (developer)
- 架构师 (arch)
- 运维专家 (ops)
- content
- seo
- test-harness-agent
- tester
- writer

**task_type 下拉选项**（10+ 种）：
- 评审 (review)
- 编码 (coding)
- 调研 (research)
- 发布帖子 (publish-post)
- 产品调研 (product-research)
- 产品规划 (product-planning)
- 我的类型 (my-type)
- 决策记录 (decision-record)
- 数据分析 (data-analysis)
- 自定义调研 (custom-survey)
- 竞品分析 (competitive-analysis)
- ...

---

### T5.4 任务详情 - 4个Tab完整验证

| 项 | 详情 |
|----|------|
| **操作** | 点击任务 t-eval-01，逐个切换4个Tab |
| **预期** | 任务详情有 4 个 Tab，内容完整 |
| **实际** | 4个Tab均正常显示，内容完整 |
| **结果** | ✅ 通过 |

**4个Tab清单及验证结果**：

| Tab名称 | 功能说明 | 验证结果 |
|---------|----------|----------|
| Harness 块 | execute 实际注入内容预览 | ✅ 正常显示 |
| 完整 Prompt | 发送给Agent的完整prompt | ✅ 正常显示 |
| 交付物 | 任务交付的成果物（Markdown） | ✅ 正常显示，含调研目标/信息来源/关键发现/结论 |
| Ledger | 任务执行台账与经验教训 | ✅ 正常显示，内容丰富 |

**Ledger 详细字段**：
- task_id / task_type / intent
- summary（任务总结）
- director_verdict（总监判定：fail）
- director_score（总监评分：2）
- lesson（经验教训）
  - worked（有效做法）
  - failed（失败原因）
  - pitfalls（常见坑点）
- director_correction（总监改进措施）
- keywords（关键词）

---

### T5.5 finish 操作与知识沉淀

| 项 | 详情 |
|----|------|
| **操作** | 查看已完成任务的状态和KB引用 |
| **预期** | 任务finish后沉淀到知识库，有KB引用 |
| **实际** | 任务显示「已 finish」状态，有 KB ref: kb://sqlite/52 |
| **结果** | ✅ 通过 |

**验证结果**：
- ✅ 任务完成状态显示（已 finish）
- ✅ Agent 信息（product）
- ✅ task_type 信息（research）
- ✅ prepared 时间戳（2026-06-19T11:42:31）
- ✅ KB 引用（kb://sqlite/52）
- ✅ 知识沉淀闭环：任务执行 → finish → 入知识库

---

## 小结

| 指标 | 值 |
|------|-----|
| 测试用例数 | 5 |
| 通过 | 5 |
| 失败 | 0 |
| 阻塞 | 0 |
| 通过率 | 100% |

**结论**：Execute 模块功能完整，全部验证通过。
- ✅ 任务列表展示与状态标识
- ✅ 新建任务表单（13个Agent角色、15种任务类型）
- ✅ 任务详情4个Tab（Harness/Prompt/交付物/Ledger）
- ✅ Ledger 台账包含完整的质量评估和经验教训
- ✅ finish 操作与知识沉淀（KB ref）
- ✅ 与知识库形成完整闭环

**截图记录**：
- t5-execute-list.png - Execute任务列表
- t5-execute-detail.png - 任务详情页
