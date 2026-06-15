---
name: "QA 方法论"
task_type: qa-methodology
description: >-
  测试方法论：风险驱动范围→可复现命令→证据链→Gate 对齐。
  code-testing / test-plan 必须先读本 skill。
---
# 测试方法论（myteam 适配版）

> **来源合成**（已裁剪）：
> - 风险驱动测试（Risk-Based Testing）
> - 测试金字塔与回归纪律
> - 验收标准可追溯（R1/Rn ↔ 用例）
> - 缺陷报告：复现步骤 + 期望/实际 + 环境

**myteam 红线**：无脚本 exit 0 证据不得写「全部通过」；禁止删失败用例糊弄 Gate。

---

## 何时启用

- `task_type` 为 code-testing、test-plan
- `agent_id=qa` 的 architecture-review / code-review（质量视角）

---

## 执行流程（必须按序）

### Step 1 — 测试范围与风险

| 维度 | 内容 |
|------|------|
| 被测对象 | 上游 P0/P1、API 契约、用户路径 |
| 风险排序 | 数据丢失 > 安全 > 功能错误 > 体验 |
| 不在范围 | 明确不测的模块与理由 |
| 入口条件 | 需何种构建/配置/种子数据 |

### Step 2 — 测试策略

选层级并说明比例：

| 层级 | 用途 | myteam 默认命令 |
|------|------|-----------------|
| 单元 | Store、plan_gate、route contract | `pytest backend -q` |
| 贯通 | 配置读写对称 | `run_linkage_tests.sh` |
| 回归套件 | 发布前 | `run_regression.sh --suite unit` |
| E2E | 平台基线 | `reg_platform_v3_e2e_baseline.py` |

**禁止** 只写「手动测一下」而无命令与预期输出。

### Step 3 — 用例设计（test-plan）

每条用例须含：

```markdown
| ID | 场景 | 前置 | 步骤 | 期望 | 优先级 | 追溯(R1/…) |
|----|------|------|------|------|--------|------------|
| TC-01 | … | … | … | … | P0 | R1 |
```

P0 用例须覆盖上游 **全部** P0 验收项。

### Step 4 — 执行与证据链（code-testing）

1. **必须** 运行全量回归，stdout 写入 `output/regression.txt`：

```bash
bash business/skills/myteam-config-linkage/scripts/run_config_regression.sh \
  2>&1 | tee output/regression.txt
echo "EXIT_CODE=$?" >> output/regression.txt
```

2. 交付物含：`测试范围` `执行命令` `结果摘要` `失败项` `建议`
3. 失败项格式：**用例名 | 断言 | 可能原因 | 建议 owner**

### Step 5 — Gate 与 known_gaps

- `known_gaps` 须与脚本 FAIL **一致**；禁止隐瞒
- 部分通过 → 明确 **阻塞发布** 的 P0 列表
- 手验清单（如 settings_manual_31）结果写入 `tests/cases.md`

### Step 6 — 缺陷与回归

- 新缺陷：最小复现 + 环境 + 日志片段
- 修复验证：同一命令 rerun，附 before/after
- 不修改测试期望来「修复」产品 bug（除非需求变更已文档化）

---

## 与 task skill 的关系

| task_type | 本方法论 | code-testing / test-plan task skill |
|-----------|----------|-------------------------------------|
| test-plan | Step 1–3 | 模板章节、Gate 标题字面一致 |
| code-testing | Step 4–6 | 脚本路径、test_report 模板 |

---

## 反模式（禁止）

- 「目测 OK」无日志
- 跳过 run_config_regression.sh
- 删除失败 pytest 用例
- 测试报告与 regression.txt 矛盾
