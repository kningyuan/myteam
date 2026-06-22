## 架构对比调研方法论（补充参考）

### Procedure
1. **先读源码再查文档**：对比调研应先理解己方实现（`backend/adapter/` + `backend/adapters/`），再对标外部框架（LangChain 等），避免以外部概念强行套用
2. **三层对比框架**：
   - 架构分层（adapter isolation）
   - 数据契约（RunRequest/AgentEvent vs 外部框架的等价物）
   - 扩展机制（新增 CLI 适配器 vs 新增 agent type）
3. **证据标注**：每个结论需标注来源（行号/文档URL），区分 Layer 1（己方代码）、Layer 2（外部文档）、Layer 3（第一性原理判断）

### Pitfalls
- 避免「为了对比而对比」：对比应服务于具体设计决策（如「是否引入新 CLI」），而非泛泛罗列差异
- 外部框架文档可能过时，优先查源码或 GitHub issues 确认
- Gate 验收标准与执行 prompt 的 task_type 必须一致，否则会导致「做的和验收的不匹配」

### Verification
- 交付物应包含：己方架构解读 + 外部框架解读 + 对比矩阵 + 设计建议
- 每个对比维度至少引用 2 个证据源（1 个己方 + 1 个外部）
- 最终结论需明确回答「这对我们意味着什么」，而非停留在描述层
