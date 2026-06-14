# myteam 产品化升级实施方案（Hub 2.0 + 配置 + 质量 + v1 闭合）

> **版本**：2026-06-10  
> **状态**：执行中（权威实施计划）  
> **基线分支**：`feat/runtime-roster-workflows-ui`  
> **原则**：Kernel L1/L2 冻结；Workflow 为编排真源；每条 Track 独立可验收；先 CHECK_ONLY 再 LIVE。

**关联文档**

| 文档 | 作用 |
|------|------|
| [V1_CAPABILITY_PLAN.md](./V1_CAPABILITY_PLAN.md) | v1 关门禁与 Phase 0–4 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Kernel / Workflow / Skill 边界 |
| [FRAMEWORK-FREEZE.md](./FRAMEWORK-FREEZE.md) | 不可改动的内核范围 |
| [DESIGN-DELIVERY-TEMPLATES.md](./DESIGN-DELIVERY-TEMPLATES.md) | delivery_template 契约 |
| [DESIGN-SKILL-SYSTEM.md](./DESIGN-SKILL-SYSTEM.md) | Skill 体系与自我升级 L0–L4 |
| [DESIGN-OUTCOME-FORMS.md](./DESIGN-OUTCOME-FORMS.md) | 三产出形态（文档态/包态/证据态） |

---

## 0. 健康基线（gstack Health Gate）

每次开工前、每个 Phase 完成后执行：

```bash
cd myteam
export PYTHONPATH="$PWD/backend:${PYTHONPATH:-}"
export MYTEAM_ROOT="$PWD"

# 1) 单元测试
venv/bin/python3 -m pytest backend/common/tests/ -q

# 2) REG CHECK_ONLY（v1 套件）
REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1

# 3) Hub 存活（可选）
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/
# 期望 200
```

| 检查项 | 当前基线（2026-06-10） | 过关标准 |
|--------|------------------------|----------|
| pytest | 483 passed | 0 failed |
| REG v1 CHECK_ONLY | Phase V1 PASS | 全脚本 PASS |
| Kernel 改动 | 仅 hooks 薄层 | 不改 process.py / gate.py 语义 |

---

## 1. 目标定义（可验收）

| 维度 | 达成标准 | 不承诺 |
|------|----------|--------|
| **配置真源** | 协作（建群/通报/群讨论）由 workflow `options.collaboration` 驱动；全局 skill_config 仅作 fallback | Hub UI 内嵌 workflow 可视化编辑器 |
| **Agent 质量** | 每条主 workflow 有 task_type + Skill +（可选）delivery_template；ledger→KB 半自动 | Agent 自主改 Skill |
| **产品化 UI** | Hub 2.0（React + shadcn）可访问 `/v2`，核心页（项目列表/详情/群组）只读对接现有 API | 一次替换全部 v1 页面 |
| **v1 闭合** | P1/P3 LIVE、xhs LIVE（登录后）、7 天 recurring ≥5/7 | OpenCode 生产基线 |

**总验收句**：Track 1–3 各 Phase 过关 + v1 §9 总验收 ⇒ 产品化 v1 达成。

---

## 2. 架构约束（实施边界）

```
┌─────────────────────────────────────────────────────────┐
│  Hub 2.0 UI (frontend-v2)  ──HTTP──▶  FastAPI /api/*   │
├─────────────────────────────────────────────────────────┤
│  workflow YAML ──▶ workflow_collaboration ──▶ 建群/通报  │
│  Skill catalog ──▶ AgentPort ──▶ opencode CLI          │
├─────────────────────────────────────────────────────────┤
│  Kernel (冻结): Process · Gate · Store · AgentPort      │
└─────────────────────────────────────────────────────────┘
```

- **Groups**：平台能力，可 `project_id=None` 独立建群；项目群由 workflow collaboration 控制。
- **Telegram**：本计划忽略，不新增依赖。
- **Evolution**：`experience.py` ledger → promote → hints；人工维护 Skill 为上限。

---

## 3. Track 1 — Workflow 配置层

### Phase C-0：`options.collaboration`  schema + 解析器 ✅ 本迭代

**交付**

