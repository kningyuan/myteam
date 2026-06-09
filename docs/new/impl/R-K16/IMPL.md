# R-K16 Recurring 外部调度 — 实现说明

| 字段 | 内容 |
|------|------|
| 需求 ID | R-K16 |
| 状态 | ✅ 已完成 |
| 日期 | 2026-06-09 |

## 交叉评审共识

| 角色 | 裁决 |
|------|------|
| 架构师 | 不在 Hub 内建常驻 scheduler；提供 System Kernel 级无状态 trigger，供 cron/webhook bridge 调用 |
| QA | CHECK_ONLY 验证 payload/CLI 参数会触发 `run_project(mode="recurring")`；不宣称真实 cron daemon 已部署 |
| 工程 | 新增 `common.recurring_trigger`，默认每次外部触发只跑 `max_cycles=1`，避免一次 cron 调用占用过久 |

## 背景

R-K13 已覆盖内核内部 recurring 循环；R-K16 补的是外部入口：让 cron、CI 或 webhook bridge 能在不依赖 Hub 的情况下触发一次 recurring tick。

## 验收

- [x] JSON payload / CLI 参数可归一为 run_project 参数
- [x] 默认 `mode="recurring"`、`max_cycles=1`
- [x] 支持 `budget` / `token_budget`、`workflow`、`backend`、`review`、`split`
- [x] `test_recurring_trigger.py` PASS
- [x] `reg_k16_recurring_trigger.py` PASS

## 改动文件

- `backend/common/recurring_trigger.py`
- `backend/common/tests/test_recurring_trigger.py`
- `scripts/regression/reg_k16_recurring_trigger.py`
- `scripts/regression/run_regression.sh`

## 使用方式

Cron 示例：

```bash
MYTEAM_ROOT=/path/to/myteam PYTHONPATH=/path/to/myteam/backend \
  /path/to/myteam/venv/bin/python3 /path/to/myteam/backend/common/recurring_trigger.py \
  --project-id weekly-review --goal "每周复盘并提出改进" --max-cycles 1 --backend claude
```

Webhook bridge 示例：

```bash
echo '{"project_id":"webhook-review","goal":"处理外部反馈","max_cycles":1}' |
  MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
  venv/bin/python3 backend/common/recurring_trigger.py --payload -
```

## 回归

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/tests/test_recurring_trigger.py -q
MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend venv/bin/python3 scripts/regression/reg_k16_recurring_trigger.py
./scripts/regression/run_regression.sh --suite framework
```

## 非目标

- 不实现常驻 daemon
- 不解析 cron 表达式
- 不负责 webhook HTTP server
- 不承诺跨多次外部触发自动延续历史 cycle 编号；跨轮记忆仍由现有 memory / deliverable 机制演进
