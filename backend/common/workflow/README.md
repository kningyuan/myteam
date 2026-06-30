# Workflow 模块

工作流加载、校验、建议、协作。从 business/workflows/ 读取声明式工作流定义。

## 核心文件

- `workflow_loader.py` — 工作流加载(YAML → 内存模型)
- `workflow_validate.py` — 工作流校验
- `workflow_bootstrap.py` — 工作流引导
- `workflow_suggest.py` — 工作流建议
- `workflow_capability_bind.py` — 能力绑定
- `workflow_collaboration.py` — 工作流协作(与 loop 懒循环 R3)

## 依赖关系

依赖:common/paths, config_store/skill_config

> **注意**:循环依赖 R3:workflow_collaboration ↔ loop_discussion_runtime(懒加载,跨 loop 聚类)

## 测试

测试位于 `common/workflow/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/workflow/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_workflow_bootstrap.py`
- `test_workflow_capability_bind.py`
- `test_workflow_collaboration.py`
- `test_workflow_loader.py`
- `test_workflow_suggest.py`
- `test_workflow_template_id.py`
- `test_workflow_validate.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径