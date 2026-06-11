# Means — 可插拔小工具

**不是**单兵交付能力本身，而是 B 层 Agent 在 `plan.md` 里从 `business/skills/catalog.yaml` **自选**的手段。

```text
A 层 myteam 派 execute
  → B 层 ALL + catalog 自选
    → means/ 下脚本产出业务文件
```

## 目录约定

```text
business/means/<name>/
  EXECUTION.md      # 该 means 的执行说明
  scripts/
  templates/        # means 专用模板（如 diagram_brief.yaml）
  references/
```

## 当前 means

| id | 路径 | 用途 |
|----|------|------|
| diagram-build | `diagram-build/` | brief → draw.io → PNG |

新增 means：在此加目录 + 在 `business/skills/catalog.yaml` 登记。
