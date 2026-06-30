# Agent 模块

Agent 交互生命周期、传输层、注册与技能挂载。是 kernel 与 CLI 适配层之间的桥梁。

## 核心文件

- `agent_port.py` — 交互生命周期中心:watchdog/idempotency/token metering,被 process 强依赖
- `agent_transport.py` — worker prompt → CLI 子进程 → AgentEvent 的传输层
- `agent_registry.py` — agent 扫描与注册(读 agents_config.json)
- `agent_skills.py` — 技能挂载到 agent workspace
- `agent_mcp.py` — MCP 服务挂载到 agent
- `agent_model.py` — 模型配置解析(backend/model 映射)
- `agent_execution.py` — 执行锁(防并发)
- `agent_bootstrap.py` — agent 初始化引导
- `agent_id_policy.py` — agent ID 策略
- `agent_task_type_suggest.py` — agent 任务类型建议
- `adapter_mcp_registry.py` — MCP 适配注册
- `adapter_skill_registry.py` — 技能适配注册

## 依赖关系

依赖:common/paths, common/contracts, common/store, common/gate, adapter/

> **注意**:循环依赖 R1:agent_port ↔ project_cancel(跨 project 聚类,懒加载)

## 测试

测试位于 `common/agent/tests/`,运行:

```bash
PYTHONPATH=backend venv/bin/python3 -m pytest backend/common/agent/tests/ -q
```

测试清单(与 `tests/` 目录实际文件一一对应,功能变更后同步更新):

- `test_agent_capability_iteration.py`
- `test_agent_delivery.py`
- `test_agent_execution_lock.py`
- `test_agent_id_policy.py`
- `test_agent_memory.py`
- `test_agent_model.py`
- `test_agent_port.py`
- `test_agent_skills.py`
- `test_agent_skills_strict.py`
- `test_agent_task_type_suggest.py`
- `test_agent_transport.py`
- `test_agents_md_mount_strip.py`
- `test_apply_model.py`
- `test_build_skill_context_description.py`

## 变更维护

- 新增/删除文件时,更新本 README 的「核心文件」清单
- 新增/删除测试时,重跑 `python3 _gen_readme.py` 同步「测试清单」
- 重命名模块时,同步更新依赖方的 import 路径