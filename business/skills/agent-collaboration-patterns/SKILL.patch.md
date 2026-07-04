## Pitfalls（实战踩坑）

- **submit_result 路径不一致**：prompt 模板中 `submit_result.py` 路径可能指向 `backend/common/agent/`，但实际文件在 `backend/common/delivery/`。执行前先用 `ls` 验证路径，避免浪费 step 在错误路径上。
- **长路径 shell 解析异常**：含 `/` 的长绝对路径在 bash 命令中可能被 shell 意外截断或替换（如 `Curso` → `Cursor` 丢失字符）。**解法**：先将路径赋值给环境变量再引用（`PY=/path/to/python && SUB=/path/to/submit.py && OUT=/path/to/output && python "$PY" "$SUB" --out "$OUT"`），避免在单条命令中直接拼接长路径。