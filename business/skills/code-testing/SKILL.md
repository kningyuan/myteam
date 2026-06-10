---
name: code-testing
task_type: code-testing
description: 运行 pytest 与配置贯通测试，输出可复现的通过/失败报告。
---

# code-testing — 配置与回归验证

## 执行步骤

1. 在 myteam 根目录执行：
   ```bash
   export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
   ./venv/bin/python -m pytest backend/common/tests/test_ui_config_linkage.py -q
   ./venv/bin/python -m pytest backend/common/tests/test_kernel_config.py backend/common/tests/test_skill_config_api.py -q
   ```
2. 若有失败：记录 **用例名 | 断言 | 可能原因**，不要静默改测试期望值糊弄通过。
3. 对设置 Tab 每一项，在交付物中给出 **手动验证步骤**（改设置 → 保存 → 触发路径 → 预期现象）。
4. 交付物章节：`## 测试范围` `## 执行命令` `## 结果摘要` `## 失败项` `## 建议`。

## 红线

- 禁止未跑测试就写「全部通过」。
- 禁止删除失败用例来「修复」回归。
