# gstack 质量保证机制分析

> 创建：2026-06-17  
> 分析范围：gstack 全部 50+ skills，重点剖析 ship/review/qa/autoplan/design-review/cso  
> 目的：理解 gstack 如何保证质量，对比 myteam 的质量保障体系

---

## 核心发现

gstack 的质量保证不是靠单一机制，而是 **四层防御体系**：

| 层级 | 机制 | 触发方式 | 作用 |
|------|------|---------|------|
| **L0: Skill 内嵌 gate** | 每个 skill 的步骤链中嵌入 STOP 检查点 | 人触发 `/command` | 每步完成前必须通过验证 |
| **L1: Hook 防护** | PreToolUse 拦截危险操作 | 自动 | 防止 rm -rf、DROP TABLE、force-push |
| **L2: 外部 review pipeline** | `/autoplan` 串联 4 个专业 review | 人触发 | 多维度质量审计 |
| **L3: 元技能（Meta-skill）** | ETHOS 哲学 + Confusion Protocol | 贯穿始终 | 决策纪律 |

---

## L0: Skill 内嵌 Gate 机制

### 典型模式：`/ship` 的 21 步工作流

`/ship` 是最能体现 gstack 质量设计的 skill。它有 **21 个有序步骤**，每个步骤都有明确的 gate：

```
Step 0: 检测分支状态（FRESH / ALREADY_BUMPED / DRIFT_STALE_PKG / DRIFT_UNEXPECTED）
  └─ STOP：DRIFT_UNEXPECTED 直接终止，不允许静默修复

Step 1-4: Version bump（分类 → 决策 → 队列感知 → 写入）
  └─ bun CLI 验证 4 位版本号格式

Step 5: 记录决策（gstack-decision-log）
  └─ 持久化到 learnings，下次 session 不重新推导

Step 6-7: Diff 分析 + 测试运行
  └─ 覆盖率必须生成且通过

Step 8: CHANGELOG 生成（读取 sections/changelog.md 作为 source of truth）
  └─ STOP：禁止从记忆编写，必须读取文件

Step 9-13: TODOS 同步 + Commit 整理 + PR 创建
  └─ 原子化 bisectable commit

Step 14-15: 推送前再验证（fresh test evidence）
  └─ 如果代码在步骤间被修改，必须重新测试

Step 16-20: PR 创建 + 度量持久化 + Plan-tune 发现
```

### 内嵌 gate 的关键模式

| 模式 | 说明 | 示例 |
|------|------|------|
| **STOP 指令** | 遇到特定条件必须暂停，等待用户决策 | ship: "DRIFT_UNEXPECTED → STOP" |
| **Source of Truth 引用** | 禁止从记忆执行，必须读取文件 | ship Step 13: "Read sections/changelog.md" |
| **Fresh Evidence 要求** | 不能复用旧结果 | ship Step 16: "Stale output is NOT acceptable" |
| **分类优先** | 先诊断状态再决定动作 | ship Step 0: classify → dispatch |
| **原子提交** | 每步独立 commit，可 bisect | ship Step 15 |
| **度量持久化** | 完成后记录指标供后续使用 | ship Step 20 |

### `/review` 的质量机制

`/review` 分析 diff 针对：
1. **SQL 安全性** — DROP TABLE、未参数化查询
2. **LLM trust boundary violations** — 不受信任输入进入 prompt
3. **Conditional side effects** — 条件分支中的副作用
4. **结构性问题** — 架构层面的风险

### `/qa` 的质量机制

三层递进：
| 层级 | 范围 | 产出 |
|------|------|------|
| Quick | 仅 critical/high 问题 | 快速反馈 |
| Standard | + medium | 完整报告 |
| Exhaustive | + cosmetic | 全量审计 |

流程：测试 → 发现 bug → 修复 → commit → 重新验证（before/after screenshots）

### `/design-review` 的质量机制

迭代修复模式：
1. 找问题（视觉不一致、间距、层次、AI slop 模式）
2. 修复源码
3. 原子 commit
4. 重新验证（before/after screenshots）
5. 循环直到无问题

---

## L1: Hook 防护体系

gstack 有独立的 hook-based 安全技能：

| 技能 | 机制 | 保护范围 |
|------|------|---------|
| `/careful` | PreToolUse hook on Bash | 拦截 rm -rf, DROP TABLE, force-push, kubectl delete 等 |
| `/freeze` | PreToolUse hook on Edit/Write | 限制编辑目录范围 |
| `/guard` | careful + freeze 组合 | 最大安全模式 |

