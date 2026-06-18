# Workflow 设计 — 项目勘察单

设计 YAML 前填写（可贴在 PR / 聊天回复）。**未填完 0.1 不得写 YAML。**

---

## 0.1 项目 Done

```text
【项目 Done】
【读者/用途】
【Out of scope】
【成功标准】
```

---

## 0.2 资产盘点

| 项 | 路径 / 结论 |
|----|-------------|
| 参考 workflow | |
| inputs bundle（新建/已有） | `business/inputs/` |
| delivery_templates | |
| 最终交付物路径 | `deliverables/…` |

---

## 0.3 Archetype

- [ ] work-review-round  
- [ ] doc-plan-static  
- [ ] 自研（简述 step 链）

`split_enabled`: false（默认）

---

## 0.4 Loop 单元表（草案）

| id | Done | 主交付物 | agent | task_type | template_id | 依赖 |
|----|------|----------|-------|-----------|-------------|------|
| | | | | | | |

Loop 六条自评：__/6（见 checklist.md）

---

## 0.5 校验记录

```text
load_workflow + ensure_workflow_ready: PASS / FAIL
失败原因：
```
