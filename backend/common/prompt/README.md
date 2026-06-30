# Prompt 模块

提示词组装、注入、模板、上下文装配。

## 核心文件

- `prompt_composer.py` — 提示词组装
- `prompt_injections.py` — 提示词注入块
- `prompt_templates.py` — 提示词模板
- `context_assembler.py` — 上下文装配

## 依赖关系

依赖:common/paths

## 测试

测试位于 `common/prompt/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/prompt/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_prompt_injections.py`
- `test_prompt_templates.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径