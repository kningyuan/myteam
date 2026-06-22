# research:t-research-01

> 自动沉淀自 ledger；供同类 execute 按需 Read。

task_id: t-research-01
task_type: research
intent: 单 agent execute harness 注入完整性调研
summary: |
  单 agent 可通过 single_execute.py 脱离 workflow 跑通 PRE/POST；
  PRE 注入 Skill+umbrella+偏好+references；KB 经验需 finish 后复利。
lesson:
  worked: |
    build_worker_prompt + execution_harness inject；
    product-methodology Pitfalls 强制列扫描路径；
    single_execute prepare/finish 可重复验证。
  failed: |
    L1 dm 记忆曾污染 execute prompt（tag 交集过宽，已修复）；
    memstack.enabled=false 时无 KB top-K。
pitfalls:
  - 勿把 interactive 群聊路径当作 execute 质量基线
  - 勿在未 finish POST 时期望「同类任务经验」块出现
  - registry skills 空时依赖 roster 回退，仍须在 Hub sync
sources:
  - backend/execution_harness/single_execute.py
  - tasks/single_agent/sa-q1/t-research-01/worker.prompt.txt
  - backend/common/agent_transport.py
  - backend/execution_harness/pre/inject.py
keywords:
  - single_execute
  - harness PRE
  - L1 scope
  - ledger distilled
