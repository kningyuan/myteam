## SKILL.patch.md

### Procedure
在 workflow_execute 场景下，调用 `submit_result.py` 提交结果时，应遵循以下标准化流程：
1. 将 JSON 响应内容写入一个确定的临时文件（如 `/tmp/result_submit.json`）。
2. 使用 `--file` 参数显式指向该临时文件路径，确保脚本能正确读取。
3. 若脚本报错，优先检查文件是否存在及路径是否正确，而非盲目重试。

### Pitfalls
- **路径引用陷阱**：在 heredoc 或 shell 命令中直接传递 JSON 字符串时，脚本可能无法正确解析 stdin 或临时路径。务必先 `write` 文件，再传文件路径。
- **参数混淆**：`submit_result.py` 的 `--out` 参数指定输出目录/文件名，`--file` 参数指定待提交的结果 JSON 文件。两者不要混用。

### Verification
执行 `ls -l /Users/kuanghualong/Project/Cursor/myteam/business/workspaces/workspace-research/.response/<interaction_id>.response` 确认文件已生成，且内容为合法的 JSON 对象。
