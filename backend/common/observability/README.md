# Observability 模块

可观测性:事件记录、审计日志、token 用量、ops 日志、thinking trace。

## 核心文件

- `observability.py` — 可观测性主入口(record_event)
- `audit_log.py` — 审计日志
- `token_usage.py` — token 用量统计
- `ops_log.py` — ops 日志
- `thinking_trace.py` — thinking trace
- `hub_operation_meta.py` — hub 操作元数据

## 依赖关系

依赖:common/paths, config_store/system_config

## 测试

测试位于 `common/observability/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/observability/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_audit_log.py`
- `test_hub_operation_meta.py`
- `test_observability.py`
- `test_observability_api.py`
- `test_token_usage.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径