# Workflow 模式库

复制到 `business/workflows/<id>.yaml` 后替换 `{占位符}`，再完成 `../SKILL.md` Step 0–5。

## 文件

| 文件 | 场景 |
|------|------|
| `work-review-round.yaml` | 单交付物：work → review 多轮 |
| `doc-plan-static.yaml` | 图 → 静态 ch* → merge → review |

## 占位符

| 占位符 | 含义 |
|--------|------|
| `{workflow_id}` | YAML `id`（与文件名 stem 一致） |
| `{display_name}` | 中文名 |
| `{loop_id}` | loop 规格 id |
| `{input_bundle}` | `business/inputs/` 下目录名 |
| `{deck_template_id}` / `{doc_template_id}` | delivery_templates |
| `{last_chapter_id}` | 最后一章 step id（merge 依赖） |

## inputs 约定

- **可选** `business/inputs/{bundle}/outline.md`：每章写作要点  
- **禁止**在 outline 里写 step 列表、python 命令、venv 路径  
- **章节 step 只在 YAML** 展开；参考样例：`business/workflows/区块链产品规划-完善.yaml`

## 校验

```bash
PYTHONPATH=backend venv/bin/python3 -c "
from common.workflow_bootstrap import ensure_workflow_ready
ensure_workflow_ready('<workflow-id>', backend='claude')
print('ok')
"
```
