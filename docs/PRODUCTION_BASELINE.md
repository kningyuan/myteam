# myteam 生产基线（REG / E2E）

> **版本**：2026-06-11  
> **用途**：所有 LIVE 回归与能力验收默认环境。见 [V1_CAPABILITY_PLAN.md](./V1_CAPABILITY_PLAN.md)。

---

## 1. 默认 Backend

| 级别 | Backend | 说明 |
|------|---------|------|
| **生产 / REG LIVE** | `claude` | 所有 Phase 1–3 LIVE REG 默认使用 |
| **Experimental** | `opencode` | P0 产品研发已试跑（`p0-opencode-trial`）；**不计入 v1 过关门禁** |
| **Hub UI 注意** | 与 agent 级 `agents_config.json` 一致 | 避免 UI 全局 backend 与 agent 配置不一致 |

验证 claude 可用：

```bash
which claude && claude --version
```

---

## 2. 环境变量（REG 通用）

```bash
export MYTEAM_ROOT="/path/to/myteam"
export PYTHONPATH="$MYTEAM_ROOT/backend"
cd "$MYTEAM_ROOT"
```

| 变量 | 默认 | 说明 |
|------|------|------|
| `REG_DEFAULT_BUDGET` | 见 `scripts/regression/reg_budget_defaults.py` | 各 REG 脚本可覆盖 |
| `REG_*_CHECK_ONLY=1` | — | 无 CLI，仅 loader/DB/KPI 检查 |
| `REG_*_RESUME=1` | — | 从 failed 任务 resume，不删 project |

---

## 3. 数据库与路径

| 路径 | 说明 |
|------|------|
| `business/tasks/state.db` | 运行态 SQLite（Phase 4 前唯一真相库） |
| `business/config/agents_config.json` | Agent backend/model（gitignore） |
| `business/tasks/project/<id>/deliverables/` | 人类可读交付物 |

---

## 4. REG 脚本索引（计划内）

| 脚本 | Phase | CHECK_ONLY |
|------|-------|------------|
| `reg_discuss_loop.py` | 1 | `REG_DISCUSS_CHECK_ONLY=1` |
| `reg_p0_product_dev.py` | 2 | `REG_CHECK_ONLY=1` |
| `reg_p1_media_ops.py` | 2 | `REG_CHECK_ONLY=1` |
| `reg_p2_pm_pack.py` | 2 | `REG_CHECK_ONLY=1` |
| `reg_p3_geo.py` | 2 | `REG_CHECK_ONLY=1` |
| `reg_l2_3role.py` | 已有 | `REG_L2_CHECK_ONLY=1` |
| `reg_k16_recurring_trigger.py` | 已有 | 内置 CHECK_ONLY |

未列出的脚本见 `scripts/regression/run_regression.sh`。

---

## 5. LIVE E2E 最低要求

- macOS 或 Linux，Python 3.11+（CI 用 3.13）
- `venv` 已安装依赖：`pip install -r requirements.txt`
- `claude` CLI 已登录且可用
- `business/config/agents_registry.json` 含 REG 所需 agent（通常 `main`、`product`、`research` 等）
- 首次运行前：`python3 scripts/bootstrap_business_roster.py`（若 workspace 缺失）

---

## 6. 失败处理

| 现象 | 动作 |
|------|------|
| 单任务 failed | `REG_*_RESUME=1` 或 Hub `/api/projects/{id}/resume` |
| Gate 反复失败 | 查 `deliverables/*_deliverable.md` 与 `run_event` |
| CLI timeout | 不切换生产基线到 opencode；记录 flaky，重跑 |
| budget paused | 提高 REG budget 或 `resume_project` |

---

## 7. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-11 | 初版：Claude 生产、OpenCode experimental |
