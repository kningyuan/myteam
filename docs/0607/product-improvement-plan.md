# myteam 产品体验升级方案

> 文档类型：strategy  
> 编写角色：产品专家  
> 创建日期：2026-06-06  
> 状态：初稿  
> 受众：研发 agent（main / developer）

---

## 1. 背景与目标

### 1.1 当前状态

myteam 已具备工业级的内核架构——Process 单内核（260 行）、Interaction 契约（6 种 kind）、确定性 Gate、SQLite 真相库、适配器隔离层均已落地并通过 94 例测试。Phase 8（go-live 切换）已完成，`run_kernel` 是唯一执行入口。

但产品层面的体验断层明显：从用户视角看，「能跑」但「不好用」。

### 1.2 核心问题

| # | 问题 | 影响 |
|---|------|------|
| P1 | 新用户从零到跑通第一个项目的路径太长 | 新用户放弃率极高 |
| P2 | 无用户侧文档，必须读架构文档才能理解概念 | 学习成本高 |
| P3 | 失败/错误信息偏技术化，用户无法自助排查 | 卡住即中断 |
| P4 | 运行中的进度和交付物不可视（无可观测 UI） | 用户无法感知进展 |
| P5 | workspace 初始化需手动创建多个配置文件 | 配置摩擦大 |

### 1.3 目标

在不违反已有设计决策（D9 UI 重设计推迟、D12 串行先行）的前提下，用**外科手术式改动**将新用户体验时间从「小时级」降低到「分钟级」，并建立基础的产品级使用闭环。

### 1.4 成功标准

| 指标 | 当前 | 目标 |
|------|------|------|
| 新用户首次跑通项目的时间 | ~30-60 分钟（含读文档+配置） | < 5 分钟（含 demo 项目） |
| 用户自助排查成功率 | 几乎为 0（必须读源码或架构文档） | > 60%（看错误消息即可定位） |
| 交付物可浏览性 | 需要在文件系统里翻 `deliverables/` | 在 Hub 上可直接浏览 |

---

## 2. 方案总览

分两个阶段执行，每个阶段独立可交付：

| 阶段 | 主题 | 工作量估计 | 依赖 |
|------|------|-----------|------|
| **Phase A** | 降低体验门槛 | 小（纯配置+文档+CLI 改进） | 无 |
| **Phase B** | 产品体验闭环 | 中（前端增量+后端少量改动） | Phase A（可选） |

---

## 3. Phase A — 降低体验门槛

### A1 快速启动模板（demo project）

**需求描述**：提供一个预配置的 demo 项目模板，用户克隆后一条命令即可跑通完整编排流程，看到 `completed` 结果。

**具体实现**：

1. 在 `business/` 下新增目录 `business/demo/`，包含：
   - `demo/goal.txt`：预定义的简单 goal，例如 `"调研 AI 编码工具的市场现状，输出一份简要报告"`
   - `demo/agents_config.json`：预配置 2 个 agent（researcher + product），使用默认模型
   - `demo/tasks/state.db`：无需预创建（run_kernel 会自动创建）
   - `demo/README.md`：说明文件

2. 在 `run_kernel.py` 新增 `--demo` 参数：
   ```
   venv/bin/python3 backend/common/run_kernel.py --demo
   ```
   效果等价于：
   - 使用 `business/demo/goal.txt` 作为 goal
   - 自动配置 minimal 的 agent 名册（仅 main + researcher + product）
   - 项目 ID 自动生成（如 `demo-YYYYMMDD-HHMMSS`）
   - 输出简化：只打印关键状态变化 + 最终结果，不打印内部调试信息

3. **约束**：
   - demo 运行完毕后，项目数据落 `business/tasks/` 下常规路径，不特殊处理
   - `--demo` 不可与 `--project` 同时使用
   - demo 仅支持 `--mode one_shot`

**验收标准**：
- [ ] 在全新 checkout（无任何业务数据）上执行 `--demo`，5 分钟内完成并 exit 0
- [ ] 输出仅包含：goal 简述、agent 选择、任务进度（当前/总数）、最终状态
- [ ] 运行结束后 `business/tasks/project/demo-*/` 下有完整的 deliverable 文件
- [ ] `--help` 输出中包含 `--demo` 说明

