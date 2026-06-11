---
name: system-design
task_type: system-design
description: 架构方案与 API 契约 — 输出可分工执行的 P0/P1 修复清单。
---

# system-design — 贯通方案与 API 契约

配置贯通类任务 **先读**：`business/skills/myteam-config-linkage/SKILL.md`

## 执行步骤

1. 阅读上游 `t-inventory`、`t-fe-contract` 交付物。
2. 复制 `templates/api_contract_table.md` 到交付物 **接口契约** 节，补全 33 字段 + owner。
3. 产出 **P0/P1 修复清单**：每项标明 `frontend | backend | 双方`、文件路径、验证命令。
4. 方案须 **最小 diff**；禁止改内核调度（`Process` / `AgentPort`）。
5. 交付物章节：`问题与约束` `领域与边界` `架构方案` `接口契约` `演化与风险`。

## 验证命令（写入每条修复项）

```bash
bash business/skills/myteam-config-linkage/scripts/run_linkage_tests.sh
```

## 红线

- 禁止新增 API 端点（除非 workflow 明确要求）。
- 禁止「重写内核」类建议。
- P0 = 用户可见且完全无效；P1 = 部分生效或缺测试。
