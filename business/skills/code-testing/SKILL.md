---
name: "代码测试"
task_type: code-testing
description: 运行 pytest 与配置贯通测试，输出可复现的通过/失败报告。
---
# code-testing — 配置与回归验证

**必须先读**：`business/skills/qa-methodology/SKILL.md`  
配置贯通类任务 **再读**：`business/skills/myteam-config-linkage/SKILL.md`

## 执行步骤

1. **必须**运行全量回归，stdout 写入交付物 `output/regression.txt`：

```bash
bash business/skills/myteam-config-linkage/scripts/run_config_regression.sh \
  2>&1 | tee output/regression.txt
echo "EXIT_CODE=$?" >> output/regression.txt
```

2. 对照 `checklists/settings_manual_31.md` 完成手动验证，结果写入 `tests/cases.md`。
3. 复制 `templates/test_report.md` 结构写 `reports/test_report.md`。
4. 若有失败：记录 **用例名 | 断言 | 可能原因**；禁止改测试期望值糊弄通过。
5. 交付物章节：`测试范围` `执行命令` `结果摘要` `失败项` `建议`。

## 模板路径

- 测试报告：`business/skills/code-testing/templates/test_report.md`
- 手验清单：`business/skills/myteam-config-linkage/checklists/settings_manual_31.md`

## 红线

- 禁止未跑 `run_config_regression.sh` 就写「全部通过」。
- 禁止删除失败用例来「修复」回归。
- 禁止在 `known_gaps` 中隐瞒脚本已报 FAIL 的项。
