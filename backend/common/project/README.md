# Project 模块

项目生命周期管理:启动、运行、产物、取消、钩子。

## 核心文件

- `project_runtime.py` — 项目运行时入口
- `project_admin.py` — 项目管理(创建/查询/删除)
- `project_artifacts.py` — 项目产物管理
- `project_cancel.py` — 项目取消(与 agent_port 懒循环 R1)
- `project_hooks.py` — 项目钩子(纯 dataclass 回调抽象)
- `job_supervisor.py` — 作业监督

## 依赖关系

依赖:common/agent(agent_port), common/store

> **注意**:循环依赖 R1:project_cancel → agent_port(懒加载,跨 agent 聚类)

## 测试

测试位于 `common/project/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/project/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_project_admin.py`
- `test_project_artifacts.py`
- `test_project_service.py`
- `test_projects_api.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径