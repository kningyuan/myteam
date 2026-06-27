## Rubric 对齐（Rubric-First Approach）

### 何时触发
- 执行 `phase=execute` 任务时，在撰写交付物之前
- 任务有明确的 rubric 或评分标准时

### Procedure
1. **读取 rubric**：从 task 配置或 rubric 文件中提取所有评分维度（dimensions）和检查项（checklist items）
2. **映射章节**：将 rubric 的每个维度映射为交付物的必需章节
   - 「需求目标匹配度」→ 目标用户/角色定位
   - 「交付物完整度」→ 正常流程 + 异常分支 + 功能清单
   - 「落地可行性」→ 技术约束 + 运营约束 + 现有系统限制
   - 「信息调研」→ 信息缺口标注
   - 「产品思维完整性」→ 效果衡量指标 + 目标用户定位
3. **撰写交付物**：按映射后的章节结构撰写，确保每个 rubric 维度都有对应内容
4. **提交前自检**：对照 rubric 逐项检查，确认无遗漏

### Pitfalls
- ❌ 凭经验自行决定交付物结构，忽略 rubric 要求
- ❌ 只关注「写得好」，忽略「写全了」
- ❌ 在交付物完成后才发现缺少 rubric 要求的章节，导致返工

### Verification
- 交付物中每个 rubric 维度都有对应章节或内容覆盖
- 提交前已完成 rubric 逐项自检
- Gate 状态为 completed 而非 needs_review