- `backend/common/workflow_collaboration.py` — 统一解析
- 接入 `project_group_service`、`loop_discussion_runtime`、`kernel_project_hooks`
- 兼容旧字段 `group_discussion_enabled` / `loop_discussion_profile`

**Schema**

```yaml
options:
  collaboration:
    project_group:
      enabled: true          # 项目启动时自动建群/同步成员
      include_main: true     # 可选，默认 skill_config.auto_group.include_main
    notifications:
      enabled: true          # task_complete 等进度通报
    group_discussion:
      enabled: true          # loop FAIL 时结构化群讨论
      profile: work-review-alignment
```

**验收**

```bash
venv/bin/python3 -m pytest backend/common/tests/test_workflow_collaboration.py -q
REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1
# reg_discuss_loop 仍 PASS（兼容旧 YAML）
```

### Phase C-1：主 workflow 迁移 collaboration 块

**交付**：以下 workflow 写入 `options.collaboration`（保留旧字段至 REG 全绿后删除）：

| workflow | project_group | notifications | group_discussion |
|----------|---------------|---------------|------------------|
| 产品规划方案 | true | true | true + work-review-alignment |
| 第三章-讨论链路测试 | true | true | true + work-review-alignment |
| 产品经理交付 | true | true | false |
| 小红书运营 | true | true | false |
| 媒体持续运营 | true | true | false |

**验收**

```bash
venv/bin/python3 -m pytest backend/common/tests/test_workflow_loader.py -q
python3 scripts/regression/reg_discuss_loop.py  # CHECK_ONLY 或 LIVE 按环境
```

### Phase C-2：task_type + delivery_template 补全

**交付**

| task_type | delivery_template | Skill |
|-----------|-------------------|-------|
| requirements | prd-lite（新建） | requirements（新建 SKILL.md） |
| product-planning | tds-ch3-product-planning（已有） | product-planning |
| deck-build | — | wps-deck |
| publish-xhs | publish-xhs（已有） | xhs-ops |

**验收**

```bash
venv/bin/python3 -m pytest backend/common/tests/test_delivery_templates.py -q
REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1
```

---

## 4. Track 2 — Agent 质量与 Evolution

### Phase Q-0：Skill 覆盖审计

**交付**：`business/skills/catalog.yaml` 与 11 条 workflow 的 task_type 矩阵文档（§附录 A）。

**验收**：每个 workflow 任务行的 `task_type` 在 catalog 有对应 Skill 或明确「内核直驱」标注。

### Phase Q-1：ledger → KB 操作手册 + REG KPI

**交付**

- `docs/EXPERIENCE_LEDGER_RUNBOOK.md` — promote 步骤与 `append_experience_hints` 验证
- REG 脚本输出 `experience_hints_applied` 计数（CHECK_ONLY mock）

**验收**

```bash
venv/bin/python3 -m pytest backend/common/tests/test_experience.py -q
```

### Phase Q-2：按 task_type 的 Skill 迭代（人工）

**节奏**：每完成一条 workflow LIVE REG，更新对应 SKILL.md + ledger 条目。

**验收**：同 task_type 第二次 RUN 可观测 hints 注入（`task_data.json` meta 或日志）。

---

## 5. Track 3 — Hub 2.0 产品化 UI

### Phase UI-0：脚手架 ✅ 本迭代

**交付**

- `frontend-v2/` — Vite + React + TypeScript + Tailwind + shadcn/ui
- `vite.config.ts` dev proxy → `http://127.0.0.1:8765`
- FastAPI 挂载 `/v2` → `frontend-v2/dist`（build 后）
- 首页：项目列表（`GET /api/projects`）+ 导航壳

**验收**

```bash
cd frontend-v2 && npm install && npm run dev
# 浏览器 http://localhost:5173/v2/ 可见项目列表

npm run build
./run.sh restart
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/v2/
# 期望 200
```

### Phase UI-1：核心页迁移

