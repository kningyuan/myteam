# myteam v1 能力达成计划

> **版本**：2026-06-11  
> **状态**：执行中（权威文档）  
> **原则**：先过关门禁，再进下一阶段；全部 Phase 过关 = 达成 v1 目标定义。

**关联文档**

| 文档 | 作用 |
|------|------|
| [PRODUCTION_BASELINE.md](./PRODUCTION_BASELINE.md) | 生产默认 backend、REG 环境 |
| [FRAMEWORK_BOUNDARY.md](./FRAMEWORK_BOUNDARY.md) | Kernel / Business 边界、Owner 决策 |
| [V1_ROADMAP.md](./V1_ROADMAP.md) | 业务 workflow 内容摘要（本计划为执行门禁 supersede） |
| [FRAMEWORK-FREEZE.md](./FRAMEWORK-FREEZE.md) | Kernel 封板范围 |

---

## 1. 目标定义（可验收）

v1 要证明 myteam 能支撑团队协作任务 **自动、稳定、正确、持续** 地进行。

| 维度 | v1 达成标准（可测） | 不承诺 |
|------|---------------------|--------|
| **自动** | Hub/CLI/`recurring_trigger` 一键启动；4 条 workflow + discuss 链有 REG；无需人工改 deliverable 才能 completed | LLM 每轮输出零瑕疵 |
| **稳定** | `pytest backend -q` 全绿；Claude REG 脚本 3 连 PASS；OpenCode 不在生产基线 | OpenCode 零超时 |
| **正确** | Gate + review 标记 + 每条 workflow 专属 REG；FAIL→讨论→PATCH→PASS 有独立 REG | 语义质量 100% 由 Gate 判定 |
| **持续** | 1 条 `mode: recurring` workflow；外部 trigger 7 天试跑 ≥5/7 completed；`publish_log`/`audit_log` 可查询 | 无人值守无限期零故障 |

**总验收句**：Phase 0→4 各阶段 **过关门禁全部 PASS** ⇒ 按上表定义达成 v1。

---

## 2. 现状评估（2026-06-11）

### 2.1 已证明

| 能力 | 证据 |
|------|------|
| Process + Gate + loop + resume + triage | `backend/common/tests/` 450+ pass |
| Work–Review 单链 | `tds-ch3-rerun2` → `REVIEW: PASS` |
| FAIL→PATCH→PASS（手工/半自动） | `tds-ch3-discuss-test/deliverables/verify.log` r2 PASS |
| L2 并行 REG | `scripts/regression/reg_l2_3role.py` archived PASS |
| Recurring 内核 + 外部 trigger | `reg_k16_recurring_trigger.py` |

### 2.2 未闭合

| 缺口 | 影响 |
|------|------|
| 无 `reg_discuss_loop.py` | 「正确」不可重复证明 |
| 4 条文档 workflow 缺失 / loader 测失败 | CI 非全绿 |
| 仅 2 条 workflow YAML 在盘 | P0–P3 业务未落地 |
| 群消息在 `groups.json`，非 DB | 审计/resume/Mac App 风险 |
| 无 publish/audit 表 | 「持续」不可查询 |
| OpenCode 生产未证明 | 稳定性方差大 |

### 2.3 多 Agent 共识（摘要）

- **product**：task_type/Skill 够；缺 workflow YAML 与运营持久化。
- **arch**：Kernel 不再大改；先统一存储，PostgreSQL 在 Phase 4 可选。
- **qa**：必须分层 REG；不过门禁不宣称「稳定/正确」。
- **main**：日常用 workflow DAG；战略用圆桌；FAIL 对齐用 loop hook。

---

## 3. 执行模型

```text
Phase N 任务清单 → 实现 → 过关门禁 → 更新 §8 进度表 → Phase N+1
                      ↑
              不过关则在本 Phase 内修复，不跳过
```

**协作讨论用法**

| 场景 | 机制 |
|------|------|
| 定计划 / 优先级 | `scripts/agent_roundtable_v1.py` 或 Hub 群聊（Phase 启动前） |
| FAIL 后定点对齐 | loop + `business/hooks/work_review_alignment.py` |
| 日常交付 | workflow DAG（非全员圆桌） |

