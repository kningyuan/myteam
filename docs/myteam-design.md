# myteam 总体设计方案

> **版本**：2026-07-04 v2（含可量化评估指标）  
> **定位**：工业级多 Agent AI 团队协作框架  
> **核心理念**：每个 Agent 在约定边界内高质量交付，通过 Workflow 编排协作完成任务  
> **使用方式**：每个功能点附带 KPI，按 KPI 达标情况判断是否完成。所有 KPI 全部达标 = myteam 项目完成

---

## 目录

1. [项目定位与总体 KPI](#1-项目定位与总体-kpi)
2. [核心架构与各层 KPI](#2-核心架构与各层-kpi)
3. [Workflow 系统与流程 KPI](#3-workflow-系统与流程-kpi)
4. [质量保证体系与各环节 KPI](#4-质量保证体系与各环节-kpi)
5. [Agent 执行机制与各环节 KPI](#5-agent-执行机制与各环节-kpi)
6. [Agent 能力生态与覆盖度 KPI](#6-agent-能力生态与覆盖度-kpi)
7. [记忆与知识体系与各钩子 KPI](#7-记忆与知识体系与各钩子-kpi)
8. [Hub 与 UI 可用性 KPI](#8-hub-与-ui-可用性-kpi)
9. [用户可配置项与完备度 KPI](#9-用户可配置项与完备度-kpi)
10. [未完成项与实现路线](#10-未完成项与实现路线)
11. [验证标准与 KPI 汇总表](#11-验证标准与-kpi-汇总表)

---

## 1. 项目定位与总体 KPI

### 1.1 一句话定位

myteam 是一个**工业级多 Agent AI 团队协作框架**，让用户像管理一个真实团队一样，配置 Agent 角色、编排协作流程、控制交付质量。

### 1.2 两个主攻方向

| 方向 | 说明 | 量化 KPI |
|------|------|----------|
| **团队协作框架** | Workflow 编排多 Agent 合作完成任务；支持私聊、群聊圆桌、自动化编排三种协作模式 | **KPI-1.2a**：新 workflow 从创建到首次成功运行 ≤ 30 分钟（用户操作 + 执行时间） |
| **交付质量保证** | Agent 按约定边界产出高质量成果物；结构性质量由 Gate 机器判，内容性质量由多 Agent 评审循环兜底 | **KPI-1.2b**：Agent 一次通过 Gate 率 ≥ 80%；review 轮次 ≤ 2 轮；review 不重复 A 类问题 |

### 1.3 总体 OKR

| 目标 | 关键结果 | 当前值 | 目标值 | 测量方式 |
|:----|:---------|:------|:------|:---------|
| **单 Agent 交付可控** | 一次通过 Gate 率 | 0%（未验证） | ≥ 80% | 统计 Gate 重试 0 次的 task 占比 |
| **多 Agent 协作高效** | 平均 review 轮次 | 3（实测） | ≤ 2 | 统计 review+rework 循环实际轮次 |
| **A/B 类质量分离** | A 类问题被 review 兜底率 | 4/5（实测 Gate 本可拦） | 0% | Gate 可判的缺陷不进 review |
| **Workflow 创建自动化** | 从对话到运行的总时长 | 未验证 | ≤ 30 分钟 | sop→workflow→启动→完成 |
| **知识共享生效** | 用户 KB 条目 7 天使用率 | 0%（未实现） | ≥ 50% | 用户写入的条目在 7 天内被 Agent 检索命中 |
| **Skill 生态健康** | Skill 被映射率 | 9/66（13.6%） | ≥ 80% | 被至少一个 Agent 挂载的 Skill 比例 |

---

## 2. 核心架构与各层 KPI

### 2.1 分层架构

```
Layer A — 框架内核（Framework Freeze）
  ├── Process：声明式状态机，串行驱动 DAG（process.py + task_pipeline.py）
  ├── AgentPort：Interaction 投递 + 取回（agent_port.py）
  ├── Gate：确定性门禁（gate.py + registry.py）
  ├── Store：SQLite 真相源（store.py）
  └── Contracts：Pydantic 辨识联合（contracts.py）

Layer B — 执行增强层（execution_harness）
  ├── PRE：prompt 注入（经验/L1/偏好/KB/rubric/umbrella_skill）
  └── POST：产出沉淀（promote/lesson/quality/rubric/skill_review）

Layer C — 适配层（adapter/）
  ├── claude/：适配 Claude Code CLI（.claude/skills/ + MCP）
  └── opencode/：适配 opencode CLI（.opencode/skills/ + MCP）

Layer D — 记忆堆栈（memstack）
  ├── L1 Memory：短时对话记忆（mem0/native/sqlite/noop）
  ├── KB：长期知识库（sqlite/gbrain），标签 + 项目域索引
  ├── Preferences：用户偏好分节 → USER.md → inject prompt
  └── Experience：同类任务经验复用（ledger 条目）
```

### 2.2 各组件 KPI

| 组件 | 功能 | KPI | 当前值 | 目标值 |
|:----|:-----|:----|:------|:------|
| **Process** | 状态机驱动 DAG | **KPI-2.2a**：串行调度正确率（无跳步/漏步） | 未验证 | 100% |
| | | **KPI-2.2b**：断点续跑正确率（中断后恢复不丢结果） | 未验证 | 100% |
| | | **KPI-2.2c**：gate 重试耗尽后 triage 触发率 | 未验证 | 100% |
| **AgentPort** | 投递+取回 | **KPI-2.2d**：看门狗正确拦截超时率 | 未验证 | 100% |
| | | **KPI-2.2e**：.response 文件正确率（校验通过才写入） | 未验证 | 100% |
| **Gate** | 三层门禁 | **KPI-2.2f**：契约门禁拦截率（非法格式不得放行） | 未验证 | 100% |
| | | **KPI-2.2g**：格式门禁误拦率（合法内容被误判为不合规） | 未验证 | ≤ 5% |
| **Store** | 持久化 | **KPI-2.2h**：数据完整率（异常中断后不丢已提交结果） | 未验证 | 100% |
| **Contracts** | 契约校验 | **KPI-2.2i**：契约校验 100% 覆盖所有 8 种 kind 的响应 | 确保 | 100% |
| **Adapter** | CLI 适配 | **KPI-2.2j**：opencode 和 claude 双后端均能成功执行标准 task | 未验证 | 双后端均通过 |
| **Layer B** | 执行增强 | **KPI-2.2k**：所有注入块默认关闭，打开后不阻塞主流程 | 确保 | 100% |

### 2.3 框架冻结原则

> 参考 `docs/FRAMEWORK-FREEZE.md`

Layer A（kernel + adapter + contracts + store）不再做功能扩展。新能力走：

| 新能力去向 | 示例 |
|-----------|------|
| `business/workflows/*.yaml` | 新的协作流程 |
| `business/skills/*/SKILL.md` | 新的 Agent 技能 |
| `business/delivery_templates/*.yaml` | 新的交付模板 |
| `business/config/` | 新的 agent/register/group 配置 |

**KPI-2.3**：新功能需求不得导致 Layer A 代码变更。违反次数 = 0 即达标。

---

## 3. Workflow 系统与流程 KPI

**workflow 是 myteam 的协作核心**。一切团队协作——多步 DAG、多 Agent 并行评审、多轮循环修稿——通过 workflow YAML 定义驱动。

### 3.1 Workflow 创建流程与 KPI

```
用户操作流程：
  1. 选择/创建 workflow → 2. 编辑 DAG 节点 → 3. 配置 loop/review
  → 4. 保存 → 5. validate_workflow() 验证 → 6. 通过 → 7. 创建项目启动
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 创建 workflow | **KPI-3.1a**：从 UI 新建 workflow 到保存成功的操作 ≤ 5 步 | 5 步 | 记录用户操作路径 |
| 2. 编辑节点 | **KPI-3.1b**：每个节点配置的平均时间 ≤ 2 分钟 | 2 分钟 | 从打开编辑到保存 |
| 3. 配置 loop | **KPI-3.1c**：loop 配置支持 3 种 transition 规则（marker/gate_passed/task_status） | 3 种 | 枚举 YAML 支持 |
| 4. 保存 | **KPI-3.1d**：保存成功率 = 100%（语法错误提示清晰） | 100% | 统计保存失败率 |
| 5. 验证 | **KPI-3.1e**：validate_workflow() 覆盖 7 项检查，每项都有明确错误信息 | 7 项 | 见 3.4 节 |
| 6. 通过 | **KPI-3.1f**：首次验证通过率 ≥ 80%（用户按指引操作） | 80% | 统计首次验证结果 |
| 7. 启动 | **KPI-3.1g**：从创建到首次成功运行 ≤ 30 分钟 | 30 分钟 | 计时 |

### 3.2 Workflow YAML 结构

```yaml
id: my-workflow
name: 我的协作流程
version: "1.0"
description: 流程说明

# 协作配置
options:
  review_enabled: false        # 是否启用 peer_review（各步自带的 review）
  split_enabled: false         # 是否启用运行时任务拆分
  parallel_enabled: false      # 是否启用同波次并行执行
  max_parallel: 4              # 最大并行数
  collaboration:               # 协作配置
    project_group:
      enabled: true
    notifications:
      enabled: true
    group_discussion:
      enabled: true
      profile: work-review-alignment

# 任务 DAG
tasks:
  - id: step-1                 # 唯一标识
    name: 任务名称
    agent: agent_id            # 执行 Agent
    task_type: research        # 任务类型
    template_id: research-report  # 交付模板
    reviewer: agent_id         # 可选：指定 reviewer
    dependencies: []           # 依赖的上游 step id
    description: "任务描述（{round}/{max_rounds} 等变量自动替换）"

  - id: loop-step              # 循环占位 task
    loop: my_loop              # 引用 loop 定义
    dependencies: [step-1]

# 循环定义
loops:
  - id: my_loop
    max_rounds: 3
    min_rounds: 1
    default_body: default
    on_pass: complete
    on_exhaust: needs_review

    bodies:
      default:
        - id: work
          agent_id: exec_agent
          task_type: research
          dependencies: []
        - id: review
          agent_id: reviewer
          task_type: section-review
          dependencies: [work]

    assess:
      ref: review
      inputs:
        - kind: goal
        - kind: phase.deliverable
          phase: work

    transition:
      - when: deliverable_marker
        task: review
        marker: 'REVIEW: PASS'
        action: exit
        outcome: complete
      - when: deliverable_marker
        task: review
        marker: 'REVIEW: FAIL'
        action: continue
        next_body: revise
      - when: exhausted
        action: exit
        outcome: needs_review

    fallback_until:
      - type: deliverable_marker
        task: review
        marker: 'REVIEW: PASS'
```

### 3.3 Loop 执行流程与 KPI

```
每轮执行流程：
  Step 1: instantiate_round_body_tasks(spec, round_num, body_key)
  Step 2: seed_patch_baseline（汲取上一轮 work 交付物为初稿）
  Step 3: persist_tasks + topological_order + 调度
  Step 4: 执行 body 内所有 task（同波次依赖感知）
  Step 5: evaluate_transition()（按规则判断）
  Step 6: action = exit(complete/needs_review) | continue(next_body)
```

| 业务流程步骤 | KPI | 目标值 | 测量方式 |
|:------------|:----|:------|:---------|
| 1. 实例化 | **KPI-3.3a**：task id 格式正确（loop_id-rN-body_id） | 100% | 检查 task id 命名 |
| 2. 汲取初稿 | **KPI-3.3b**：第 2+ 轮正确复制上一轮 work 交付物 | 100% | 文件内容对比 |
| 3. 调度 | **KPI-3.3c**：body 内 DAG 拓扑排序正确 | 100% | 统计依赖顺序 |
| 4. 执行 | **KPI-3.3d**：同波次无依赖 task 并行执行墙钟 < 串行之和 | 验证 | 对比并行 vs 串行 |
| 5. 评估 | **KPI-3.3e**：transition 4 种条件（deliverable_marker/gate_passed/task_status/exhausted）均可用 | 4 种 | 枚举测试 |
| 6. 跳转 | **KPI-3.3f**：min_rounds 未达时 exit 强制 continue 正确触发 | 100% | 边界测试 |

### 3.4 Workflow 校验 7 项检查

| 检查项 | 说明 | KPI |
|:-------|:-----|:----|
| 1. DAG 无环 | 拓扑排序不报错 | **KPI-3.4a**：有环时明确提示「依赖存在环」 |
| 2. Agent 存在 | agent 在 agents_registry 中 | **KPI-3.4b**：缺失时提示「Agent X 不存在，请先在管理 Tab 创建」 |
| 3. task_type 已注册 | task_type 在 templates.yaml 中 | **KPI-3.4c**：缺失时提示「未知 task_type「X」」 |
| 4. Agent 能力绑定 | agent 已配置对应 task_type | **KPI-3.4d**：缺失时提示「X 未配置 task_type「Y」」 |
| 5. reviewer 在名册 | reviewer 在 roster 中 | **KPI-3.4e**：缺失时提示「reviewer X 不在团队名册中」 |
| 6. template 存在 | template_id 对应 delivery_template | **KPI-3.4f**：缺失时提示「未找到交付模板 X」 |
| 7. loop 结构正确 | body id 无重复、assess.ref 在 body 内 | **KPI-3.4g**：错误时明确提示具体问题 |

### 3.5 多 Agent 并行评审模式

```
一轮 body:
  work (research) ─┬──→ review-product (product)
                    │
                    └──→ review-arch (arch)
                          ↓
                    review-summary (main)

transition 规则：
  - review-summary 含 "REVIEW: PASS" → exit(complete)
  - review-summary 含 "REVIEW: FAIL" → continue(下一轮)
  - 耗尽 → exit(needs_review)
```

| KPI | 说明 | 目标值 |
|:----|:-----|:------|
| **KPI-3.5a** | 并行评审的墙钟时间 < 最慢 reviewer × 2 | 验证 |
| **KPI-3.5b** | 多个 reviewer 可以同时执行（不互相等待） | 验证 |
| **KPI-3.5c** | review-summary 正确合并多个 reviewer 意见 | 验证 |

### 3.6 Workflow 消费方式

| 方式 | 入口 | 场景 | KPI |
|:----|:-----|:-----|:----|
| Kernel 命令行 | `run_kernel.py --workflow <id> --goal "..."` | CLI 执行 | **KPI-3.6a**：命令行执行成功退出码 = 0 |
| Hub API | `POST /api/projects/run { workflow, goal }` | UI 创建项目 | **KPI-3.6b**：API 返回 200 且项目状态为 completed |
| Workflow Editor | UI 中配置后保存+启动 | 配置后即运行 | **KPI-3.6c**：编辑器保存后 workflow YAML 格式正确 |

---

## 4. 质量保证体系与各环节 KPI

### 4.1 两层质量划分

```
质量 = A 类（结构性，机器判） + B 类（内容性，Agent 判）
```

| 类别 | 判断方式 | 责任方 | 特征 | KPI |
|:----:|:--------|:------|:----|:----|
| **A 类** | 确定性机器判 | Gate | 可观测、可量化、不依赖主观判断；正则/解析/计数 | **KPI-4.1a**：Gate 可判的 A 类缺陷不进 review，拦截率 100% |
| **B 类** | 需要领域知识 | Reviewer Agent | 推断是否合理、数据是否过时、建议是否可执行 | **KPI-4.1b**：reviewer 不重复报告 A 类问题 |

**关键原则**：A 类由 Gate 拦，不进 review；B 类才用 review，review 不重复 A 类。预期 review 轮次从 3 降到 1。

### 4.2 Gate 门禁体系

#### 4.2.1 三层门禁

```
check_execute(response):
  1. check_contract(response)        ← 契约门禁：Pydantic 结构校验
  2. check_format(spec, content)     ← 格式门禁：章节/防 stub/文件/质量约束
  3. check_action_evidence(spec)     ← 证据门禁：URL/截图（仅 action 型）
  + check_code_project(spec, dir)    ← 代码项目门禁（仅 code_project 型）
```

| 门禁层 | KPI | 目标值 | 测量方式 |
|:-------|:----|:------|:---------|
| 契约门禁 | **KPI-4.2a**：非法结构（缺字段/类型错误）100% 拦截 | 100% | 构造非法样本测试 |
| 格式门禁 | **KPI-4.2b**：缺章节/防 stub/缺文件 100% 拦截 | 100% | 构造缺章节样本 |
| | **KPI-4.2c**：合法内容误拦率 ≤ 5% | ≤ 5% | 统计误拦比例 |
| 证据门禁 | **KPI-4.2d**：缺 URL/截图时 100% 拦截 | 100% | 构造缺证据样本 |
| 代码项目门禁 | **KPI-4.2e**：缺文件/扩展名错误 100% 拦截 | 100% | 构造缺文件样本 |

#### 4.2.2 Gate 重试流程与 KPI

```
Gate 不通过 → 结构化 feedback → 重试（最多 max_gate_retries 次）→ 通过或耗尽
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 分类 | **KPI-4.2f**：feedback 按 format_only/structural/content 三分类 | 3 类 | 检查分类逻辑 |
| 2. 引导 | **KPI-4.2g**：pattern_guidance 对不同 pattern 给出不同修复指引 | 验证 | 枚举 pattern |
| 3. 重试 | **KPI-4.2h**：重试时复用已有会话（session_id 传递正确） | 100% | 检查 session_id |
| 4. 耗尽 | **KPI-4.2i**：耗尽后正确触发 Process triage（gate_exhausted 标记） | 100% | 检查 fail_reason |

#### 4.2.3 约束绑定方式

```
交付模板（delivery_template）← 约束写在这里
  └── check_rules:
        required_sections: [章节A, 章节B]
        stub_floor: 200
        source_inline_required: true
        dimension_coverage: [维度1, 维度2]

task_type ← 关联模板
  └── template_id: research-report（task 带 template_id 时走模板 check_rules）
  └── 无 template_id 时：走 task_type base check_rules
```

**KPI-4.2j**：绑定解析正确率（带 template_id 时走模板规则，不带时走 base 规则） = 100%

### 4.3 Review 评审体系

#### 4.3.1 单步 review 流程与 KPI

```
execute 通过 Gate → quality_status（自评）
  → self-assessment score < quality_floor(0.6) → needs_review
  → known_gaps 非空 → needs_review

review 流程：
  1. 自动分配 reviewer → 2. 注入交付物+标准 → 3. 评审返回
  → 4. PASS → 完成 | FAIL → 5. rework → 重走 execute → Gate → 再评审
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 自动分配 | **KPI-4.3a**：reviewer 自动分配排除执行者和协调者 | 验证 | 检查分配结果 |
| | **KPI-4.3b**：优先选能处理该 task_type 的 Agent | 验证 | 检查能力匹配 |
| 2. 注入 | **KPI-4.3c**：reviewer prompt 包含交付物 + acceptance_criteria + template 章节 | 3 项 | 检查 prompt 结构 |
| 3. 评审 | **KPI-4.3d**：reviewer 必须返回 PASS/FAIL + feedback | 100% | 检查响应结构 |
| 4. PASS | **KPI-4.3e**：首轮 review 通过率 ≥ 80% | 80% | 统计 |
| 5. rework | **KPI-4.3f**：rework prompt 含"仅修指出的问题，不重写全文" | 验证 | 检查 prompt 结构 |
| | **KPI-4.3g**：rework 后 Gate 通过率（不通过则需 review） | ≥ 90% | 统计 |
| 6. 耗尽 | **KPI-4.3h**：max_review_retries 耗尽后状态为 needs_review（不阻塞） | 正确 | 检查状态转换 |

#### 4.3.2 多 Agent 评审流程与 KPI

```
workflow 的 loop 定义更灵活的多 Agent 评审：
  - 多个 reviewer 并行评审（product + arch → summary）
  - transition 规则控制流程（PASS → exit, FAIL → continue）
  - assess task 可注入 goal + 各 phase 交付物
  - min_rounds 确保至少 X 轮评审
  - max_rounds 防止无限循环
  - 多 body 分支（draft → revise → final）
```

| KPI | 说明 | 目标值 |
|:----|:-----|:------|
| **KPI-4.3i** | 多个 reviewer 并行评审时，墙钟时间 = 最慢 reviewer | 验证 |
| **KPI-4.3j** | transition 规则按有序匹配，不跳过 | 100% |
| **KPI-4.3k** | min_rounds 未达时，非 pass 的 exit 强制 continue | 100% |

#### 4.3.3 群讨论对齐流程与 KPI

```
Work-Review FAIL → 群讨论对齐 → 产出定点改稿清单 → work Agent 定点 PATCH → 下一轮 review
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 触发 | **KPI-4.3l**：review FAIL 后正确触发群讨论（profile 配置正确） | 100% | 检查事件日志 |
| 2. 对齐 | **KPI-4.3m**：群讨论在 ≤ 5 轮对话内达成一致 | 5 轮 | 统计对话轮次 |
| 3. 清单 | **KPI-4.3n**：产出"定点改稿清单"，格式为可执行条目 | 验证 | 检查清单格式 |
| 4. PATCH | **KPI-4.3o**：work Agent 按清单定点修改，不重写未列出的内容 | 验证 | diff 对比 |

### 4.4 Rubric 自动化评估

```
不阻塞流程，仅记录+打分。
- evaluate_task_output() → 按维度打分
- record_rubric_result() → 记录到 store
- 命中红线（redlines）时记录告警
- Agent 端通过 inject_rubric_block 知晓评估标准
```

| KPI | 说明 | 目标值 |
|:----|:-----|:------|
| **KPI-4.4a** | rubric 评估阻塞流程 = 0（不阻塞才算达标） | 不阻塞 |
| **KPI-4.4b** | rubric 评分记录到 store 的成功率 | 100% |
| **KPI-4.4c** | 命中红线时正确记录告警 | 验证 |

### 4.5 质量数据沉淀

```
每条 task 完成时记录：
- quality_score（Agent 自评）
- gate_passed（是否通过 Gate）
- review_result（skipped / passed / failed）
- rubric 维度评分
- lessons（gate 重试后成功的经验 → KB ledger）
```

**KPI-4.5**：每条完成的 task 必须完整记录上述 5 项数据，缺失率 = 0%

---

## 5. Agent 执行机制与各环节 KPI

### 5.1 CLI 后端

Agent 通过 CLI 后端执行，目的是**吃到 CLI 本身功能升级的红利**：

| CLI 后端 | Skill 目录 | MCP 配置 | 适配器 |
|:---------|:----------|:---------|:-------|
| opencode | `workspace/.opencode/skills/` | `workspace/.opencode/mcp.json` | `adapter/opencode/` |
| claude | `workspace/.claude/skills/` | `workspace/.claude/mcp.json` | `adapter/claude/` |

**KPI-5.1a**：opencode 和 claude 双后端对标准 task 执行成功率 = 100%  
**KPI-5.1b**：Agent 的 CLI 配置与用户默认 CLI 完全隔离，互不影响

### 5.2 Skill 挂载流程与 KPI

```
技能挂载流程：
  1. 用户配置 agents_registry.json → agent.skills
  2. sync_workspace_skills() 读取配置
  3. 清空 workspace 中未被 registry 包含的 skill 目录
  4. 对每个配置的 skill，建立到 business/skills/<id>/ 的符号链接
  5. 写入 .myteam-skills.json manifest
  6. CLI 启动时自动加载 .opencode/skills/ 下所有 SKILL.md
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 配置 | **KPI-5.2a**：registry 配置的 skill 列表同步到 workspace 成功率 | 100% | 检查 manifest |
| 2. 同步 | **KPI-5.2b**：多出的 skill 目录被正确清理（不遗留） | 100% | 统计残留 |
| 3. 链接 | **KPI-5.2c**：符号链接建立正确，目标路径存在 | 100% | 检查链接 |
| 4. 加载 | **KPI-5.2d**：CLI 启动后 SKILL.md 被 Agent 读取 | 验证 | 跟踪 thinking trace |

### 5.3 MCP 挂载流程与 KPI

```
MCP 库（管理面板 CRUD） → registry 配置 → sync_workspace_mcp() → workspace/.opencode/mcp.json → CLI 启动加载
```

**KPI-5.3a**：MCP 配置同步到 workspace 成功率 = 100%  
**KPI-5.3b**：Agent 的 MCP 配置与用户默认 CLI 完全隔离

### 5.4 Prompt 注入流程与 KPI

```
execute 前，prompt 按顺序注入：
  1. Experience hints    ← KB ledger 中同类任务经验
  2. Lesson hints        ← gate 重试后成功 lessons（默认关）
  3. Umbrella skill      ← task_type 对应的方法论 SKILL.md
  4. Reference pointers  ← umbrella skill 的引用资产
  5. L1 memory           ← 短期对话记忆中相关内容
  6. Preferences         ← USER.md 中的用户偏好
  7. KB top-k            ← 知识库中匹配条目
  8. Rubric block        ← 质量评估标准
```

| 注入块 | KPI | 目标值 | 测量方式 |
|:-------|:----|:------|:---------|
| 1. Experience | **KPI-5.4a**：有经验时注入，无经验时不注入空块 | 验证 | 检查 prompt 内容 |
| 2. Lesson | **KPI-5.4b**：默认关，打开后正确注入 | 验证 | 检查配置开关 |
| 3. Umbrella skill | **KPI-5.4c**：task_type 有对应 umbrella_skill 时注入正文 | 验证 | 检查 prompt 内容 |
| 4. References | **KPI-5.4d**：有引用资产时注入，无时不注入 | 验证 | 检查 prompt 内容 |
| 5. L1 | **KPI-5.4e**：有相关记忆时注入，无时不注入空块 | 验证 | 检查 prompt 内容 |
| 6. Preferences | **KPI-5.4f**：有偏好时注入，无偏好时不注入空块 | 验证 | 检查 prompt 内容 |
| 7. KB | **KPI-5.4g**：有匹配条目时注入 top-k，无匹配时不注入 | 验证 | 检查 prompt 内容 |
| 8. Rubric | **KPI-5.4h**：始终注入 rubric 评估标准 | 100% | 检查 prompt 内容 |

**KPI-5.4i**：全部注入块由 execution_harness.config 控制开关，默认只开 umbrella_skill + rubric

### 5.5 交互协议

```
AgentPort.run(request) →
  1. 写 .trigger 文件（含 InteractionRequest JSON）
  2. Transport 投递给 CLI（opencode/claude）
  3. CLI 启动 Agent 会话，Agent 读取 .trigger 后开始任务
  4. Agent 通过 submit_result.py 本地校验 + 原子写 .response
  5. AgentPort 看门狗监控：等待事件流 / 检测超时
  6. 读到合法 .response → 返回 AgentPortResult
```

| 流程步骤 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 写 trigger | **KPI-5.5a**：.trigger 文件格式正确，InteractionRequest 完整 | 100% | 检查文件内容 |
| 2. 投递 | **KPI-5.5b**：Transport 成功启动 CLI 子进程 | 100% | 检查进程 |
| 3. 响应 | **KPI-5.5c**：Agent 能正确读取 .trigger 并开始执行 | 100% | 检查事件流 |
| 4. 提交 | **KPI-5.5d**：submit_result.py 本地校验 + 原子写 .response 成功率 | 100% | 检查文件 |
| 5. 监控 | **KPI-5.5e**：看门狗 soft_idle 正确告警，hard_idle 正确取消+重试 | 验证 | 注入超时测试 |
| 6. 返回 | **KPI-5.5f**：读到合法 .response 后才返回，不返回空/错误结果 | 100% | 检查返回状态 |

### 5.6 Agent 配置

```json
{
  "agents": {
    "research": {
      "name": "研究员",
      "role": "specialist",
      "description": "市场调研与竞品分析",
      "backend": "opencode",
      "model": "claude-opus-4-7",
      "task_types": ["research", "custom-survey"],
      "skills": ["research_methodology", "data_analysis_methodology"],
      "mcp_servers": ["web-search", "web-fetch"]
    }
  }
}
```

**KPI-5.6**：全部 7 个配置项（name/role/description/backend/model/task_types/skills/mcp_servers）均可在管理 UI 编辑，缺一不可

---

## 6. Agent 能力生态与覆盖度 KPI

> **框架提供"怎么做"的机制，Skill/MCP/TaskType/Template 提供"用什么做、做成什么样"的内容。**

### 6.1 Skill 体系

#### 6.1.1 Skill 结构

```
business/skills/<skill-id>/
├── SKILL.md        ← 核心方法论
├── checklist.md    ← 可选：检查清单
└── docs/           ← 可选：参考文档
```

**KPI-6.1a**：每个 Skill 的 SKILL.md 必须有 frontmatter（name + description）+ 正文（何时启用 + 工作流程）

#### 6.1.2 Skill 覆盖度 KPI

| 维度 | KPI | 当前值 | 目标值 | 测量方式 |
|:----|:----|:------|:------|:---------|
| **挂载率** | **KPI-6.1b**：被至少一个 Agent 挂载的 Skill 比例 | 9/66（13.6%） | ≥ 80% | 统计 agents_registry 中 skill 引用 |
| **映射率** | **KPI-6.1c**：每个 task_type 至少有一个 umbrella_skill | 0/6（0%） | 100% | 检查 umbrella_skill 映射 |
| **有效性** | **KPI-6.1d**：有 Skill 引导时 Gate 通过率显著高于无 Skill | 基线 | +20% | A/B 对比测试 |
| **冗余度** | **KPI-6.1e**：无重复 Skill（同一方法论只保留一个） | 67 个 | 清理后 ≤ 40 个 | 人工审核 |

#### 6.1.3 Skill 来源

| 来源 | 说明 | KPI |
|:----|:-----|:----|
| **自建** | 根据业务需求自行编写 | **KPI-6.1f**：自建 Skill 的 frontmatter 完整率 100% |
| **第三方** | 社区/开源方法论，适配后使用 | **KPI-6.1g**：第三方 Skill 须注明来源，无来源的不可入库 |
| **Agent 沉淀** | 项目完成后 `skill_extract` 自动提炼 | **KPI-6.1h**：skill_extract 产出格式正确，可被重新挂载 |

### 6.2 MCP 生态

| MCP 类型 | 功能 | 来源策略 | KPI |
|:---------|:-----|:---------|:----|
| **Web 搜索** | 获取实时信息 | 第三方 | **KPI-6.2a**：至少 1 个可用的搜索 MCP |
| **文件读写** | 读写本地/远程文件 | 内置 | 内置 |
| **数据库** | 查询/写入数据库 | 第三方 | **KPI-6.2b**：至少 1 个可用的数据库 MCP |
| **API 调用** | 与外部系统交互 | 第三方 | **KPI-6.2c**：至少 1 个可用的 API MCP |
| **代码执行** | 沙箱运行代码 | 内置或第三方 | **KPI-6.2d**：至少 1 个可用的代码执行 MCP |
| **浏览器** | 页面抓取 / E2E 测试 | 第三方 | **KPI-6.2e**：至少 1 个可用的浏览器 MCP |

**KPI-6.2f**：MCP 库管理面板支持 CRUD 操作，新增/编辑/删除/列表 全部可用  
**KPI-6.2g**：Agent 的 MCP 配置与用户默认 CLI 完全隔离

### 6.3 TaskType 与交付模板体系

#### 6.3.1 当前已有 TaskType

| TaskType | 用途 | 模板 | check_rules | 状态 |
|:---------|:-----|:-----|:------------|:-----|
| `research` | 竞品调研 | `research-report` | ✅ | ✅ 有 check_rules |
| `section-review` | 同行评审 | `review-report` | ✅ | ✅ 有 acceptance_criteria |
| `custom-survey` | 自定义调研 | 无 | ❌ | ⚠️ 基础 |
| `data-analysis` | 数据分析 | 无 | ❌ | ⚠️ 基础 |
| `feature-design` | 功能设计 | 无 | ❌ | ⚠️ 基础 |
| `code-deliverable` | 代码交付 | 无 | ❌ | ⚠️ 基础 |

**KPI-6.3a**：每个 task_type 必须有 delivery_template（无模板的 task_type 不计入"已完成"）

#### 6.3.2 需要补齐的 TaskType

| TaskType | 适用场景 | 优先级 | 补齐 KPI |
|:---------|:---------|:------|:---------|
| `system-design` | 系统设计/架构文档 | 高 | **KPI-6.3b**：3 个月内完成 templates.yaml + delivery_template + Agent 绑定 |
| `requirement-analysis` | 需求分析文档 | 高 | **KPI-6.3c**：3 个月内完成 |
| `decision-record` | 决策记录（ADR） | 高 | **KPI-6.3d**：3 个月内完成 |
| `acceptance-report` | 验收报告 | 中 | **KPI-6.3e**：6 个月内完成 |
| `test-plan` | 测试计划 | 中 | **KPI-6.3f**：6 个月内完成 |
| `incident-report` | 事故复盘 | 中 | **KPI-6.3g**：6 个月内完成 |
| `strategy` | 策略/方案文档 | 中 | **KPI-6.3h**：6 个月内完成 |
| `creative-writing` | 创意写作 | 低 | 无硬性时限 |
| `translation` | 翻译 | 低 | 无硬性时限 |

**KPI-6.3i**：每个新 task_type 至少需要 4 项（templates.yaml 定义 + delivery_template + Agent 绑定 + umbrella_skill），缺项不计入完成

### 6.4 生态建设策略

#### 6.4.1 不要自己造车轮

| 要做的 | 不要做的 |
|:-------|:---------|
| 写方法论 SKILL（Agent 怎么做某类工作） | 自己实现搜索 MCP（用现成的） |
| 写 check_rules（质量门槛） | 自己实现浏览器 MCP（用 Playwright 等） |
| 配置 and 维护 MCP 服务器列表 | 自研数据库 MCP（用社区版） |
| 编排 workflow（串联协作） | 自研代码执行沙箱（用 sandbox MCP） |

**KPI-6.4a**：自研 MCP 数量 = 0（全部使用第三方或内置）

#### 6.4.2 建设路径 KPI

| Phase | 目标 | 完成 KPI |
|:------|:-----|:---------|
| **Phase 1**：核心缺失补齐 | 3-5 个高频 task_type（system-design/requirement-analysis/decision-record） | **KPI-6.4b**：每个新 task_type 配基础 check_rules + delivery_template |
| **Phase 2**：Skill 质量提升 | 清理 Skill 库 + 建立 umbrella_skill 映射 | **KPI-6.4c**：Skill 清理后 ≤ 40 个，映射率 ≥ 80% |
| **Phase 3**：第三方集成 | 整理 MCP 列表 + 接入指南 | **KPI-6.4d**：管理面板支持一键添加常见 MCP |
| **Phase 4**：内容生态 | 用户自定义 + 导入导出 | **KPI-6.4e**：支持 template 导入/导出 |

---

## 7. 记忆与知识体系与各钩子 KPI

### 7.1 记忆堆栈总览

```
memstack/
├── l1/              ← 短期对话记忆（L1 Memory）
│   ├── mem0/        ← external mem0 后端
│   ├── native/      ← 原生实现
│   ├── sqlite/      ← SQLite 后端
│   └── noop/        ← 空操作（关闭）
│
├── kb/              ← 长期知识库（Knowledge Base）
│   ├── sqlite       ← SQLite 实现（当前默认）
│   └── gbrain       ← gbrain 实现
│
├── preferences/     ← 用户偏好库
│   ├── static/      ← 静态 MD 文件（USER.md）
│   ├── sectioned/   ← 分节存储
│   └── user_store/  ← 每个用户独立存储
│
└── orchestration/   ← 编排层
    ├── experience   ← 同类任务经验检索注入
    └── context      ← 各场景上下文定义
```

### 7.2 记忆注入钩子 KPI

| 钩子 | 触发时机 | 读取源 | 写入源 | KPI |
|:----|:--------|:-------|:-------|:----|
| H1 on_chat_turn | 私聊/群聊每轮 | L1 memory + Preferences | 对话完成后自动存 | **KPI-7.2a**：对话记录自动存入 L1（有记忆后端时） |
| H2 on_task_success | execute 成功 | — | promote + lesson + rubric | **KPI-7.2b**：task 完成后 promote 成功，lesson 在 gate 重试>1 时写入 |
| H3 inject_for_execute | execute 前 | KB + L1 + Preferences + Experience | — | **KPI-7.2c**：注入的条目与 task_type 匹配，不注入无关内容 |
| H4 on_project_complete | 项目完成 | — | 项目复盘 → KB | **KPI-7.2d**：项目完成后复盘写入 KB 成功 |
| H5 on_consensus | 圆桌共识通过 | — | 最佳实践 → KB | **KPI-7.2e**：共识通过后 best_practice 写入 KB 成功 |

### 7.3 用户-Agent 共享知识库（目标设计）

**现状问题**：KB 只有 Agent 端写入口（任务完成自动沉淀），用户无法把自己的经验/信息写入 KB 并让 Agent 共享。

**目标方案**：

```
KB 条目结构：
- title: 知识标题
- content: 知识正文
- tags: [类别标签]（用于搜索命中）
- project_id: 所属项目（""=全局，对所有人可见）
- source: "user" | "agent" | "auto"
- created_by: 创建者（用户ID 或 Agent ID）
```

| 实现要点 | KPI | 目标值 | 测量方式 |
|:---------|:----|:------|:---------|
| 1. 用户写入 | **KPI-7.3a**：管理面板 KB 页面支持"我的知识库"类型，自由写 title + content + tags | 可用 | 功能测试 |
| 2. Agent 写入 | **KPI-7.3b**：现有自动沉淀（on_task_complete + on_project_complete）保留 | 不变 | 回归测试 |
| 3. 私聊沉淀 | **KPI-7.3c**：用户在私聊中说"记住这个" → 自动将对话上下文存入 KB | 可用 | 功能测试 |
| 4. 读取注入 | **KPI-7.3d**：fetch_kb_entries() 扩展搜索所有 source 类型的条目 | 可用 | 验证 |
| 5. 标签匹配 | **KPI-7.3e**：用户 KB 条目按 task_type 标签匹配，精确命中 | 验证 | 检查注入内容 |
| 6. 使用率 | **KPI-7.3f**：用户写入的 KB 条目在 7 天内被 Agent 检索命中率 ≥ 50% | 50% | 统计 |

### 7.4 偏好库 KPI

| 功能 | 当前形态 | 改进方向 | KPI |
|:----|:---------|:---------|:----|
| 存储 | 团队级别，不按用户区分 | 支持多用户各自的偏好 | **KPI-7.4a**：支持按用户 ID 存偏好 |
| 维度 | 全局偏好 | 支持按 Agent 维度分 | **KPI-7.4b**：支持"对 research Agent 我希望…" |
| 打通 | 偏好库独立 | 偏好/KB 打通 | **KPI-7.4c**：用户偏好自动转为 KB 标签条目 |

---

## 8. Hub 与 UI 可用性 KPI

### 8.1 API 端点可用性

| 路由组 | 功能 | KPI |
|:------|:-----|:----|
| `/api/chat/{agent_id}` | 私聊 Agent（SSE 流） | **KPI-8.1a**：SSE 连接正确建立，消息流式推送 |
| `/api/groups/*` | 群聊管理 | **KPI-8.1b**：CRUD 全部可用 |
| `/api/projects/*` | 项目管理 | **KPI-8.1c**：创建/启动/跟踪/取消全部可用 |
| `/api/workflows/*` | Workflow CRUD | **KPI-8.1d**：CRUD + 校验全部可用 |
| `/api/agents/*` | Agent 管理 | **KPI-8.1e**：CRUD + 配置全部可用 |
| `/api/task-types/*` | TaskType CRUD | **KPI-8.1f**：CRUD + 约束列表全部可用 |
| `/api/delivery-templates/*` | 交付模板 CRUD + 约束全集 | **KPI-8.1g**：CRUD + 约束注册表全部可用 |
| `/api/delivery-profiles/*` | 交付配置管理 | **KPI-8.1h**：CRUD 全部可用 |
| `/api/skills/*` | Skill 库管理 | **KPI-8.1i**：目录/分类/导入/审批全部可用 |
| `/api/mcp/*` | MCP 服务器管理 | **KPI-8.1j**：CRUD 全部可用 |
| `/api/memory/*` | 知识库条目 CRUD | **KPI-8.1k**：CRUD + 搜索全部可用 |
| `/api/preferences/*` | 偏好库管理 | **KPI-8.1l**：CRUD + 分节编辑全部可用 |
| `/api/prompt-templates/*` | Prompt 模板管理 | **KPI-8.1m**：CRUD 全部可用 |
| `/api/config/*` | 系统/Skill/Backend 配置 | **KPI-8.1n**：读写全部可用 |
| `/api/observability/*` | 可观测性 | **KPI-8.1o**：事件/审计/用量查询全部可用 |
| `/api/obs/*` | 过程事件 SSE | **KPI-8.1p**：SSE 正确推送过程事件 |

**KPI-8.1q**：全部 API 端点返回 200（正常）或 4xx（有明确错误信息），不返回 500

### 8.2 前端功能页可用性

| 页面 | 路径 | 核心功能 | KPI |
|:----|:-----|:---------|:----|
| 私聊 | `/chat/:agentId` | 与单个 Agent 对话 | **KPI-8.2a**：消息发送 + SSE 接收 + 历史记录 |
| 群聊 | `/groups/:groupId` | 群组聊天 + 圆桌讨论 | **KPI-8.2b**：消息发送 + 圆桌发起 + 共识投票 |
| 项目 | `/projects/` | 创建/查看/跟踪项目 | **KPI-8.2c**：创建 + 状态跟踪 + 交付物查看 |
| Workflow 编辑器 | `/workflows/:id` | 可视化编排 DAG + loops + 配置 | **KPI-8.2d**：DAG 编辑 + loop 配置 + 保存 + 校验 |
| 管理-Agent | `/manage/agents` | Agent 配置/模型/Skill/MCP 绑定 | **KPI-8.2e**：CRUD + 配置编辑 |
| 管理-TaskType | `/manage/task-types` | 任务类型 + 交付模板编辑 | **KPI-8.2f**：CRUD + 约束编辑 |
| 管理-Prompt 模板 | `/manage/prompt-templates` | 按 task_type/kind 的 prompt 模板 | **KPI-8.2g**：CRUD |
| 管理-偏好 | `/manage/preferences` | 用户偏好分节编辑 | **KPI-8.2h**：分节 CRUD + 聚合 USER.md |
| 管理-知识库 | `/manage/knowledge` | KB 条目 CRUD | **KPI-8.2i**：CRUD + 搜索 |
| Skills 库 | `/skills/` | 全部 Skill 目录浏览/管理 | **KPI-8.2j**：目录 + 分类 + 导入 + 审批 |
| MCP 库 | `/mcp/` | MCP 服务器管理 | **KPI-8.2k**：CRUD |

**KPI-8.2l**：全部功能页加载正常，无白屏/崩溃/JS 错误

---

## 9. 用户可配置项与完备度 KPI

| 配置项 | 位置 | 说明 | KPI |
|:------|:-----|:------|:----|
| Agent | `agents_registry.json` + 管理 UI | 名称、角色、CLI 后端、模型、task_types、skills、mcp_servers | **KPI-9a**：7 项配置项均可在 UI 编辑 |
| TaskType | `templates.yaml` + 管理 UI | 名称、交付模板、check_rules、acceptance_criteria | **KPI-9b**：CRUD 全部可用 |
| 交付模板 | `delivery_templates/*.yaml` + 管理 UI | 章节结构、check_rules、acceptance_criteria | **KPI-9c**：章节编辑 + 约束可视化编辑 |
| Workflow | `workflows/*.yaml` + WorkflowEditor | DAG、loops、options、collaboration | **KPI-9d**：可视化编辑 + 校验 |
| Delivery Profile | `config/` + 管理 UI | 过程产物检查规格 | **KPI-9e**：CRUD |
| Prompt 模板 | `prompt_templates.yaml` + 管理 UI | 按 kind + task_type 的 prompt | **KPI-9f**：CRUD |
| Skill 挂载 | 管理 UI | 每个 Agent 可用的 Skill | **KPI-9g**：勾选即生效 |
| MCP 挂载 | 管理 UI | 每个 Agent 可用的 MCP 服务器 | **KPI-9h**：勾选即生效 |
| 偏好 | UI PreferencesPanel | 用户偏好分节 → USER.md | **KPI-9i**：分节编辑 + 自动聚合 |
| 知识库 | UI KnowledgePanel | KB 条目 CRUD | **KPI-9j**：CRUD + 搜索 |
| 系统配置 | `system_config.json` | 端口、默认后端、模型列表 | **KPI-9k**：UI 可读可写 |

**KPI-9l**：全部 11 项配置项，每项都有对应的 UI 编辑入口，且编辑后持久化成功

---

## 10. 未完成项与实现路线

### 10.1 当前已实现的功能

- [x] Process 内核（DAG 驱动 + state machine + retry/triage）
- [x] Gate 三层门禁（contract + format + evidence）
- [x] Registry + FormatSpec（约束收敛 + 模板覆盖）
- [x] Workflow 系统（加载、校验、实例化）
- [x] Loop 运行时（多轮循环 + transition + assess）
- [x] 多 Agent 并行评审模式（competitive-research-review.yaml）
- [x] AgentPort + Transport（opencode + claude 双后端）
- [x] Skill 挂载（opencode .opencode/skills/ + claude .claude/skills/）
- [x] MCP 挂载
- [x] Hub API（全部路由已实现）
- [x] 后端管理 UI（Agent/TaskType/Template/Prompt/Skill/MCP）
- [x] 私聊 Agent
- [x] 群聊 + 圆桌讨论 + 共识沉淀
- [x] L1 记忆（多后端）
- [x] 知识库（sqlite + gbrain）
- [x] 偏好库（分节 + USER.md）
- [x] 经验复用（KB ledger → execute inject）
- [x] Prompt 注入体系
- [x] Rubric 自动化评估
- [x] 群讨论对齐（work-review-alignment）
- [x] 断点续跑（D8 恢复）
- [x] Budget 控制（降级 + 硬停）
- [x] 审计日志 + 可观测性

### 10.2 待完成项与达标 KPI

#### P0 — 核心质量链路验证

| 待完成项 | 达标 KPI |
|:---------|:---------|
| workflow-creator SKILL.md 修复 | **KPI-P0a**：清理头部 106 行污染，修复后文件结构正确 |
| Gate + review 链路端到端验证 | **KPI-P0b**：跑完 sop-to-workflow → workflow-creator → 启动 workflow → Gate 拦截 → review 兜底 → 完成，全流程无报错 |
| review+rework 定点修改验证 | **KPI-P0c**：Agent 重做时 diff 仅修改反馈指出的内容，不修改其他章节 |

#### P1 — 共享知识库

| 待完成项 | 达标 KPI |
|:---------|:---------|
| 用户 KB 写入入口 | **KPI-P1a**：管理面板 KB 页面支持"我的知识库"类型，自由写 title + content + tags |
| 私聊沉淀 | **KPI-P1b**：用户在私聊中说"记住这个" → 自动存入 KB |
| KB 读取注入增强 | **KPI-P1c**：fetch_kb_entries() 扩展搜索范围，用户 KB 条目按标签匹配注入 |
| source/created_by 字段 | **KPI-P1d**：KB 条目有 source 字段（user/agent/auto） |

#### P2 — 偏好库增强

| 待完成项 | 达标 KPI |
|:---------|:---------|
| 多用户偏好 | **KPI-P2a**：支持按用户 ID 存偏好，非全局 "default" |
| 偏好按 Agent 维度 | **KPI-P2b**：支持"对 research Agent 我希望…" |
| 偏好/KB 打通 | **KPI-P2c**：用户偏好自动转为 KB 标签条目 |

#### P3 — 质量约束完善

| 待完成项 | 达标 KPI |
|:---------|:---------|
| 确定约束全集边界 | **KPI-P3a**：明确 A 组（框架通用）与 B/C/D 组（模板业务）的边界 |
| 约束所见即所验 | **KPI-P3b**：UI 配置的约束 = Gate 真验的约束，不出现"配了不验"或"验了不能配" |
| 更多模板填充 | **KPI-P3c**：至少有 3 个 task_type 有完整 check_rules |

#### P4 — 工具链

| 待完成项 | 达标 KPI |
|:---------|:---------|
| workflow-creator 自动验证 | **KPI-P4a**：Agent 生成 workflow 后自动跑 validate_workflow()，通过才写入 |
| 自动配置缺失项 | **KPI-P4b**：workflow 创建时自动检测并配置缺失的 task_type 和 agent 绑定 |
| 端到端自动化规程 | **KPI-P4c**：sop-to-workflow → workflow-creator 全流程自动化，无需人工干预中间步骤 |

#### P5 — Agent 能力生态建设

| 待完成项 | 达标 KPI |
|:---------|:---------|
| 补齐高频 task_type | **KPI-P5a**：3 个月内完成 system-design/requirement-analysis/decision-record 的 template + check_rules + Agent 绑定 |
| 每个新 task_type 配 4 项 | **KPI-P5b**：templates.yaml 定义 + delivery_template + Agent 绑定 + umbrella_skill，缺项不计入完成 |
| 清理 Skill 库 | **KPI-P5c**：Skill 从 66 个清理到 ≤ 40 个，被映射率 ≥ 80% |
| 第三方 MCP 指南 | **KPI-P5d**：文档列出至少 5 个可用的第三方 MCP 及接入步骤 |
| 管理面板一键添加 MCP | **KPI-P5e**：管理面板支持从列表中选择常见 MCP 一键添加 |

---

## 11. 验证标准与 KPI 汇总表

### 11.1 总体 KPI 一览

| 编号 | KPI | 当前值 | 目标值 | 优先级 | 归属 |
|:----|:----|:------|:------|:------|:-----|
| 1.2a | 新 workflow 从创建到首次成功运行时长 | 未验证 | ≤ 30 分钟 | P0 | 定位 |
| 1.2b | Agent 一次通过 Gate 率 | 0% | ≥ 80% | P0 | 定位 |
| 1.3c | 平均 review 轮次 | 3 | ≤ 2 | P0 | 定位 |
| 1.3d | A 类问题被 review 兜底率 | 4/5 | 0% | P0 | 定位 |
| 1.3f | Skill 被映射率 | 13.6% | ≥ 80% | P5 | 生态 |
| 2.2b | 断点续跑正确率 | 未验证 | 100% | P0 | 架构 |
| 2.2j | 双后端标准 task 执行成功率 | 未验证 | 100% | P0 | 架构 |
| 3.1g | workflow 创建到运行总时长 | 未验证 | ≤ 30 分钟 | P0 | 流程 |
| 3.3a | loop task id 格式正确率 | 未验证 | 100% | P0 | 流程 |
| 3.4a-g | workflow 校验 7 项检查全部通过 | 未验证 | 100% | P0 | 流程 |
| 4.1a | A 类缺陷 Gate 拦截率 | 0% | 100% | P0 | 质量 |
| 4.2a | 非法结构契约门禁拦截率 | 未验证 | 100% | P0 | 质量 |
| 4.3e | 首轮 review 通过率 | 未验证 | ≥ 80% | P0 | 质量 |
| 4.3g | rework 后 Gate 通过率 | 未验证 | ≥ 90% | P0 | 质量 |
| 5.2a | Skill 同步成功率 | 未验证 | 100% | P0 | 执行 |
| 5.5f | 返回合法 .response 才返回 | 未验证 | 100% | P0 | 执行 |
| 6.1b | Skill 被映射率 | 13.6% | ≥ 80% | P5 | 生态 |
| 6.3a | 每个 task_type 有 delivery_template | 2/6 | 6/6 | P5 | 生态 |
| 7.3f | 用户 KB 条目 7 天使用率 | 0% | ≥ 50% | P1 | 记忆 |
| 8.1q | API 端点不返回 500 | 未验证 | 100% | P0 | Hub |
| 9l | 11 项配置项均有 UI 入口 | 部分 | 全部 | P0 | 配置 |

### 11.2 验证流程

每次迭代后按以下步骤验证：

```
Step 1: 运行测试套件
  PYTHONPATH=backend venv/bin/python3 -m pytest backend -q
  → 所有测试通过（KPI-2.2）

Step 2: 运行端到端 demo
  venv/bin/python3 backend/common/run_kernel.py --demo --backend opencode
  → 项目状态为 completed（KPI-1.2a, KPI-1.2b）

Step 3: 运行带 review 的 workflow
  venv/bin/python3 backend/common/run_kernel.py competitive-research-review \
    --goal "..." --review
  → review 轮次 ≤ 2（KPI-1.3c, KPI-4.3e）

Step 4: 检查 Gate 拦截
  → Gate 可判的缺陷不进 review（KPI-1.3d, KPI-4.1a）

Step 5: 检查 Skill 同步
  → 每个 Agent 的 workspace 中 skill 目录正确（KPI-5.2a）

Step 6: 检查 API
  → 所有 API 端点返回正常（KPI-8.1q）
```

### 11.3 完成标准

myteam 项目完成 = 以下条件全部满足：

1. **P0 全部关闭**（KPI-P0a, P0b, P0c 全部达标）
2. **P1 全部关闭**（KPI-P1a, P1b, P1c, P1d 全部达标）
3. **P2 全部关闭**（KPI-P2a, P2b, P2c 全部达标）
4. **P3 全部关闭**（KPI-P3a, P3b, P3c 全部达标）
5. **P4 全部关闭**（KPI-P4a, P4b, P4c 全部达标）
6. **P5 基线达标**（KPI-P5a, P5b, P5c, P5d, P5e 全部达标）
7. **总体 KPI 表中的"目标值"列全部达标**

---

> **此方案的实现 = myteam 项目的完成。**
> 
> 每个功能点、每个业务流程都有可量化验证的 KPI。迭代时按 KPI 检视进度，KPI 全部达标 = 项目完成。
> 
> 框架能力（P0-P4）是"把已经建好的东西验证通"——不可跳过。
> 内容生态（P5）是"不断积累有价值的内容填充框架"——没有终点，但基线达标后可交付使用。