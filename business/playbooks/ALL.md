# ALL — Align · Launch · Learn

每个 **execute** 任务（B 层交付）须按本 playbook 留下可追溯过程产物，再交卷。

## 流程

```text
Align  →  Launch  →  Learn
align.md   plan.md + 执行 + verify.log   ledger.entry.yaml
```

| 阶段 | 产物 | 说明 |
|------|------|------|
| **Align** | `align.md` | 理解任务：对象、输入、成功标准、约束 |
| **Launch** | `plan.md` | 方案：从 catalog 自选的 Skill/means、探针、回退 |
| **Launch** | 业务交付物 | 按 task_type 注册表与所选 Skill playbook 执行 |
| **Launch** | `verify.log` | 探针与 verify 脚本的命令、退出码、关键输出 |
| **Learn** | `ledger.entry.yaml` | 一条可复用经验（见 `business/experience/schema/ledger.entry.yaml`） |

## 目录约定

过程产物与 **deliverable Markdown、业务文件** 同目录（交付物目录 `DELIV`）：

```text
  DELIV/
  align.md
  plan.md
  verify.log
  ledger.entry.yaml
  trace.manifest.yaml
  <task_id>_deliverable.md
  …业务文件（如 diagram.drawio、diagram.png）
```

可用 **`business/playbooks/scripts/scaffold_process.sh "$DELIV"`** 复制 ALL 过程模板（align/plan/ledger/trace/verify.log）。

## Align（align.md）

须回答：

1. **对象**：本步要交付什么（读者、用途）
2. **输入**：上游 task / 文件 / 约束
3. **成功标准**：Gate 会检查什么（章节、文件、探针）
4. **非目标**：明确不做什么

## Launch（plan.md）

须包含：

1. **chosen_skills**：从 `business/skills/catalog.yaml` 按 `task_type` 筛选后选定的条目（可多条）
2. **means**：具体手段（如 `brief_to_drawio`、手写 `.drawio`）
3. **probes**：执行前/后运行的脚本（如 `probe.sh`、`verify_*.py`）
4. **fallbacks**：探针失败时的备选路径

Workflow **不得**写死 Skill 路径；自选结果只写在 `plan.md`。

## verify.log

追加记录每次探针/校验，格式示例：

```text
=== 2026-06-10T12:00:00 probe.sh ===
exit=0
OK draw.io CLI: /Applications/draw.io.app/Contents/MacOS/draw.io

=== 2026-06-10T12:05:00 verify_diagram.py ===
exit=0
diagram.drawio + diagram.png OK
```

## Learn（ledger.entry.yaml）

任务结束后写 **一条** 经验：什么有效、什么失败、下次建议。schema 见 `business/experience/schema/ledger.entry.yaml`。

## 与 A / B 的关系

- **A（Team Run）**：DAG、Gate、状态；不指定具体 Skill。
- **B（Agent Delivery）**：Agent 读本 playbook + catalog + task_type router Skill，完成 ALL 与业务交付。
