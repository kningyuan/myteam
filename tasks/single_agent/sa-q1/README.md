# sa-q1 — 单 Agent execute 实测批次

> 不经过 Workflow；runner: `backend/execution_harness/single_execute.py`

| task_id | 状态 | 交付物 | 备注 |
|---------|------|--------|------|
| t-research-01 | ✅ finish | `deliverables/t-research-01_deliverable.md` | T2 research 基线；POST → KB + reference |
| t-research-02b | prepare only | — | 验证第二次 prompt 含「同类任务经验」 |

## 复现

```bash
cd myteam
PYTHONPATH=backend python backend/execution_harness/single_execute.py prepare \
  --project sa-q1 --task t-research-01 --agent product --task-type research \
  --intent "…"
# 编辑 deliverable + ledger 后
PYTHONPATH=backend python backend/execution_harness/single_execute.py finish \
  --project sa-q1 --task t-research-01 --agent product --task-type research
```

详细记录：[AGENT_CAPABILITY_ITERATION_LOG.md §I-08](../../docs/AGENT_CAPABILITY_ITERATION_LOG.md#i-08-单-agent-execute-实测t2)