---

## 4. Phase 0 — 基线可信

**周期**：约 1 周  
**目的**：CI 全绿、文档与实测一致、生产 backend 明确。

| ID | 任务 | 产出 |
|----|------|------|
| 0.1 | 补回或删除过时 workflow 引用 | `business/workflows/*.yaml` 与 `test_workflow_loader.py` 一致 |
| 0.2 | 修复 `test_resume_merges_workflow_description` | recovery 测全绿 |
| 0.3 | 修复其余 failing tests（bootstrap / task_type_store / hub_operation_meta / skill_extract 等） | 见 pytest 输出 |
| 0.4 | 更新 FRAMEWORK-FREEZE、FRAMEWORK_BOUNDARY 测试数 | 与 CI 一致 |
| 0.5 | 编写 [PRODUCTION_BASELINE.md](./PRODUCTION_BASELINE.md) | Claude = 生产；OpenCode = experimental |
| 0.6 | 文档化 TDS 第三章样板 | `business/workflows/README.md` 含复跑命令 |

### 过关门禁 0

```bash
cd myteam
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
venv/bin/python3 -m pytest backend -q
# 要求：0 failed
```

| 检查项 | 命令 / 标准 |
|--------|-------------|
| 全量单测 | `pytest backend -q` → 0 failed |
| 生产基线文档 | `docs/PRODUCTION_BASELINE.md` 存在 |
| Kernel 封板 | 本 Phase 无 Process/Gate 行为变更（仅 bugfix） |

**状态**：⬜ 未开始

---

## 5. Phase 1 — 讨论链可重复 REG

**周期**：约 1–2 周  
**目的**：FAIL→群讨论→PATCH→PASS 从「看过 verify.log」升级为自动化回归。

| ID | 任务 | 产出 |
|----|------|------|
| 1.1 | 新增 `scripts/regression/reg_discuss_loop.py` | CHECK_ONLY + LIVE 模式 |
| 1.2 | 基于 `第三章-讨论链路测试` workflow | project_id 可配置 |
| 1.3 | REG 断言：r1 FAIL、group_discussion.md、patch_list、r2 `REVIEW: PASS` | 脚本内 KPI |
| 1.4 | 纳入 `scripts/regression/run_regression.sh` | `business/regression/runs.jsonl` |
| 1.5 | hook 单测加强（patch_list 非空、ALIGN 解析） | `test_project_group_discussion.py` |
| 1.6 | **3 连跑** LIVE REG（防 flaky） | 3/3 PASS 记录 |

### 过关门禁 1

```bash
# 结构 / loader（无 CLI）
REG_DISCUSS_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
  python3 scripts/regression/reg_discuss_loop.py

# 全量 E2E（需 claude CLI，见 PRODUCTION_BASELINE.md）
MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
  python3 scripts/regression/reg_discuss_loop.py
# 连续 3 次 exit 0
```

| 检查项 | 标准 |
|--------|------|
| CHECK_ONLY | exit 0 |
| LIVE × 3 | exit 0；deliverables 含 `*-group_discussion.md` 与 r2 `REVIEW: PASS` |
| runs.jsonl | 有 `"script": "reg_discuss_loop"` 且 `"pass": true` |

**状态**：⬜ 未开始（依赖 Phase 0）

---

## 6. Phase 2 — 四条业务 workflow E2E

**周期**：约 3–4 周  
**目的**：P0–P3 声明式 workflow 均可 REG 证明。

| ID | Workflow 文件 | 任务链 | REG 脚本 |
|----|---------------|--------|----------|
| 2.1 | `business/workflows/产品研发.yaml` | requirements → arch(可选) → code → test → acceptance | `reg_p0_product_dev.py` |
| 2.2 | `business/workflows/产品经理交付.yaml` | product-planning → requirements → deck-build | `reg_p2_pm_pack.py` |
| 2.3 | `business/workflows/媒体持续运营.yaml` | research → content → publish-post | `reg_p1_media_ops.py` |
| 2.4 | `business/workflows/GEO持续优化.yaml` | content → geo-audit → geo-plan | `reg_p3_geo.py` |

