# R-L3-1 Skill 自动抽提 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-L3-1 |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | Skill 自动抽提属于 System Kernel 收尾能力：项目 completed 后生成 Skill 草案；不引入新的 LLM 总结链路 |
| QA | 验收必须证明草案文件存在、包含 project goal 关键词，并覆盖 one_shot/recurring 完成路径 |
| 工程 | 复用 `skill_extract.py` scaffold；在 `Process` completed 收尾触发 `_maybe_extract_skills`；默认只生成 `business/skills/auto-*` 草案 |

## 背景

原能力已有 scaffold：`extract_skill_draft()` 可从 deliverable 前 500 字生成 `SKILL.md` 草案，`Process._maybe_extract_skills()` 已接入普通 completed 收尾。但需求表要求「含任务 goal 关键词」，且 recurring completed 路径未触发抽提。

## 验收

- [x] `SKILL.md` 草案写入 `business/skills/auto-<project>-<task>/SKILL.md`
- [x] 草案元数据包含 `project_goal`
- [x] one_shot completed 路径触发抽提
- [x] recurring completed 路径触发抽提
- [x] `reg_l3_skill_extract.py` PASS

## 改动文件

- `backend/common/skill_extract.py`
- `backend/common/process.py`
- `backend/common/tests/test_skill_extract.py`
- `backend/common/tests/test_process.py`
- `scripts/regression/reg_l3_skill_extract.py`
- `scripts/regression/run_regression.sh`

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest \
  backend/common/tests/test_skill_extract.py \
  backend/common/tests/test_process.py::test_recurring_completed_extracts_skill_draft \
  backend/common/tests/test_recovery.py::test_maybe_extract_skills_writes_draft -q

MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend venv/bin/python3 scripts/regression/reg_l3_skill_extract.py
./scripts/regression/run_regression.sh --suite framework
```

## 非目标

- 不把草案直接注册为生产 Skill
- 不调用额外 LLM 做高阶总结
- 不代表 self-upgrade E2E 已完成
- 不覆盖 A2A / 经验记忆持久化
