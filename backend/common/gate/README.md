# Gate 模块

门禁 + 注册表 + 任务类型 + 规则。gate 与 agent 共享同一 registry spec(下链=检查链)。

## 核心文件

- `gate.py` — 门禁:合约/格式/完整性校验
- `registry.py` — task_type spec 源(gate 与 agent 共享)
- `task_type_store.py` — 任务类型存储(与 task_type_suggest 懒循环 R2)
- `task_type_suggest.py` — 任务类型建议(与 task_type_store 懒循环 R2)
- `rules_merge.py` — 规则合并
- `shared_rules.py` — 共享规则
- `quality_suggest.py` — 质量建议

## 依赖关系

依赖:common/paths, common/contracts, config_store/system_config

> **注意**:循环依赖 R2:task_type_store ↔ task_type_suggest(懒加载,同目录内)

## 测试

测试位于 `common/gate/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/gate/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_failure_patterns_lesson.py`
- `test_gate.py`
- `test_rules_api.py`
- `test_rules_merge.py`
- `test_shared_rules.py`
- `test_task_type_store.py`
- `test_task_type_suggest.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径