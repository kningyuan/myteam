# Experience Layer

任务结束后，Agent 在交付物目录写入 `ledger.entry.yaml`，供后续同类任务参考。

- **Schema**：`schema/ledger.entry.yaml`（字段说明与示例）
- **写入时机**：ALL 的 Learn 阶段，与 `submit_result` 之前
- **范围**：单任务一条；不替代项目级 `business/tasks/` 状态

Kernel 不解析 ledger；Gate 仅做 `file_exists` 校验（试点 task_type）。
