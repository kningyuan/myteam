# Store 模块

项目运行态 SQLite 真相源。与 config_store/(系统配置)职责不同。

## 核心文件

- `store.py` — Store 门面
- `store_backend.py` — 抽象后端
- `store_sqlite.py` — SQLite 实现
- `task_data_store.py` — 任务数据存储

## 依赖关系

依赖:common/paths。被依赖:common/process, common/project, common/agent

> **注意**:区别:config_store/ 存系统配置 JSON,本模块存项目运行态

## 测试

测试位于 `common/store/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/store/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_store.py`
- `test_store_backend.py`
- `test_store_concurrency.py`
- `test_v1_ops_store.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径