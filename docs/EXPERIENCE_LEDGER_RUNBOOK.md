# Experience Ledger → KB 操作手册（Q-1）

> 半自动经验沉淀：ledger 条目 → promote → 下次同 task_type 注入 hints

## 1. 写入 ledger

任务完成后，在 deliverables 目录放置 `ledger.entry.yaml`：

```yaml
task_id: t-deck
task_type: deck-build
lesson:
  worked: 先列 slide 大纲再填内容
  next_time: 检查 wps-deck probe 通过后再 build
```

## 2. Promote 到 KB

```python
from common.experience import promote_ledger_to_memory
from common.store import Store

store = Store()
ref = promote_ledger_to_memory(
    deliverables_dir,   # Path 到项目 deliverables
    project_id,
    task_id,
    task_type,
    store,
)
# ref 形如 kb://...
```

CLI 等价：任务 hook 或 Hub resume 后由 `experience.py` 在合适节点调用。

## 3. 验证 hints 注入

```bash
cd myteam
venv/bin/python3 -m pytest backend/common/tests/test_experience.py -q
```

第二次同 `task_type` RUN 时，`agent_transport` 会在 execute prompt 追加：

```
【同类任务经验（参考，勿照抄）】
- ledger: ...
```

## 4. REG KPI（CHECK_ONLY）

在 REG 脚本中可 mock 计数 `experience_hints_applied`（见 `reg_workflow_common.py` 扩展位）。

## 5. 人工边界

- Skill 正文仍由人维护；ledger 只补「上次教训」
- 不自动改 SKILL.md 或 workflow