每条 workflow 必须：

1. 通过 `test_workflow_loader` / plan_gate  
2. 有 `REG_*_CHECK_ONLY=1`（无 CLI）  
3. 有 LIVE 模式（Claude，budget 见 PRODUCTION_BASELINE）  
4. 有 `business/workflows/README-<名>.md` 说明  

**arch 节点（Owner）**：大需求方案 Gate + 实现 Gate；小需求/纯内容在 YAML 省略 arch task。

### 过关门禁 2

```bash
for reg in reg_p0_product_dev reg_p2_pm_pack reg_p1_media_ops reg_p3_geo; do
  REG_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
    python3 scripts/regression/${reg}.py || exit 1
done

# LIVE（逐条，需 claude）
for reg in reg_p0_product_dev reg_p2_pm_pack reg_p1_media_ops reg_p3_geo; do
  MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \
    python3 scripts/regression/${reg}.py || exit 1
done
```

| 检查项 | 标准 |
|--------|------|
| 4× CHECK_ONLY | 全部 exit 0 |
| 4× LIVE | project `status=completed`，`gate_failed=0` |
| L2 并行 REG 仍 PASS | `REG_L2_CHECK_ONLY=1 reg_l2_3role.py` |

**状态**：⬜ 未开始（依赖 Phase 1）

---

## 7. Phase 3 — 持续运营 MVP

**周期**：约 2 周  
**目的**：recurring + 外部调度 + 运营数据可查询。

| ID | 任务 | 产出 |
|----|------|------|
| 3.1 | `媒体持续运营.yaml` 设 `mode: recurring`，`max_cycles≥3` | 单进程多 cycle |
| 3.2 | 文档 `docs/RECURRING_OPS.md` | launchd/cron 调 `recurring_trigger.py` 示例 |
| 3.3 | Store 表 `publish_log`、`audit_log`（SQLite） | `store.py` migration |
| 3.4 | publish-post / geo-audit 完成时写 log | hook 或 task meta |
| 3.5 | **7 天试跑** | `business/regression/recurring_week.json` |
| 3.6 | REG 联合 | `reg_k16` + `reg_p1_media_ops` |

### 过关门禁 3

| 检查项 | 标准 |
|--------|------|
| recurring 3 cycles | 单项目 3 cycle 内 ≥2 completed（允许 1 次 triage 恢复） |
| 7 天试跑 | ≥5/7 tick → completed |
| publish_log | 每次 tick 有行，含 project_id、deliverable 路径、status |
| REG-K16 | PASS |

**状态**：⬜ 未开始（依赖 Phase 2）

---

## 8. Phase 4 — 数据统一 + Mac 就绪

**周期**：约 2–3 周（可与 Phase 3 部分并行）  
**目的**：单一真相源、Hub 配置校验、可选 PostgreSQL。

| ID | 任务 | 产出 |
|----|------|------|
| 4.1 | 群消息迁入 `conversation`/`message` | `group_manager.py` 改读 Store |
| 4.2 | `groups.json` 只保留元数据或废弃 messages 数组 | 迁移脚本 |
| 4.3 | 表 `agent_config`、`workflow_version` | Hub CRUD + 版本 |
| 4.4 | Hub 保存 workflow/agent 前校验（400 + 原因） | Owner 决策 A |
| 4.5 | `StoreBackend` 抽象；`DATABASE_URL` 可选 PG | `scripts/migrate_sqlite_to_pg.py` |
| 4.6 | `docs/MAC_APP_CONTRACT.md` | 只调 Hub API，不碰 Kernel |

### 过关门禁 4

| 检查项 | 标准 |
|--------|------|
| 新群消息 | 仅写 DB，可 JOIN project_id |
| 非法 workflow | Hub POST → 400 |
| pytest + Phase 2 REG | PG 模式下仍全 PASS（若启用 PG） |
| MAC_APP_CONTRACT | 文档存在且与 Hub API 一致 |

**状态**：⬜ 未开始（依赖 Phase 0；4.5 可选）

---

