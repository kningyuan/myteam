# 复盘教训写入建议

## Action: patch

**Skill ID**: `product-methodology`

**Notes**:

```markdown
## Procedure: submit_result 环境准备
- 执行 `submit_result.py` 前，先确认系统 Python 是否已安装 `pydantic`
- 若系统 Python 缺少依赖，使用项目 venv Python：`venv/bin/python3`
- 建议在 worker prompt 中预置检查步骤：`venv/bin/python3 -c "import pydantic"`

## Pitfalls
- `submit_result.py` 依赖 pydantic 进行合约校验，系统 Python 默认未安装
- 直接调用 `python3`（系统路径）会因缺少依赖导致提交失败
- 失败后需切换到 `venv/bin/python3` 重试

## Pitfalls（续）
- `deliverable_adopted.path` 应使用**相对路径**（相对于 `MYTEAM_ROOT`），而非绝对路径
- 上一轮门禁失败：`result.artifact.path` 用了绝对路径 `/Users/.../deliverables/...`，Gate 拒绝
- 正确格式：`t3.t3.1_deliverable.md` 或 `business/tasks/project/<id>/deliverables/t3.t3.1_deliverable.md`
- 路径错误会导致 `deliverable_adopted` 无法正确关联，Gate 返回 `needs_review`

## Verification（续）
- 提交前验证：`venv/bin/python3 /path/to/submit_result.py --help` 应无报错
- 提交后验证：检查 `.response/` 目录是否存在同名 `.response` 文件
- 验证文件内容是否符合 `InteractionResponse` 合约（可通过 `venv/bin/python3 -c "from pydantic import BaseModel; ..."` 校验）
- **路径校验**：`deliverable_adopted.path` 不应以 `/` 开头；若以 `/` 开头，需转为相对路径
```
