---
name: "代码健康检查"
description: >-
  对代码仓库执行全面健康检查：TypeScript 编译检查、Python 测试、ESLint 代码质量、
  代码统计。生成可量化的健康评分仪表盘（0-10 分），输出改进建议。
  本 skill 仅在工作流驱动下执行，不独立调用。
task_types:
  - code-audit
agents:
  - developer
---
# code-audit — 代码健康检查

> **你是代码健康检查员，不是修复者。**  
> 不修改任何文件。只运行工具、收集结果、生成报告。  
> 产出：`deliverables/code-audit.md`（含检测结果 + 评分 + 改进建议）

> **与 `backend-engineering-methodology` 的分工**：本职工作覆盖后端代码的实现方法论，本 skill 覆盖代码库的量化检测评分体系。

---

## 何时被调度

- workflow step 指定 `task_type: code-audit`，分派本 agent 执行
- 作为多步 workflow 的一部分（例如：pytest → eslint → tsc → 汇总评分）
- **不**独立触发，由内核根据 workflow 定义调度

---

## Step 0 — 了解本项目

确认 MYTEAM_ROOT 在项目根目录：

```bash
MYTEAM_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
cd "$MYTEAM_ROOT"
```

检测技术栈：

```bash
echo "=== 项目统计 ==="
PY_FILES=$(find backend -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*" | wc -l)
TS_FILES=$(find frontend-v2/src -name "*.ts" -o -name "*.tsx" | wc -l)
PY_LINES=$(find backend -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*" -exec cat {} + | wc -l)
TS_LINES=$(find frontend-v2/src \( -name "*.ts" -o -name "*.tsx" \) -exec cat {} + | wc -l)
WF_FILES=$(ls business/workflows/*.yaml 2>/dev/null | wc -l)
TEST_FILES=$(find backend -name "test_*.py" | wc -l)
echo "Python 文件：$PY_FILES（${PY_LINES} 行）"
echo "TypeScript 文件：$TS_FILES（${TS_LINES} 行）"
echo "Workflow 数量：$WF_FILES"
echo "测试文件数：$TEST_FILES"
```

---

## Step 1 — 运行检测工具

### 1.1 TypeScript 编译检查

```bash
cd frontend-v2 && npx tsc --noEmit 2>&1; TS_EXIT=$?
echo "TS_EXIT=$TS_EXIT"
```

- exit 0 → 无错误（10 分）
- 记录错误行数（error TS 匹配的行数）

### 1.2 ESLint 代码质量

```bash
npx eslint --no-error-on-unmatched-pattern . 2>&1; ESLINT_EXIT=$?
echo "ESLINT_EXIT=$ESLINT_EXIT"
```

- 解析输出中的错误数（`✖ N problems`）
- 区分 errors 和 warnings

### 1.3 Python 测试

```bash
cd "$MYTEAM_ROOT"
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/ -q --tb=no 2>&1; PYTEST_EXIT=$?
```

- 解析 `N passed, M failed` 或 `N failed, M passed`
- 计算通过率 = passed / (passed + failed)

---

## Step 2 — 评分

使用以下权重计算综合得分：

| 类别 | 权重 | 10 分 | 7 分 | 4 分 | 0 分 |
|------|------|-------|------|------|------|
| TypeScript 编译 | 30% | exit 0（无错误） | < 5 个错误 | < 20 个错误 | ≥ 20 或失败 |
| ESLint | 25% | exit 0（无错误） | < 10 个错误 | < 30 个错误 | ≥ 30 个错误 |
| 测试通过率 | 35% | 100% 通过 | ≥ 95% | ≥ 80% | < 80% |
| 代码统计 | 10% | 目测结构合理，有足够测试（测试文件 > 20） | 测试 > 10 | 有测试 | 无测试 |

```text
综合得分 = tsc得分×0.30 + eslint得分×0.25 + 测试得分×0.35 + 代码统计×0.10
```

---

## Step 3 — 生成报告写入交付物

写入 `deliverables/code-audit.md`，格式：

```markdown
# 代码健康检查报告

## 执行摘要

检测时间：{时间}
检测范围：{项目名}（{Python 文件数} Python + {TS 文件数} TypeScript 文件）
工具链：tsc → eslint → pytest → 代码统计

## 检测结果

| 类别 | 工具 | 结果 | 得分 |
|------|------|------|------|
| TypeScript | tsc --noEmit | 通过/失败（N 个错误） | N/10 |
| ESLint | eslint | N 个错误，N 个警告 | N/10 |
| 测试 | pytest | N/N 通过 | N/10 |
| 代码统计 | 文件统计 | {简述} | N/10 |

### {工具名称} 详情

{如有问题，列出关键发现}

## 评分与趋势

**综合得分：{N}/10**

| 类别 | 得分 | 权重 |
|------|------|------|
| TypeScript | {N}/10 | 30% |
| ESLint | {N}/10 | 25% |
| 测试 | {N}/10 | 35% |
| 代码统计 | {N}/10 | 10% |

**加权计算：{公式和结果}**

## 改进建议

### 高优先级（影响评分 > 15%）
- {建议}

### 中优先级（影响评分 5-15%）
- {建议}

### 低优先级（影响评分 < 5%）
- {建议}

---

AUDIT: PASS
```

> 如果综合得分 ≥ 6，末行写 `AUDIT: PASS`  
> 如果综合得分 < 6，末行写 `AUDIT: FAIL`

---

## Step 4 — 清理

删除检测产生的临时文件（如有）：

```bash
rm -f /tmp/design-*.png 2>/dev/null || true
```

---

## 参考

| 工具 | 路径 |
|------|------|
| TypeScript 编译器 | `frontend-v2/node_modules/.bin/tsc` |
| ESLint | `frontend-v2/node_modules/.bin/eslint` |
| Pytest | `venv/bin/pytest` |

## 红线

- 禁止修改任何源代码文件（只读审计）
- 禁止删除或修改测试结果
- 评分必须基于实际工具输出，不可估算
- 报告必须包含全部四个章节（执行摘要 / 检测结果 / 评分与趋势 / 改进建议）