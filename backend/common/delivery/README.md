# Delivery 模块

交付物保证:模板、scaffold、提交校验。submit_result 是 kernel 写回 .response 的唯一入口。

## 核心文件

- `submit_result.py` — 提交校验(本地原子校验后写 .response,无 rescue 路径)
- `deliverable_guarantee.py` — 交付物保证(scaffold markdown)
- `deliverable_meta.py` — 交付物元数据
- `delivery_templates.py` — 交付模板
- `delivery_template_store.py` — 模板存储
- `delivery_profiles.py` — 交付配置档

## 依赖关系

依赖:common/paths, common/contracts

## 测试

测试位于 `common/delivery/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/delivery/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_deliverable_guarantee.py`
- `test_delivery_profiles.py`
- `test_delivery_templates.py`
- `test_outcome_forms.py`
- `test_submit_dispatch_gate.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径