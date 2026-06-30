# Loop 模块

循环运行时:recurring 模式的单轮调度与讨论循环。

## 核心文件

- `loop_runtime.py` — 循环运行时(recurring 单轮)
- `loop_discussion_dispatch.py` — 讨论循环调度(kernel 入口)
- `loop_discussion_runtime.py` — 讨论循环运行时(与 workflow 懒循环 R3)

## 依赖关系

依赖:common/process, common/workflow, common/business_hook_loader

> **注意**:循环依赖 R3:loop_discussion_runtime → workflow_collaboration(懒加载,跨 workflow 聚类)

## 测试

测试位于 `common/loop/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/loop/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_loop_runtime.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径