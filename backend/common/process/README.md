# Process 模块

编排内核状态机:DAG 调度、决策管线、计划扩展与任务执行。kernel 的心脏。

## 核心文件

- `process.py` — Process 状态机(kernel 心脏):DAG schedule/failure/retry/triage
- `process_types.py` — 进程数据类型(ProcessConfig/TaskOutcome)
- `dag_dispatch.py` — DAG 调度(并行波次)
- `decision_pipeline.py` — 决策管线
- `task_pipeline.py` — 任务执行管线
- `plan_expansion.py` — 计划扩展
- `plan_gate.py` — 计划校验
- `plan_splice.py` — 子任务拼接
- `notify_format.py` — 通知格式化

## 依赖关系

依赖:common/agent(agent_port), common/store, common/gate, common/delivery

## 测试

测试位于 `common/process/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/process/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_dag_dispatch.py`
- `test_decision_pipeline.py`
- `test_plan_expansion.py`
- `test_plan_gate.py`
- `test_process.py`
- `test_process_loops.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径