## 上游交付物缺失时的处理

### Procedure
1. 先尝试 glob/ls 常见路径（`./deliverables/`、任务目录、workspace 根）
2. 若文件不存在，检查元数据摘要中的 `t{n}_deliverable.md` 引用
3. 基于摘要撰写评审时，明确标注「基于元数据摘要，置信度受限」
4. 自评分数应下调（如 0.7–0.8），并在 known_gaps 中记录缺失项

### Pitfalls
- 不要跳过评审直接报错——摘要信息仍可产出有价值的结构化反馈
- 不要假装已读全文——评审局限性声明必须出现
- 不要给满分——缺失上游交付物本身就是质量风险

### Verification
- 交付物首段包含局限性声明
- known_gaps 数组含 "upstream_deliverables_not_found" 或类似条目
- 自评分数 < 0.9