| 页面 | API | 优先级 |
|------|-----|--------|
| 项目详情 + 任务 DAG | `/api/projects/{id}` | P0 |
| 群组列表/聊天 | `/api/groups`, SSE | P0 |
| Agent 管理 | `/api/agents` | P1 |
| Workflow 列表（只读） | `/api/workflows` | P1 |
| 任务类型 / 产出形态（只读） | `/api/task-types`, `/api/task-types/outcome-kinds` | P1 |
| 设置 | `/api/skill-config` | P2 |

**验收**：gstack browse 对 `/v2/projects`、`/v2/groups` 截图对比 v1 功能 parity checklist。

### Phase UI-2：v1 并行与切换

- 根路径 `/` 保持 v1 `frontend/` 不变
- Hub 顶栏「体验新版」链到 `/v2`
- v1 废弃门：UI-1 全页 parity + 7 天无 P0 bug

---

## 5. Track O — 产出形态（三形态模型）

> 权威设计：[DESIGN-OUTCOME-FORMS.md](./DESIGN-OUTCOME-FORMS.md)

**目标**：全行业 workflow 抽象为三种 **产出形态**（文档态 / 包态 / 证据态），Gate 算法固定；差异下沉到 `delivery_template`。

| 产出形态 | `outcome_kind` | Gate |
|----------|----------------|------|
| 文档态 | `artifact` | `check_format` |
| 包态 | `code_project` | `check_code_project` |
| 证据态 | `action` | `check_action_evidence` |

### Phase O-1：catalog + registry ✅

- `OUTCOME_KIND_CATALOG` 含 `form_label_zh` / `gate_algorithm`
- `FormatSpec.required_extensions` + gate 包态扩展名校验
- `code-deployment` 标注文档态；新增 `deploy-run`（证据态）、`config-bundle`（包态）

### Phase O-2：delivery_template 示例 ✅

- `deploy-smoke.yaml` → `deploy-run`
- `config-bundle.yaml` → `config-bundle`（yaml/json 非源码包态）

### Phase O-3：Hub 暴露 ✅

- `/api/task-types` 返回 `outcome_form_label` / `gate_algorithm`
- v1 管理 Tab 产出形态列读 catalog
- Hub 2.0 `/v2/task-types` 只读页

**验收**

```bash
venv/bin/python3 -m pytest backend/common/tests/test_outcome_forms.py -q
REG_CHECK_ONLY=1 python3 scripts/regression/reg_outcome_forms.py
cd frontend-v2 && npm run build
```

---

## 6. Track 4 — v1 能力闭合

| 项 | 命令 | 过关 |
|----|------|------|
| P1 LIVE | `bash scripts/regression/run_regression.sh --suite p1` | PASS（OpenCode 可用时） |
| P3 LIVE | 同上 `--suite p3` | PASS |
| xhs LIVE | `bash business/skills/xhs-ops/scripts/check_xhs_login.sh` → 0；再跑 xhs REG | PASS |
| 7-day recurring | cron + `recurring_trigger` | ≥5/7 completed |
| 总验收 | V1_CAPABILITY_PLAN §9 | 全 Phase PASS |

---

## 7. Track 5 — 群组 UX 增强

### Phase G-0：消息格式化（已有 notify_format 统一）

**验收**：`format_progress_message` 输出多行结构；群 UI 渲染 markdown/换行。

### Phase G-1：@all + 完整上下文（可选）

- `send_group_message` 支持 `@all`
- `_stream_agent_in_group` 取消 200 字截断，改 configurable limit

**验收**：群 @mention E2E pytest + 手工 Hub 验证。

---

## 8. 执行顺序与里程碑

| 周次 | 内容 | 里程碑 |
|------|------|--------|
| W1 | C-0 + UI-0 + C-1 部分 | collaboration 解析器 + Hub2 壳 |
| W2 | UI-1 项目/群组 + C-2 | `/v2` 日可用 |
| W3 | Q-0/Q-1 + P1/P3 LIVE | REG LIVE 绿 |
| W4 | xhs LIVE + recurring + v1 §9 | v1 总验收 |

---

## 9. 本迭代实施清单（2026-06-10 → autoplan 全量）

