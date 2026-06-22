## 1. 契约与门禁

- [x] 1.1 新增 `PlanResult`、`PlanResponse` 契约（contracts.py）
- [x] 1.2 新增 `check_plan()` 轻量门禁（gate.py）
- [x] 1.3 `Kind` 加 `"plan"` 辨识联合

## 2. 重试策略升级（路径 D）

- [x] 2.1 失败模式分类模块（post/failure_patterns.py）
- [x] 2.2 Gate 反馈 → 分类摘要 + 可操作指引（task_pipeline.py）
- [x] 2.3 Agent 侧结构化 retry 反馈显示（agent_transport.py）

## 3. 经验教训回授闭环（路径 B）

- [x] 3.1 Lesson 写入模块（post/lesson.py）
- [x] 3.2 PRE 教训注入模块（pre/lesson_inject.py）
- [x] 3.3 共享 YAML 解析器（post/_yaml_util.py）
- [x] 3.4 POST 集成 lesson 写入（facade.py）
- [x] 3.5 PRE 集成 lesson 注入（pre/inject.py）
- [x] 3.6 配置开关（config.py）

## 4. Plan-then-Execute（路径 A）

- [x] 4.1 Plan prompt 构建（agent_transport.py）
- [x] 4.2 `run_plan()` 预执行交互 + plan 存入 task meta（task_pipeline.py）
- [x] 4.3 Execute prompt 注入 plan 块（agent_transport.py）
- [x] 4.4 `plan_enabled` 配置开关（process_types.py）

## 5. Agent 质量画像（路径 C）

- [x] 5.1 质量记录模块（post/quality.py）
- [x] 5.2 Quality 写入 task 完成回调（task_pipeline._record_quality）
- [x] 5.3 Team_config 质量注入（decision_pipeline._quality_team_hint）

## 6. 测试与验证

- [x] 6.1 单元测试：29 项契约/Gate/Lesson/Quality 测试
- [x] 6.2 集成测试：39 项核心测试通过
- [x] 6.3 端到端实测：run_kernel.py 真实 Claude API 调用验证
  - Plan 确认：5 个真实任务通过 check_plan
  - Quality 确认：5 条质量记录写入 KB
  - Lesson 确认：任务一次通过无需 retry（预期行为）