---

### A2 用户侧文档

**需求描述**：补充面向终端用户的文档，与现有架构文档（面向贡献者）互补。研发 agent 编写以下 4 份文档，保存到 `docs/` 目录。

| 文档 | 文件 | 目标读者 | 核心内容 |
|------|------|---------|---------|
| 快速开始 | `docs/quick-start.md` | 新用户 | 从安装到跑通第一个项目的 5 步指南 |
| 用户指南 | `docs/user-guide.md` | 日常用户 | 项目、任务、agent、交付物的概念与操作 |
| 术语表 | `docs/glossary.md` | 所有读者 | 30+ 核心术语的一句话定义 |
| 故障排查 | `docs/troubleshooting.md` | 遇到问题的用户 | 常见错误、原因、解决方法对照表 |

**文档质量标准**：
- 快速开始必须能在 5 分钟内读完并跟着操作
- 每个概念附一句话定义 + 一句话为什么重要
- 故障排查每条必须包含：错误现象 → 可能原因 → 解决步骤（3 层结构）
- 不出现架构决策编号（D1–D19），不引用代码内部实现

**验收标准**：
- [ ] 4 份文档全部创建，格式一致
- [ ] 快速开始经过 dry-run 验证（按文档步骤能跑通 demo 项目）
- [ ] 术语表覆盖 agent / task / task_type / DAG / gate / outcome / artifact / action / interaction / workspace / project / deliverable / registry / triage

---

### A3 错误信息改进

**需求描述**：改进 `run_kernel` 和 Process 状态机的错误输出，让用户能理解「什么出错了 + 该怎么办」。

**改动点**：

1. **`backend/common/run_kernel.py`** — 顶层错误处理增强：
   ```python
   # 当前：打印 traceback 或原始异常
   # 改为：按异常类型分类输出
   ```
   实现建议：在 `main()` 的 try/except 中按异常类型输出不同信息：

   | 异常类型 | 用户消息 |
   |---------|---------|
   | `FileNotFoundError`（agent workspace 缺失） | ❌ 找不到 agent「{agent_id}」的工作空间。请确认 `business/workspaces/workspace-{agent_id}/` 存在。 |
   | `FileNotFoundError`（config 缺失） | ❌ 缺少配置文件 `{path}`。可执行 `--init` 生成默认配置。 |
   | `RuntimeError`（task_plan agent 越界） | ❌ 编排规划失败：main 分配了名册外的 agent「{agent}」。重试后仍失败，需要检查 agents_registry.json。 |
   | `subprocess.CalledProcessError` | ❌ CLI 后端执行失败（exit code {code}）。请确认 CLI（opencode/claude）安装正确且已登录。 |
   | 其他 | ❌ 未知错误。详情见日志。如需帮助，请附上 `business/tasks/project/{project_id}/` 目录。 |

2. **`backend/common/process.py`** — 状态转换时输出 human-readable 消息：

   在 Process 的关键状态转换点（task failed / blocked / triage）增加格式化日志输出：
   ```
   # 示例输出
   ╔══════════════════════════════════════╗
   ║  项目进度  ████████░░  3/4 任务完成  ║
   ╚══════════════════════════════════════╝
   ✔ research(researcher) → completed (12s, 3.2k tokens)
   ✔ seo-plan(seo) → completed (45s, 15k tokens)
   ✔ strategy(product) → completed (38s, 12k tokens)
   ```
   仅在 `--verbose` 模式下输出详细日志。

3. **`backend/common/agent_port.py`** — 看门狗超时明确提示：
   - soft_idle 超时：`⚠️ agent「{agent_id}」已 {idle_seconds}s 无响应（阈值 {soft_idle}s），仍在等待...`
   - hard_idle 超时：`✖ agent「{agent_id}」无响应超过 {hard_idle}s，将终止并重试`