- [x] C-0 collaboration 解析器
- [x] C-1 5 条 workflow collaboration 块
- [x] C-2 prd-lite + 产品经理交付 template_id + 测试
- [x] UI-0 脚手架 + /v2 挂载
- [x] UI-1 项目 DAG/交付物、群组/chat、Agent、Workflow 只读页
- [x] UI-2 v1 侧栏「2.0」入口
- [x] Q-0 WORKFLOW_TASK_TYPE_MATRIX + catalog 补全
- [x] Q-1 EXPERIENCE_LEDGER_RUNBOOK + test_experience.py
- [x] G-1 @all + 可配置 reply_preview_limit（默认 0=不截断）
- [x] REG `--suite p1` / `--suite p3`
- [x] Track O 三产出形态：catalog + deploy-run/config-bundle + Hub 2.0 task-types 页
- [ ] Track 4 LIVE：需 Claude CLI + xhs 登录 + 7-day cron（运维/人工）

---

## GSTACK REVIEW REPORT

<!-- /autoplan restore point: ~/.gstack/projects/myteam/feat-runtime-roster-workflows-ui-autoplan-restore-20260610.md -->

**审查模式**：autoplan（Claude-only，6 原则自动拍板）  
**结论**：**APPROVED — 执行全量实现（Track 4 LIVE 除外）**

### CEO 共识（自动）

| 维度 | 决策 |
|------|------|
| 问题正确性 | Workflow 为真源 + Hub 2.0 并行迁移，不 big-bang 替换 v1 |
| 范围 | 完成 C-2/UI-1/Q/G-1；LIVE/recurring 标 UNVERIFIABLE 待运维 |
| 6 个月轨迹 | Kernel 冻结，配置与 UI 分层演进 |

### Design 共识（UI scope）

| 维度 | 分数 | 决策 |
|------|------|------|
| 信息架构 | 8/10 | 顶栏：项目/群组/Agent/Workflow/**任务类型** |
| 空/错/加载态 | 7/10 | 各页有 loading + error banner |
| SSE 群聊 | 7/10 | 对齐 v1 `/chat` + `/events` |

### Eng 共识

| 维度 | 决策 |
|------|------|
| 架构 | `workflow_collaboration` 薄层；frontend-v2 纯 API 消费 |
| 测试 | prd-lite gate、@all mention、experience inject |
| 风险 | prd-lite default_for 与 templates.yaml 并存 — loader 优先 YAML 实例 |

### DX 共识

| 维度 | 决策 |
|------|------|
| TTHW Hub2 | `npm run dev` + `./run.sh start` → `/v2` |
| 文档 | MATRIX + LEDGER RUNBOOK |

### Decision Audit Trail

| # | Phase | Decision | Principle |
|---|-------|----------|-----------|
| 1 | CEO | 并行 v1/v2，不删 v1 | P3  pragmatic |
| 2 | Eng | prd-lite 3 节非 5 节 | P1 completeness for lite use case |
| 3 | Eng | reply_preview_limit 默认 0 | P1 完整上下文 |
| 4 | CEO | Track 4 LIVE 不阻塞代码合并 | P6 bias toward action |

### NOT in scope（defer）

- Workflow 可视化编辑器
- Hub2 设置页（skill-config 编辑）
- OpenCode 生产基线
- 7-day recurring 无人值守（需 cron + 环境）

### Verification

```bash
venv/bin/python3 -m pytest backend/common/tests/ -q
REG_CHECK_ONLY=1 bash scripts/regression/run_regression.sh --suite v1
cd frontend-v2 && npm run build
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/v2/
```

---

## 附录 A：workflow × task_type 矩阵（快照）

| workflow | task_types |
|----------|------------|
| 产品规划方案 | product-planning, … |
| 产品经理交付 | product-planning, requirements, deck-build |
| 小红书运营 | publish-xhs, content-ops, … |
| 第三章-讨论链路测试 | product-planning + loop review |

（Phase Q-0 补全完整矩阵 CSV。）

---

## 附录 B：Plan Completion 审计命令

发版前（gstack ship Step 8 同款）：

```bash
# 提取计划条目并对照 diff
git diff main...HEAD --stat
# 逐项核对 §9 清单与 Track Phase 验收命令
```

**Plan 文件路径**：`docs/HUB2_PRODUCTIZATION_PLAN.md`
