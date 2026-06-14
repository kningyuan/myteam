# P3 回归测试报告

> **日期**：2026-06-14  
> **Workflow v3**：P3.5 Gate（端口化文档 + API Wave 4）  
> **触发变更**：P3.1 API 拆分 Wave 4（workflows/jobs/workspace_events）、端口化文档、codex/cursor stub adapter、skill_config 测试 patch 修正

## 执行命令与结果

| 套件 | 命令 | 结果 |
|------|------|------|
| 全量单元 | `pytest backend/common/tests -q` | **594 passed**, 0 failed, 1 warning |
| 回归 unit | `bash scripts/regression/run_regression.sh --suite unit` | **116 passed**, Phase 1 PASS |
| E2E 双跑基线 | `venv/bin/python3 scripts/regression/reg_platform_v3_e2e_baseline.py` | **8 passed × 2 runs**, consistent=true, PASS |

环境：`PYTHONPATH=backend`，`MYTEAM_ROOT=<repo root>`。

## 变更覆盖

- `docs/ARCHITECTURE-PORTS.md` — 统一端口框架对照表与 Registry/DI 模式
- `docs/ARCHITECTURE.md` §9 — 前后端分工与端口化（引用 ARCHITECTURE-PORTS）
- `routes/workflows.py` — PGD workflow CRUD + suggest
- `routes/jobs.py` — job 列表/详情
- `routes/workspace_events.py` — 事件列表 + SSE stream
- `adapters/stub_cli.py` + `adapters/__init__.py` — codex/cursor registry stub
- `common/agent_transport.py` — `_default_adapter` 经 registry 解析
- `test_skill_config_api.py` — monkeypatch 目标改为 `hub.api.routes.config`

## Gate 判定

| 项 | 阈值 | 实际 | 状态 |
|----|------|------|------|
| pytest 0 failed | 0 | 0 | ✅ |
| unit regression | PASS | PASS | ✅ |
| E2E 双跑一致 | consistent | true | ✅ |
| E2E 通过率 | 100% | 8/8 | ✅ |

## 已知警告

- `StarletteDeprecationWarning`：`httpx` vs `httpx2`（TestClient 依赖，非本次回归阻塞项）

## 结论

**P3.5 回归 Gate：PASS** — API Wave 4 路由提取与端口化文档未引入契约回归；全套件 594 + 116 unit + 8 E2E 全绿。
