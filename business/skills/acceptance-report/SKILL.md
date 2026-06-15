---
name: "验收报告"
task_type: acceptance-report
description: 升级验收 — 对照契约与测试结果，给出发布建议。
---
# acceptance-report — 升级验收

**必须先读**：`business/skills/product-methodology/SKILL.md`（验收证据链）  
**再读**：`business/skills/product-operations/SKILL.md`  
**myteam 配置贯通任务再读**：`business/skills/myteam-config-linkage/SKILL.md`

## 通用产品验收（默认）

1. 对照上游 PRD/方案的 **R1/Rn** 逐项 PASS/FAIL。
2. 骨架：`business/skills/product-operations/templates/acceptance_checklist.md`
3. 无脚本日志不得写「全部通过」。

## myteam 系统升级 / 配置贯通（专用）

1. 阅读 `t-fe-contract`、`t-plan`、`t-test` 交付物。
2. **必须**确认 qa 已附 `run_config_regression.sh` 的 exit 0 输出或等价 pytest 日志；无日志不得写「全部通过」。
3. 对照 t-plan 的 P0/P1 清单逐项打勾（PASS / 遗留 / 降级）。
4. 运行静态校验（若 qa 未附）：

```bash
bash business/skills/myteam-config-linkage/scripts/run_config_regression.sh
python3 business/skills/myteam-config-linkage/scripts/verify_config_contract.py
```

5. 交付物章节：`验收范围` `验收结果`（表格）`遗留项` `发布建议`。

## 验收表模板

| 验收项 | 标准 | 证据 | 结果 |
|--------|------|------|------|
| 字段 33/33 对齐 | verify_config_contract PASS | 脚本输出 | |
| pytest 回归 | run_config_regression PASS | pytest 摘要 | |
| P0 修复 | t-plan 清单 | 代码 diff / 测试 | |
| 手动 31 项 | settings_manual_31 | qa 交付物 | |

## 红线

- 禁止无证据的「建议发布」。
- 遗留项须标优先级，不能隐瞒 known_gaps。
