## Procedure: 环境变量缺失时的处理

当 `submit_result.py` 因环境变量（如 `MYTEAM_DISPATCH_TOKEN`）缺失被拒绝时：

1. **禁止绕过**：不得手动写入 `.response` 文件或调用其他 skill 脚本
2. **上报错误**：将错误信息通过对话回复告知用户，说明环境配置问题
3. **等待修复**：由系统管理员补充环境变量后重新触发

## Pitfalls

| 错误行为 | 正确做法 |
|---------|---------|
| 手动写入 `.response` 文件 | 停止操作，上报环境错误 |
| 尝试绕过 token 校验 | 等待管理员修复环境 |
| 在对话中直接返回 JSON | 通过 `submit_result` 提交，对话仅做说明 |

## Verification

- [ ] `submit_result.py` 调用失败时，Agent 停止尝试并上报
- [ ] 无手动写入 `.response` 文件的行为
- [ ] 对话回复仅用于说明，不替代 structured response