## 9. 总验收（全面测试）

全部 Phase 0→4 完成后，执行 **v1 总验收集**：

```bash
cd myteam
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"

# 1. 单元 + 集成
venv/bin/python3 -m pytest backend -q

# 2. 回归套件（CHECK_ONLY 快路径）
REG_DISCUSS_CHECK_ONLY=1 python3 scripts/regression/reg_discuss_loop.py
REG_L2_CHECK_ONLY=1 python3 scripts/regression/reg_l2_3role.py
REG_K16_CHECK_ONLY=1 python3 scripts/regression/reg_k16_recurring_trigger.py
for reg in reg_p0_product_dev reg_p1_media_ops reg_p2_pm_pack reg_p3_geo; do
  REG_CHECK_ONLY=1 python3 scripts/regression/${reg}.py
done

# 3. LIVE E2E（需 claude，生产基线）
./scripts/regression/run_regression.sh --live-tier1

# 4. 7 天试跑记录
test -f business/regression/recurring_week.json && \
  python3 -c "import json; d=json.load(open('business/regression/recurring_week.json')); assert d['completed_ticks']>=5"
```

**总验收 PASS 条件**

| # | 条件 |
|---|------|
| T1 | pytest backend → 0 failed |
| T2 | 所有 CHECK_ONLY REG → exit 0 |
| T3 | LIVE tier1（discuss + 4 workflow + L2）→ archived PASS |
| T4 | recurring_week ≥5/7 completed |
| T5 | publish_log / audit_log 有数据且可 SQL 查询 |

---

## 10. 进度追踪

| Phase | 名称 | 门禁 | 状态 | 完成日期 |
|-------|------|------|------|----------|
| **0** | 基线可信 | pytest 0 failed | ✅ | 2026-06-11 |
| **1** | 讨论链 REG | reg_discuss_loop CHECK_ONLY | ✅ | 2026-06-11 |
| **2** | 四条 workflow | 4 REG CHECK_ONLY PASS | ✅ | 2026-06-11 |
| **2+** | P0 OpenCode LIVE | `p0-opencode-trial` completed + REG-P0 LIVE_KPI | ✅ | 2026-06-11 |
| **2+** | P2 产品经理交付 LIVE | `pm-pack-trial` completed（3/3 + deck.pptx）+ REG-P2 LIVE_KPI | ✅ | 2026-06-12 |
| **3** | 持续运营 MVP | publish/audit 表 + recurring 文档 | 🔄 | 2026-06-11 |
| **4** | 数据统一 | 群消息入 DB + workflow_version | 🔄 | 2026-06-11 |
| **总验收** | v1 达成 | §9 LIVE claude + 7 天试跑 | ⬜ | |

> **2026-06-12**：`pytest backend/common/tests` **483 passed**（`test_gate` action 证据用 mock，不测 live 知乎）；P2 `pm-pack-trial` **completed**。

> 实施时更新上表：⬜ → 🔄 → ✅，并填写完成日期。

---

## 11. 实施顺序（当前）

**下一步（P1 → 总验收）**：

1. **P1 LIVE**：`reg_p1_media_ops.py`、`reg_p1_xhs_ops.py`（小红书运营 workflow E2E）  
2. **P3 LIVE**：`reg_p3_geo.py`  
3. **Phase 3**：`媒体持续运营` recurring + **7 天试跑**（≥5/7 completed）  
4. **Phase 4 验收**：群消息 DB + `workflow_version` 查询；Hub `validate_workflow` 400 行为  
5. **§9 总验收**：LIVE tier1 + publish_log/audit_log 可 SQL 查询  

**REG 入口**：`REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1`（须 bash，勿用 python 调用）。

**90 天内不做**（见 FRAMEWORK_BOUNDARY §8.5）：分布式调度、拖拽编排器、完整 sandbox、Kernel DSL 大改。

---

## 12. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-11 | Phase 0–2 CHECK_ONLY 落地；Phase 3/4 部分实现；470 tests pass |
| 2026-06-12 | P2 pm-pack-trial LIVE；test_gate action 证据 mock 去 flaky；483 tests pass |
