# Recurring 持续运营

> **版本**：2026-06-11  
> 见 [V1_CAPABILITY_PLAN.md](./V1_CAPABILITY_PLAN.md) Phase 3。

---

## Workflow

使用 `媒体持续运营` workflow，启动时指定 recurring：

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

venv/bin/python3 backend/common/run_kernel.py media-week-1 \
  --workflow 媒体持续运营 \
  --mode recurring \
  --max-cycles 3 \
  --goal "本周知乎专栏：myteam 协作框架入门" \
  --budget 500000 \
  --backend claude
```

---

## 外部调度（cron / launchd）

每次 tick 调用 `recurring_trigger.py`（与 Hub 解耦）：

```bash
venv/bin/python3 backend/common/recurring_trigger.py \
  --project-id media-week-1 \
  --goal-file business/workflows/tier-l3-free-goal.txt \
  --max-cycles 1
```

---

## 运营日志

任务完成后自动写入（`common/ops_log.py`）：

| 表 | 触发 task_type |
|----|----------------|
| `publish_log` | `publish-post` |
| `audit_log` | `geo-audit`, `geo-verification` |

查询示例：

```sql
SELECT * FROM publish_log WHERE project_id='media-week-1' ORDER BY id DESC;
```

---

## 7 天试跑 KPI

记录文件：`business/regression/recurring_week.json`（LIVE 试跑后填写）

```json
{
  "project_id": "media-week-1",
  "started": "2026-06-11",
  "total_ticks": 7,
  "completed_ticks": 5,
  "notes": "≥5/7 即 Phase 3 过关"
}
```

---

## REG

```bash
REG_CHECK_ONLY=1 python3 scripts/regression/reg_p1_media_ops.py
REG_K16_CHECK_ONLY=1 python3 scripts/regression/reg_k16_recurring_trigger.py
```