**验收标准**：
- [ ] 5 种常见错误场景下，用户看到的不是 Python traceback 而是结构化中文提示
- [ ] 每类提示包含「出了什么错」和「该怎么办」两个部分
- [ ] Process 任务完成时输出进度条（非 verbose 模式）
- [ ] 错误提示保存在项目 `run_event` 中，可通过 observability API 查询

---

### A4 Workspace 初始化优化

**需求描述**：将目前需要手动创建的 workspace 配置自动化，减少新用户配置摩擦。

**改动点**：

1. **在 `run_kernel.py` 新增 `--init` 参数**：
   ```
   venv/bin/python3 backend/common/run_kernel.py --init
   ```
   自动执行：
   - 读取 `business/config/agents_registry.json` 获取所有已注册 agent
   - 对每个 agent，检查 `business/workspaces/workspace-{agent_id}/` 是否存在
   - 若不存在，创建目录结构：
     ```
     business/workspaces/workspace-{agent_id}/
       AGENTS.md          # 从 AGENTS.md.template 复制
       IDENTITY.md        # 从 agents_registry 自动生成
       SOUL.md             # 从 agents_registry 自动生成
       .trigger/           # 空目录
       .response/          # 空目录
       deliverables/       # 空目录
     ```
   - 输出初始化结果清单

2. **在 `business/` 下新增模板文件**：
   - `business/AGENTS.md.template` — 通用的 AGENTS.md 模板（参考现有 workspace-main/AGENTS.md）

3. **在 `backend/common/agent_bootstrap.py` 中新增 `init_workspace()` 函数**（可测试）：
   - 输入：`agent_id`, `agent_config`（来自 registry）
   - 输出：创建的文件列表
   - 不覆盖已有文件（幂等）

**验收标准**：
- [ ] `--init` 在全新 checkout 上运行时，为所有 12 个注册 agent 创建 workspace
- [ ] 重复运行 `--init` 不产生重复文件，不报错
- [ ] 每个 workspace 包含 AGENTS.md/IDENTITY.md/SOUL.md 三个文件
- [ ] `--help` 输出中包含 `--init` 说明

---

## 4. Phase B — 产品体验闭环

### B1 Hub 项目总览页

**需求描述**：在 Hub 现有前端上新增一个项目总览页面，让用户通过浏览器即可查看编排项目状态和交付物，不用翻文件系统。

**背景**：D9 将 UI 重设计推迟到前端数据契稳定之后。当前 Interaction 契约（D11）和可观测 API（D17）已稳定落地，条件已满足。本需求不涉及 UI 重设计（不改变风格/布局），而是在现有单页应用上增量添加功能。

**具体实现**：

1. **后端**（`hub/api/observability_api.py`）：
   - 新增 `GET /api/obs/projects` — 返回所有项目列表（id, status, created_at, task_count）
   - 确认 `GET /api/obs/projects/{id}/overview` 和 `GET /api/obs/projects/{id}/tasks` 已存在且返回完整数据
   - 新增 `GET /api/obs/projects/{id}/deliverables` — 返回项目交付物列表（task_id, agent_id, task_type, files[]）

2. **前端**（`frontend/app.js` / `frontend/index.html`）：
   - 在 Hub 导航上新增「项目」标签页
   - 项目列表：卡片式展示（项目 ID / 状态 / 任务数 / 创建时间）
   - 点击项目进入详情：展示任务 DAG（简化为列表+依赖箭头），每个任务显示 agent / task_type / 状态 / token 消耗
   - 交付物区域：列出所有 deliverable 文件，提供下载/查看链接

3. **样式**（`frontend/style.css`）：
   - 复用现有暗色主题和组件样式，不引入新设计语言
   - 任务状态用颜色标识（completed=绿 / in_progress=黄 / failed=红 / blocked=灰）

**验收标准**：
- [ ] 可在 Hub 上看到所有已完成和进行中的项目列表
- [ ] 可查看单个项目的任务清单和状态
- [ ] 可浏览和下载任务的 deliverable 文件
- [ ] 页面数据来自 observability API，不直接读文件系统

---

