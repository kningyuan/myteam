---
name: architecture-review
task_type: architecture-review
description: 架构/配置/贯通性评审 — 输出可执行的差距矩阵与最小修复方案。
---

# architecture-review — 配置与架构评审

配置贯通类任务 **先读**：`business/skills/myteam-config-linkage/SKILL.md`

## 执行步骤

1. 阅读上游交付物与【项目目标】，列出评审范围。
2. 运行静态校验，结果附进「发现与分级」：

```bash
python3 business/skills/myteam-config-linkage/scripts/verify_config_contract.py
bash business/skills/myteam-config-linkage/scripts/scan_config_inventory.sh
```

3. 用 `templates/field_matrix.md` 做 **UI id → JSON path → GET/PUT** 对照；标注缺失/冗余/默认值不一致。
4. 表格输出：**项 | 现状 | 期望 | 差距 | 修复建议 | 风险 | owner**。
5. P0 = 用户可见且完全无效；P1 = 部分生效或缺测试；P2 = 文档/体验。
6. 交付物章节：`评审范围` `现状摘要` `发现与分级` `技术债务` `演进建议`（与 templates.yaml 对齐）。

## 前端专责（t-fe-contract）

- 只读 `frontend/` + 后端 DEFAULT 对照；**禁止改 backend**。
- 重点：`loadSettings` / `saveSettings` 与双 API 对称性。

## 红线

- 禁止在未读代码/未跑 verify 脚本的情况下断言「已贯通」。
- 禁止扩大 scope 到与目标无关的重构。
