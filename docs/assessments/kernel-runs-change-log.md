# _KERNEL_RUNS 治理变更日志（修正项 6）

> **状态**：已在代码层完成（2026-06-14）  
> **Workflow v3**：P3.1 附带修复提前落地

## 问题

Hub 使用进程内 `_KERNEL_RUNS: dict` 缓存项目运行态，Hub 重启后与 Store 真相可能不一致，产生 ghost `running=true`。

## 变更

| 项 | 说明 |
|----|------|
| 新增 | `backend/hub/services/kernel_run.py` — 仅读写 `project.meta.hub_kernel_run` |
| 删除 | `server.py` 内 `_KERNEL_RUNS` 内存 dict |
| 保留 | `ProjectRuntime` + `JobSupervisor` 调度线程；`_reconcile_stale_kernel_runs()` 于 Hub 启动清理残留 |

## 验证

- `backend/common/tests/test_kernel_run.py`（6 项）
- `backend/common/tests/test_platform_e2e_baseline.py::test_kernel_run_meta_get_set`
- `backend/common/tests/test_projects_api.py` / `test_api_contract.py` 已迁移

### 验证步骤（P3 Gate 可复现）

```bash
cd /path/to/myteam
export PYTHONPATH=backend MYTEAM_ROOT=$PWD

# 1. kernel_run 单元
venv/bin/python3 -m pytest backend/common/tests/test_kernel_run.py -q

# 2. 项目 API 与 kernel 标记交互
venv/bin/python3 -m pytest backend/common/tests/test_projects_api.py -q

# 3. E2E 双跑（含 test_kernel_run_meta_get_set）
venv/bin/python3 scripts/regression/reg_platform_v3_e2e_baseline.py

# 4. 全量回归
venv/bin/python3 -m pytest backend/common/tests -q
```

**期望**：0 failed；E2E `consistent: true`；Hub 重启后 `_reconcile_stale_kernel_runs` 清除 ghost `running=true`（见 `test_kernel_run.py::test_reconcile_stale`）。

## Gate（P3-G5 / P4-6）

- Hub 重启后无 ghost `running=true`：由 `_reconcile_stale_kernel_runs` + Store-only 读写保证
- 回归：`pytest backend/common/tests -q` 全绿