**与 myteam 的对比**：
- gstack 的 hook 是 **Claude Code 的 permissions system**（`permissionDecision: "ask"`）
- myteam 的 gate 是 **YAML 声明式规则**（delivery_template + section-review）
- gstack 是 **运行时拦截**，myteam 是 **DAG 节点门控**

---

## L2: 外部 Review Pipeline — `/autoplan`

`/autoplan` 是 gstack 的最高级质量门，串联 4 个独立 review：

```
/autoplan
  ├── /plan-ceo-review    → CEO/战略审查（10-star product, scope expansion）
  ├── /design-review      → 视觉/UX 审查
  ├── /plan-eng-review    → 工程架构审查
  └── /devex-review       → 开发者体验审查（实测 onboarding flow）
```

每个 review 是 **独立 agent + 独立方法论**，最后汇总到一个审批 gate。

**关键设计**：
- 4 个 review **并行发现、串行决策**
- 每个 review 有自己的 confidence score
- 最终需要用户审批（human-in-the-loop）
- 支持 auto-decide（基于历史偏好）

---

## L3: Meta-skill 体系

### ETHOS 哲学

```
Boil the Ocean      → 完整性原则：推荐全量覆盖
Search Before Build → 搜索优先：先查现有代码再写
User Sovereignty    → 用户主权：cross-model agreement ≠ decision
```

### Confusion Protocol

> 对于高风险歧义（架构、数据模型、破坏性范围、缺失上下文），**STOP**。  
> 一句话命名问题，呈现 2-3 个选项及其 tradeoffs，然后询问。  
> 不适用于常规编码或明显变更。

### Completeness Scoring

每个 AskUserQuestion 中嵌入 `Completeness: X/10`：
- 10 = 所有 edge cases
- 7 = 仅 happy path
- 3 = 捷径

### Learning 持久化

```bash
# 决策日志
gstack-decision-log '{"decision":"...","rationale":"...","scope":"repo"}'

# 学习检索
gstack-learnings-search --limit 3

# 偏好调优
gstack-question-preference --check "<id>"
```

---

## gstack vs myteam 质量保障对比

| 维度 | gstack | myteam |
|------|--------|--------|
| **触发方式** | 人触发 `/command` | 内核调度 DAG |
| **Gate 机制** | 步骤链中的 STOP 指令 | YAML transition + deliverable_marker |
| **评审方式** | 独立 review skill 串联 | section-review task_type |
| **安全防护** | PreToolUse hook（运行时） | delivery_template（声明式） |
| **上下文持久化** | learnings.jsonl + decision-log | SQLite state machine |
| **完整性检查** | Completeness scoring + probe | quality-review methodology |
| **重试粒度** | 单 skill 内循环 | 单 step gate retry |
| **多视角评审** | autoplan 串联 4 review | assess + transition |
| **证据要求** | before/after screenshots | REVIEW: PASS/FAIL marker |

---

## gstack 质量体系的弱点

### 1. 依赖人的纪律

gstack 的 STOP 指令完全依赖 agent 自觉执行。没有运行时强制——如果 agent 忽略 STOP，没有任何机制阻止它继续。

> myteam 的优势：YAML transition 是**内核强制执行**的，不是 skill 建议。

### 2. 无并发安全

gstack 是单线程 CLI 工具，没有并发保护。两个 `/ship` 同时运行可能导致版本冲突。

> myteam 的优势：SQLite state machine + 分布式锁。

### 3. Review 串联成本高

`/autoplan` 需要 4 次完整的 skill 执行，每次都要加载 preamble + artifacts sync，token 开销巨大。

> myteam 的优势：assess 步骤只做必要的评审。

### 4. 无自动化回归测试

gstack 的 `/qa` 是手动触发的，没有 CI/CD 集成。每次 ship 前需要人主动调用。

> myteam 的优势：transition 规则自动触发评审。

### 5. 证据链断裂风险

gstack 依赖 screenshots 和手动验证，没有结构化的证据存储。

> myteam 的优势：deliverables 目录 + SQLite 状态持久化。

---

## 对 myteam 的启示

1. **STOP 指令需要内核级强制** — 不能只靠 skill 文本建议
2. **Completeness Scoring 可以借鉴** — 在 workflow YAML 中嵌入质量评分要求
3. **Confusion Protocol 是好的决策纪律** — 可以写进 coordination-methodology
4. **Hook 防护不适合 myteam** — myteam 的质量保障应该在 DAG 层面，不是运行时拦截
5. **autoplan 模式有价值** — myteam 的 multi-workflow composition 可以实现类似功能
