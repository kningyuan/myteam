---
name: diagram-build
task_type: diagram-build
description: Router — ALL + catalog 自选 means；执行见 business/means/diagram-build/
workflows:
  - 产品独立交付
agents:
  - product
  - arch
  - developer
  - frontend
  - analyst
  - research
  - content
  - docs
  - main
---

# diagram-build — task_type Router

本文件是 **task_type 路由**（B 层入口），不是 means 本体。  
Means 脚本在 `business/means/diagram-build/`。

## 必读

| 文档 | 路径 |
|------|------|
| ALL 过程 | `business/playbooks/ALL.md` |
| 过程脚手架 | `business/playbooks/scripts/scaffold_process.sh` |
| Skill/means 目录 | `business/skills/catalog.yaml` |
| means 执行 | `business/means/diagram-build/EXECUTION.md` |

## 执行顺序

```text
scaffold_process.sh → align.md → plan.md（catalog 自选 means）
  → probe.sh → brief/.drawio → build_diagram.sh → deliverable
  → verify_diagram.py → verify.log → ledger → submit_result
```

## 快速命令

```bash
DELIV="<交付物目录>"
bash business/playbooks/scripts/scaffold_process.sh "$DELIV"
bash business/means/diagram-build/scripts/probe.sh | tee -a "$DELIV/verify.log"
```

Workflow **不得**写 `【Skill】`；自选写在 **`plan.md`**。
