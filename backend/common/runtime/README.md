# Runtime 模块

kernel 入口与配置:run_kernel.py 是 CLI 入口,kernel_config 是配置中心。

## 核心文件

- `run_kernel.py` — CLI 入口(Python -m common.runtime.run_kernel)
- `kernel_config.py` — kernel 配置中心
- `kernel_project_hooks.py` — 项目钩子加载
- `business_hook_loader.py` — 业务钩子加载器
- `goal_template.py` — 目标模板
- `workspace_gc.py` — workspace 垃圾回收

## 依赖关系

依赖:common/process, common/agent, common/project, common/store

## 测试

测试位于 `common/runtime/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/runtime/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_kernel_config.py`
- `test_kernel_run.py`
- `test_recovery.py`
- `test_run_kernel.py`
- `test_workspace_gc.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径