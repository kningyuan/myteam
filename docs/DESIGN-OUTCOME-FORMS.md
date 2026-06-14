# 产出形态（Outcome Forms）设计

> **版本**：2026-06-10  
> **状态**：权威定义（与 `outcome_kind` 代码 id 对齐）  
> **关联**：[DESIGN-DELIVERY-TEMPLATES.md](./DESIGN-DELIVERY-TEMPLATES.md) · [HUB2_PRODUCTIZATION_PLAN.md](./HUB2_PRODUCTIZATION_PLAN.md)

---

## 1. 三层配置模型

```text
task_type（任务类型）     → 做什么类工作（requirements、code-writing、publish-post…）
outcome_kind（产出形态）   → 交出来是什么「终极形态」（仅 3 种）
template_id（交付模板）   → 该形态下的结构契约（章节、文件、证据规则）
         ↓
Gate 按 outcome_kind 选算法，按 template 的 check_rules 验条目
Review 按 template 的 acceptance_criteria 验质量
```

**原则**：形态有限、模板无限；新增行业流程 = 复用/新增 task_type + 写 delivery_template，**不改 Kernel**。

---

## 2. 三种终极产出形态

| 产品名 | 代码 id | 载体 | Gate 算法 | 典型 task_type |
|--------|---------|------|-----------|--------------|
| **文档态** | `artifact` | 主 Markdown + 可选附件 | `check_format` | requirements, product-planning, architecture-review |
| **包态** | `code_project` | `deliverables/<task_id>/` 目录 | `check_code_project` | code-writing, code-testing, config-bundle |
| **证据态** | `action` | Markdown 中的 URL/截图/回执 | `check_action_evidence` | publish-post, deploy-run, geo-verification |

### 2.1 文档态 Document

- **定义**：结构化知识产出，以一篇（或主）Markdown 为 Gate 入口。
- **覆盖**：方案、需求、PRD、架构说明、评审、测试计划、验收、部署**记录**、数据分析、内容大纲…
- **模板规则**：`required_sections`、`file_exists`（png/drawio）、`must_include`、`stub_floor`

### 2.2 包态 Package（代码 id 仍为 `code_project`）

- **定义**：以**目录**为交付单元的多文件产出（不限于源码）。
- **覆盖**：代码工程、配置包（yaml/json）、测试 harness、数据管道目录、设计资产包。
- **模板规则**：`min_project_files`、`file_exists`、`require_code_file` 或 `required_extensions`

### 2.3 证据态 Evidence

- **定义**：证明「已在系统外完成动作」。
- **覆盖**：内容发布、部署 smoke、GEO 验证、线上开关留痕。
- **模板规则**：`evidence_url`（host、screenshot_field、verify_title）

---

## 3. 配置示例

```yaml
# templates.yaml — task_type
requirements:
  outcome_kind: artifact
  display_name: 需求

# workflow 任务行
- task_type: requirements
  template_id: prd-lite

# delivery_templates/prd-lite.yaml — Gate 唯一契约
check_rules:
  required_sections: [背景与目标, 范围, 用户故事与验收标准]
  min_length: 400
```

---

## 4. 部署类拆分（形态正交）

| task_type | 产出形态 | 含义 |
|-----------|----------|------|
| `code-deployment` | 文档态 | 部署**记录**（步骤、回滚方案 Markdown） |
| `deploy-run` | 证据态 | 部署**执行**留痕（URL + 健康检查截图） |

---

## 5. API

- `GET /api/task-types/outcome-kinds` — 产出形态目录（含中文产品名、Gate 说明、覆盖场景）
- `POST /api/task-types/suggest` — 从描述推导 task_type + outcome_kind + sections

---

## 6. 验收

```bash
venv/bin/python3 -m pytest backend/common/tests/test_outcome_forms.py -q
REG_CHECK_ONLY=1 venv/bin/python3 scripts/regression/reg_outcome_forms.py
```
