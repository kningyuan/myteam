# Roundtable 模块

圆桌讨论与群消息存储。多 agent 协作讨论的运行时。

## 核心文件

- `roundtable_runtime.py` — 圆桌运行时
- `roundtable_context.py` — 圆桌上下文
- `group_message_store.py` — 群消息存储

## 依赖关系

依赖:common/paths, base/group_manager

## 测试

测试位于 `common/roundtable/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/roundtable/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_group_mentions.py`
- `test_group_message_store.py`
- `test_group_roundtable.py`
- `test_roundtable_reliability.py`
- `test_roundtable_trace_persist.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径