### B2 实时进度可视化

**需求描述**：在 Hub 上实时展示编排运行进度，让用户不必盯着终端等结果。

**实现**：

1. **前端消费 `run_event` SSE**：
   - 在 Hub 前端新增 SSE 连接到 `/api/obs/projects/{id}/events`
   - 事件类型处理：
     - `task_started` → 对应任务卡片切换到「运行中」状态
     - `task_completed` → 更新任务状态 + 显示耗时/token
     - `task_failed` → 标记失败 + 显示错误摘要
     - `project_completed` → 整体状态更新 + 最终摘要
   - 使用 EventSource API

2. **进度指示**：
   - 项目详情页顶部显示整体进度（已完成/总数）
   - 当前运行中的任务显示「执行中…」动画指示

**验收标准**：
- [ ] 在 Hub 上启动编排项目后，页面自动刷新状态（无需手动刷新）
- [ ] 任务状态变化在 3 秒内反映到 UI

---

### B3 CLI 进度输出美化

**需求描述**：改进 `run_kernel` 终端输出的可读性，让用户在不打开 Hub 时也能直观了解执行进度。

**实现**：见 A3-2 中 Process 格式化输出的具体方案。

---

## 5. 执行路径与依赖关系

```mermaid
flowchart LR
    subgraph "Phase A"
        A1["--demo 快速启动"]
        A2["用户侧文档"]
        A3["错误信息改进"]
        A4["--init 初始化"]
    end
    subgraph "Phase B"
        B1["Hub 项目总览"]
        B2["实时进度可视化"]
    end

    A1 --> A3  <!-- demo 需要好的错误提示 -->
    A4 --> A1  <!-- init 确保 demo 所需 workspace 存在 -->
    A3 --> B1  <!-- 错误信息结构化后可在 Hub 展示 -->
    B1 --> B2  <!-- 项目总览是 SSE 可视化的基础 -->
```

**建议的执行顺序**：

| 顺序 | 需求 | 理由 |
|------|------|------|
| 1 | A4 (`--init`) | 零依赖，为后续所有需求保障 workspace 可用 |
| 2 | A1 (`--demo`) | 依赖 `--init` 确保 agent workspace 就绪 |
| 3 | A3 (错误信息) | 提升所有场景的体验，与 A1 并行开发 |
| 4 | A2 (文档) | 纯内容工作，可与 A1/A3 并行 |
| 5 | B1 (Hub 项目页) | 依赖 A3 的错误结构化输出 |
| 6 | B2 (SSE 可视化) | 依赖 B1 的项目总览框架 |

---

## 6. 未纳入本次方案的事项

以下问题已识别但**不在本次方案范围内**，各有明确理由：

| 事项 | 排除理由 |
|------|---------|
| UI 重设计（新主题/布局/组件库） | D9 要求保持现有前端形态，本次仅做增量功能 |
| 并行 DAG 执行 | D12 明确串行先行，并行推迟 |
| 多租户/RBAC/鉴权 | 项目早期，无企业级用户需求 |
| 外部集成（Slack/飞书/GitHub） | 无明确用户需求，过早泛化 |
| 移动端/PWA | D9 已推迟到桌面端 UI 稳定之后 |
| Action 型任务前端操作流 | 依赖 publish-post 等 action skill 先稳定 |

---

## 7. 不确定性声明

- **Phase B 的工作量估计为粗略值**：具体取决于 Hub 前端现有 `app.js` 的模块化程度。如果前端当前代码组织不利于增量修改，Phase B 实际工作量可能上浮 50–100%。
- **`--demo` 的 goal 选择**：如果 demo 跑通过长（>5 分钟），体验反而不如预期。建议选择纯 research 类 goal（只需 researcher 一个 agent），保证 3 分钟内完成。需要研发 agent 在实现时确认最短可完成的 goal。
- **错误信息维护**：引入结构化错误分类后，后续新增错误场景时需要同步更新错误映射表。这需要通过代码审查保证。

---

*本文档由 workspace-product（产品专家）产出，供研发 agent 评估工作量并进入实现。*
