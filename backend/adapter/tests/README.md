# Adapter 测试

`backend/adapter/tests/` 覆盖 adapter CLI 隔离层:parser 解析、命令行构建、模型列举、MCP/Skill 同步,以及前后端接口契约。所有测试**不依赖外部 CLI**(opencode/claude 未安装亦可跑),用 `tmp_path` 隔离工作区、`monkeypatch` 替换 CLI 探测 / `subprocess.run` / `load_mcp_registry`。

## 运行方式

```bash
# 全量(10 文件,42 用例)
PYTHONPATH=backend python3 -m pytest backend/adapter/tests/ -q

# 单文件
PYTHONPATH=backend python3 -m pytest backend/adapter/tests/test_opencode_mcp_sync.py -q
```

> 仓库根 `AGENTS.md` 规定 `PYTHONPATH=backend` 必填(adapter 包以 `adapter.` 绝对导入)。`run.sh` / 顶层 pytest 也已设此路径。

## conftest 说明

`conftest.py` 仅做 `sys.path` 注入:把 `backend/`(`parents[2]`)幂等插入 `sys.path`,保证 `import adapter.*` / `import common.*` / `import config_store.*` 可用。各测试文件顶部亦各自 `sys.path.insert` 做双保险(深度变化后仍幂等)。**无共享 fixture**,每个测试文件自带 `@pytest.fixture()`。

## 测试清单(10 文件,42 用例)

| # | 文件 | 用例数 | 覆盖内容 |
|---|------|--------|----------|
| 1 | `test_opencode_parser.py` | 3 | opencode NDJSON 解析:`tool_use` 捕获 input+state.output、无 output 仍解析、error 事件多层消息提取 |
| 2 | `test_opencode_models.py` | 2 | `OpenCodeAdapter.list_models`:动态 `opencode models` 解析+默认标记、CLI 失败回退静态模型 |
| 3 | `test_opencode_skill_sync.py` | 4 | opencode Skill 软链:挂载 desired、清理 stale、报告 missing、`adapter.sync_agent_skills` 通路 |
| 4 | `test_opencode_mcp_sync.py` | 5 | opencode MCP 同步:写 `opencode.json`(local command+environment / remote type+url+headers)、报告 missing/disabled、保留已有 `$schema`、写 manifest、`adapter.sync_agent_mcp` 通路 |
| 5 | `test_claude_parser.py` | 8 | claude stream-json 解析:assistant.usage 增量 STEP_FINISH、result 累积 STEP_FINISH、token 累加公式 B、result 行补 TEXT、无 total_tokens 回退、thinking→REASONING、thinking+text 双发、累积 max 覆盖增量 |
| 6 | `test_claude_adapter.py` | 3 | claude 命令行构建:rules+`.mcp.json`+`--setting-sources` 注入、`_runtime_settings_json` 含用户 env、无可选 flag 时不注入 |
| 7 | `test_claude_models.py` | 3 | `_merge_claude_models`:内置别名+完整 id、config 扩展不替目录、config 空时用目录 |
| 8 | `test_claude_mcp_sync.py` | 3 | claude MCP 同步:写 `.mcp.json`(local command+args / remote type:http+url)、报告 missing/disabled、`adapter.sync_agent_mcp` 通路 |
| 9 | `test_claude_skill_sync.py` | 4 | claude Skill 软链:挂载 desired、清理 stale、报告 missing、`adapter.sync_agent_skills` 通路 |
| 10 | `test_api_contract.py` | 7 | 前后端接口契约形状(防代码/契约/前端三方漂移):项目总览全集、title 兜底、群列表 last_message_at、摘要 totals、错误信封 error.message、真实 app MRO 优先级、续跑 run-status 标记 |

## 缺失项说明

- **已补齐**:`test_opencode_mcp_sync.py` 原为缺失项(opencode MCP 同步无测试,而 claude 侧有 `test_claude_mcp_sync.py`),现已新增,覆盖 `sync_workspace_mcp` 全路径 + `adapter.sync_agent_mcp` 通路。
- **`core/` 抽象层无独立测试目录**:`events` / `protocol` / `registry` / `sse` / `subprocess_cli` 由各 adapter 测试间接覆盖(如 `test_*_parser` 覆盖 `AgentEvent`/`EventKind`,`test_*_adapter` 覆盖 `RunRequest`/`CLIAdapter`/registry side-effect 注册),`SubprocessCLIAdapter` 的进程组回收/cancel 看门狗经 `common/tests/test_integration.py` 全链路间接验证。`sse.encode_*` 与 `registry.list_models_all` 目前无直接断言——若要直接测 `SubprocessCLIAdapter` 的 cancel/进程组回收,需起真实子进程,暂未单测。

## 变更维护

- **新增 CLI 后端**:补 `test_<cli>_parser.py` + `test_<cli>_adapter.py`(参照 opencode/claude);若有 MCP/Skill 同步,补 `test_<cli>_mcp_sync.py` / `test_<cli>_skill_sync.py`;更新本清单。
- **改 parser 行格式**:补对应 `test_<cli>_parser.py` 用例。
- **改 MCP/Skill entry 格式**:补对应 `test_<cli>_*_sync.py` 用例(注意 opencode 与 claude 的格式差异,见各自 README)。
- **改接口契约字段**:`test_api_contract.py` 用全集断言(`==` 而非 `in`),改前端消费字段须先改契约 + 测试,强制走变更登记。
