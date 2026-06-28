## Pitfall: 重复生成相同内容导致 token 耗尽

### 问题
Agent 在收到 rubric 反馈后，反复用 `write` 写入完全相同的交付物内容，未能实际修改。原因：reasoning 中意识到问题（"I keep writing the exact same content!"），但后续步骤仍重复相同操作，最终触发 token 上限（262144）导致 APIError。

### 根因
- 收到 rubric 反馈（如"缺少关键词：原因、背景、历史"）后，Agent 未重新读取已有交付物内容，而是从头生成，导致内容重复
- 缺乏"先读后写"的强制检查：未确认新内容与旧内容的差异就覆盖写入

### 修复建议
在 `product-methodology` 的 Procedure 中添加：

```markdown
### 交付物迭代流程（收到 rubric 反馈后）
1. **先读取当前交付物**：`Read` 已有文件，确认当前内容
2. **明确差异点**：列出 rubric 反馈中要求补充的具体内容（如关键词、章节）
3. **增量修改**：用 `Edit` 在原文基础上插入新内容，而非用 `Write` 覆盖全文
4. **验证差异**：写入前确认新内容包含 rubric 要求的关键词/章节
```

### Verification
- 收到 rubric 反馈后，第一步必须是 `Read` 已有交付物
- 使用 `Edit` 而非 `Write` 进行增量修改
- 每次写入后，检查内容是否包含 rubric 反馈中要求的新关键词
