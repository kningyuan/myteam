# Phase 0 · 现状脆弱点清单（Findings Note）

> 实现阶段排期的「决策门」产物（不改逻辑）。逐项给出**脆弱点 → 代码位置 → 触发条件 → 对应决策**。
> 验证标准（D 计划 Phase 0）：能列出每处脆弱点对应的代码位置与触发条件。✅

本次审计基于代码静态走查（未做完整 live run，因 live run 依赖 opencode CLI + workspaces 实跑）；
所有位置已逐一核对行号。

---

## F1 · JSON 抢救（contract 松）—— 框架在「修」Agent 的非法输出

| 项 | 内容 |
|---|---|
| 位置 A | `skill/team/agent-notify/scripts/notify_agent.py` · `_write_response_file`（468–551） |
| 位置 B | `skill/team/task-executor/scripts/executor.py` · `state_execute_task` 内（1136–1168） |
| 触发 | Agent 在聊天里返回自然语言/半结构化文本，而非把合法 JSON 写进 `.response` |
| 现象 | A：全角引号→半角、markdown 围栏剥离、平衡花括号截取、`{"raw_response": content}` 兜底；B：`raw_response`/`runId` 分支用正则从文本里猜 `deliverable_path`，补 `status/phase/task_id` |
| 风险 | 框架替 Agent 猜测意图 → 误判完成、把失败当成功；契约形同虚设 |
| 决策 | D1（短板=契约松）、D11（submit_result 本地校验后才写回，消灭抢救）、D12（混合取回） |

---

## F2 · 格式定义分散（同一约束有 4 处出处）

| 出处 | 位置 |
|---|---|
| task_type→章节提示（硬编码 prompt） | `executor.py` · `state_task_plan`（388–399 的 agent→task_type 映射 + 400–412 的 expected_format） |
| 交付物模板 + 校验规则 | `skill/team/templates/templates.yaml`（research/seo-plan/content/test-plan/code-deliverable/strategy/publish-post） |
| 通用默认校验值 | `common/validator.py` · `validate_output`（min_length/required_sections/required_elements/must_include/format） + `state_execute_task` 默认 `{min_length:200,...}`（≈1210–1217） |
| 门禁规则读取 | `common/quality_gate.py` · `read_standards`（本地 templates → gbrain 回退） |
| 触发 | 改一个 task_type 的章节/字数要求需要同时改多处，极易漂移 |
| 决策 | D10-D（templates.yaml 上移为框架「格式注册表」，单一出处）、D11（结构进代码、约束进配置）、D14/D15 |

---

## F3 · 质量与格式混淆（门禁越权判「好坏」）

| 项 | 内容 |
|---|---|
| 位置 | `common/quality_gate.py` · `check`（290–400）：`min_length`（333–344）、`must_include`（370–377）与 `required_sections`/`section_level`/`file_exists`/`evidence_url` 混在同一确定性门禁 |
| 触发 | 任意 execute 后的门禁调用 |
| 风险 | `min_length`/`must_include` 是「内容质量」代理指标，却作为**阻塞性**确定性门禁；与 D14「框架只判契约/格式/完整性，质量归 Agent」冲突 |
| 决策 | D14（min_length 降为「防 stub 下限」、must_include 移出默认关；acceptance_criteria 给自评+评审）、D15（按 outcome_kind 取规则） |

---

## F4 · 存活性判定 = 固定总超时（非事件心跳）

| 项 | 内容 |
|---|---|
| 位置 | `common/config.py`（ACK_TIMEOUT=300 / TASK_TIMEOUT=3600 / EXECUTE_TIMEOUT=3600 …）；`executor.state_execute_task` 用 `task_timeout_sec = timeout_minutes*60` 做 deadline（≈1122–1126） |
| 触发 | 长任务（>超时）被误杀；真卡死则要等满超时才发现 |
| 决策 | D7（事件心跳 + 看门狗 soft/hard 取代固定总超时）、D12（两段式 soft_idle/hard_idle） |

---

## F5 · 文件即真相 + 残留治理薄弱（`.trigger`/`.response`）

| 项 | 内容 |
|---|---|
| 位置 | `state_task_plan` 直接 `json.dump` 写 `.request`（416–417）并轮询 `.response`（427–460）；`find_response_file` 用 `min_mtime` 过滤（`common/response_finder.py`）；`_write_response_file` 多命名格式扫描（482–498） |
| 触发 | 进程崩溃/重复投递/旧响应残留 → 状态无单一真相，靠 mtime + 文件名启发式 |
| 风险 | 无 ACID、可能半截写、重复采纳旧文件 |
| 决策 | D8（原子写 + 任务状态机 + 幂等 + 恢复）、D12（interaction_id 命名 + mtime 晚于请求 + 启动 GC）、D13（SQLite 真相库；文件退为缓存/产物） |

---

## F6 · 双引擎重复 + 薄测试

| 项 | 内容 |
|---|---|
| 位置 | `task-executor/scripts/executor.py`（1660 行）与 `continuous-executor/scripts/engine.py` 形态重复；`task-dispatch`/`task-queue` 另有调度 |
| 测试 | 全仓仅 4 个 `test_*.py`：`common/tests/test_quality_gate.py`、`test_cross_review.py`、`task-executor/tests/test_executor.py`、`continuous-executor/tests/test_engine.py` |
| 决策 | D10（合并单内核 + 模式配置）、D18（失败语义）、Phase 8（补集成测试 + 每信封契约测试） |

---

## F7 · 机制被打包成 skill 并用 subprocess 互调

| 项 | 内容 |
|---|---|
| 位置 | `executor.py` 通过 `_run_script`/`_notify_agent` 调 `project-data/scripts/project_data.py`、`agent-notify/scripts/notify_agent.py` 等子进程；`bridge/myteam_notify.py` 再 HTTP 调 Hub |
| 风险 | 进程边界多、错误归一难、计量/取消/心跳无处统一沉淀 |
| 决策 | D2（机制进代码、能力做 skill）、D8（工业机制统一沉到 AgentPort）、D10-A（上移为 backend 内核） |

---

## 实现顺序确认（接 D 计划）

契约(F1/F2) → 存储(F5) → 端口(F4/F7) → 门禁(F2/F3) → 流程(F6) → 记忆 → 可观测 → 收尾(F6)。

Phase 1 首先消灭 F1（JSON 抢救）：引入 `contracts.py`（Pydantic 信封）+ `submit_result`（Agent 侧本地校验后原子写）+ `validator` 反序列化进契约模型；旧抢救路径置于迁移开关后，可回退。

*创建：实现阶段 Phase 0*
