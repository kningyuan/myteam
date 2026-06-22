本次教训：artifact.path 字段错误使用相对路径导致 Gate 双倍路径拼接失败。已在 SKILL.patch.md 新增 Pitfalls 条目和 Verification 检查项，指导 Worker Agent 在 execute 阶段仅写文件名而非相对路径。
