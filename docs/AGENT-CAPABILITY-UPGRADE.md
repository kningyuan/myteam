# Agent 执行能力提升方案

> 基于 2026-06-27 对 Skill 系统、知识库、偏好库的深度调研，识别出 5 个能力短板和 3 个可引入的第三方 Skill 包。

---

## 一、核心发现：三个被静默禁用的能力注入

调研发现，系统当前的 execute harness 注入链有 **3 个关键环节处于失效状态**，直接导致 Agent 执行任务时"看不到"本该辅助它的知识、偏好和经验。

### 1.1 KB top-K 知识注入被禁用（严重）

| 项 | 详情 |
|----|------|
| **现象** | `fetch_kb_entries()` 始终返回空列表，Agent 看不到【相关知识】块 |
| **根因** | `kb_inject_allowed()` 要求 `memstack.enabled=true` **且** `execution_harness.kb_enabled=true`，但当前 `memstack.enabled=false` |
| **影响** | 知识库 208 条记录中，仅经验(1条)和教训(12条)能注入；KB top-K（按 task_type 召回的 3 条相关知识）完全失效 |
| **配置位置** | `config/skill_config.json` → `memstack.enabled` |
| **修复** | 将 `memstack.enabled` 设为 `true` |

**注入链路对比（修复前 vs 修复后）**：

| 注入块 | 数据源 | 当前状态 | 修复后 |
|--------|--------|----------|--------|
| 【同类任务经验】 | KB search tags=[task_type,"ledger"] | 生效（1 条） | 生效 |
| 【同类任务教训】 | store.memory_search tags=["lesson"] | 生效（12 条） | 生效 |
| 【本任务推荐方法论 Skill】 | task_type_skills.yaml | 生效 | 生效 |
| 【同类任务参考】 | skill/references/*.md | 生效 | 生效 |
| 【工作记忆 L1】 | SqliteAgentMemory | 生效（2 条） | 生效 |
| 【用户偏好】 | config/USER.md | 生效（但内容为"- foo"） | 生效（需填充内容） |
| **【相关知识 KB top-K】** | **kb.search(tags=[task_type])** | **禁用** | **生效（3 条/task_type）** |
| 【质量评分标准】 | 硬编码 | 生效 | 生效 |

### 1.2 偏好库 USER.md 形同空置（严重）

| 项 | 详情 |
|----|------|
| **当前内容** | `# Rules\n- foo` |
| **分节机制** | 已就绪（style/avoid/principles/tools），但未填内容 |
| **注入方式** | execute 时注入【用户偏好】块；有界同步到 workspace/USER.md |
| **影响** | Agent 不知道团队的交付标准、风格禁忌、决策原则 |
| **修复** | 填充 config/USER.md 实质内容 |

### 1.3 L1 工作记忆几乎为空（中等）

| 项 | 详情 |
|----|------|
| **当前数据量** | 2 条（`__memstack_l1__` project_id） |
| **根因** | L1 在每轮对话后自动写入，但系统执行的任务量少 |
| **影响** | Agent 跨轮次的上下文记忆不足 |
| **修复** | 正常使用会自动积累；短期可手动写入种子数据 |

---

## 二、Skill 系统覆盖度分析

### 2.1 当前 Skill 清单

| 类型 | 数量 | 说明 |
|------|------|------|
| 自研生产 Skill | 14 | 方法论 + 工具类 |
| Vendor 软链 Skill | 12 | OfficeCLI 套件(11) + browse(1) |
| auto-* 草案 | 7 | 自动抽提 scaffold（不可挂载） |
| _pending 补丁 | 47 | skill_review 产生的增量 patch，待审批 |

### 2.2 task_type × Skill 覆盖矩阵

| task_type | 专属 Skill | 覆盖状态 | 缺口 |
|-----------|-----------|----------|------|
| research | product-methodology | ✅ 有 | - |
| product-research | product-methodology | ✅ 有 | - |
| product-planning | product-methodology | ✅ 有 | - |
| competitive-analysis | product-methodology | ✅ 有 | - |
| business-diagnosis | product-methodology | ✅ 有 | - |
| acceptance-report | product-methodology | ✅ 有 | - |
| decision-record | product-methodology | ✅ 有 | - |
| coding | backend/frontend-engineering-methodology | ✅ 有 | - |
| review | quality-review | ✅ 有 | - |
| code-deliverable | backend-engineering-methodology | ✅ 有 | - |
| code-deployment | backend-engineering-methodology | ✅ 有 | - |
| **publish-post** | 无平台专属 | **⚠️ 弱** | 缺少各平台发布规范 |
| **data-analysis** | 无专属 | **⚠️ 弱** | 缺少数据分析方法论 |
| **custom-survey** | 无 | **❌ 无** | 仅推荐 product-methodology |
| **my-type** | 无 | **❌ 无** | 疑似测试模板 |

### 2.3 其他 Skill 问题

- **prompt-optimizer 路由悬空**：catalog.yaml 有条目但磁盘上无对应目录
- **47 个 _pending 补丁未审批**：skill_review 产生的增量改进，因 `skills_write_approval=true` 暂存
- **Agent Skill 挂载不均**：research/ops/content/seo/test-harness-agent/tester 等角色在 registry 中 `skills=[]`，执行任务时无方法论指导

---

## 三、第三方 Skill 引入方案

### 3.1 推荐引入的 Skill 包

| Skill 包 | 来源 | 技能数 | 适用场景 | 引入价值 | 安装命令 |
|----------|------|--------|----------|----------|----------|
| **superpowers** | obra/superpowers | 14 | TDD/调试/代码审查/重构/文档 | 补强 developer/qa 的工程能力 | `npx skills add obra/superpowers` |
| **planning-with-files** | OthmanAdi/planning-with-files | 1 | 外部记忆/任务规划/进度追踪 | 补强 Agent 长任务规划能力 | `npx skills add OthmanAdi/planning-with-files` |
| **webapp-testing** | 社区 | 1 | Playwright Web 应用测试 | 补强 qa 的自动化测试能力 | `npx skills add browser-use/browser-use` |

### 3.2 superpowers 技能清单（14 个）

| 技能 | 用途 | 对应 myteam 角色 |
|------|------|-----------------|
| brainstorming | 头脑风暴，发散思维 | product / main |
| test-driven-development | TDD 测试驱动开发 | developer / qa |
| systematic-debugging | 系统化调试流程 | developer / qa |
| code-review | 代码审查 | qa / arch |
| refactoring | 重构建议 | developer / arch |
| documentation | 文档生成 | 所有角色 |
| planning | 项目规划 | main / product |
| ... | ... | ... |

### 3.3 引入方式

myteam 已有 `skill_install.py` 支持 URL 安装，且 `skill_link.py` 支持 vendor 软链：

```python
# 方式一：通过 myteam 的 skill_install API
POST /api/skills/install
{"source": "obra/superpowers", "type": "github"}

# 方式二：手动创建软链（与 officecli/browse 同模式）
# business/skills/superpowers → ~/.claude/skills/obra/superpowers
```

引入后在 `agents_registry.json` 中为对应 Agent 挂载：
```json
{
  "developer": {
    "skills": ["backend-engineering-methodology", "superpowers"]
  },
  "qa": {
    "skills": ["qa-methodology", "superpowers", "webapp-testing"]
  }
}
```

---

## 四、具体提升方案（按优先级排序）

### P0：立即修复（配置层面，0 代码改动）

#### 4.1 启用 KB top-K 注入

```json
// config/skill_config.json
{
  "memstack": {
    "enabled": true,  // false → true
    "kb_backend": "sqlite",
    "l1_backend": "sqlite",
    "preferences_backend": "static",
    "inject_top_k": 3
  }
}
```

**预期效果**：每次 execute 时，Agent 额外获得 3 条按 task_type 召回的相关知识（来自 208 条 KB 记录）。

#### 4.2 填充偏好库 USER.md

```markdown
# 团队交付规则

## style（风格偏好）
- 交付物用中文撰写，技术术语保留英文原文
- Markdown 格式，章节标题用 ## 二级标题
- 代码块标注语言类型（python/bash/json/yaml）
- 数据和结论必须标注来源

## avoid（禁忌）
- 禁止使用"有潜力""建议完善"等空话替代可验证结论
- 禁止编造数据或路径
- 禁止忽略 intent 中的硬性要求（数量、格式、范围）
- 禁止交付 stub（"待补充""TODO""占位"）

## principles（决策原则）
- 先扫描清单再动手，不即兴发挥
- 结论必须 Pass/Fail，不给模糊评价
- 每个发现须有可复现命令或代码路径佐证
- Out of Scope 须明确列出，不少于 3 条

## tools（工具与库）
- 调研类任务：优先用 WebSearch + WebFetch
- 代码类任务：遵循 backend/frontend-engineering-methodology
- 文档类任务：遵循 product-methodology 的交付模板
- 测试类任务：用 Playwright + pytest
```

**预期效果**：Agent execute 时获得明确的交付标准约束，减少 stub 和空话。

### P1：短期补充（1-2 天）

#### 4.3 补充缺失 Skill

**data-analysis 方法论 Skill**：

创建 `business/skills/data-analysis-methodology/SKILL.md`：
- 数据采集 → 清洗 → 分析 → 可视化 → 结论 的标准流程
- 必选章节：数据来源/清洗规则/分析方法/关键指标/可视化图表/结论与建议
- 工具推荐：pandas / matplotlib / seaborn
- Gate 规则：须含可复现的分析脚本路径

**publish-post 平台规范 Skill**：

创建 `business/skills/publish-post-methodology/SKILL.md`：
- 各平台发布规范（知乎/小红书/微信公众号）
- 证据要求：已发布 URL + 截图
- 内容结构：标题/正文/标签/封面图
- Gate 规则：check_action_evidence（URL host 校验 + 标题验证）

#### 4.4 审批 _pending 补丁

47 个 _pending 补丁中筛选有价值的改进：

```bash
# 批量查看 pending 补丁
ls business/skills/_pending/

# 检查每个补丁的 meta.json
for d in business/skills/_pending/*/; do
  echo "=== $(basename $d) ==="
  cat "$d/meta.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d.get(\"skill_id\",\"?\")} | {d.get(\"action\",\"?\")} | {d.get(\"notes\",\"?\")}')"
done
```

审批流程：有价值的 patch 合并到对应 SKILL.md，无价值的删除。

#### 4.5 修复悬空路由

```bash
# 方式一：创建 prompt-optimizer skill 目录
mkdir -p business/skills/prompt_optimizer
# 编写 SKILL.md（prompt 优化方法论）

# 方式二：从 catalog.yaml 移除悬空条目
# 编辑 business/skills/catalog.yaml，删除 prompt-optimizer 条目
```

### P2：中期增强（3-5 天）

#### 4.6 引入第三方 Skill 包

```bash
# 安装 superpowers（14 个工程技能）
npx skills add obra/superpowers -y

# 安装 planning-with-files（外部记忆）
npx skills add OthmanAdi/planning-with-files -y

# 安装 webapp-testing（Playwright 测试）
npx skills add browser-use/browser-use -y
```

安装后在 `agents_registry.json` 中为对应 Agent 挂载。

#### 4.7 为无 Skill 的 Agent 补充方法论

| Agent | 当前 skills | 建议补充 |
|-------|------------|----------|
| research | [] | research-methodology（新建） |
| ops | [] | ops-methodology（新建：部署/监控/告警） |
| content | [] | content-methodology（新建：SEO/排版/配图） |
| seo | [] | seo-methodology（新建：关键词/外链/排名） |

#### 4.8 对齐 Agent 配置一致性

`agents_registry.json` 的 `task_types` 与 workspace `AGENTS.md` 的 task_type 列表不一致：

| Agent | registry task_types | AGENTS.md task_types | 差异 |
|-------|--------------------|-----------------------|------|
| developer | ["coding"] | 7 个（含 code-review/system-design 等） | registry 过窄 |
| research | ["research"] | 3 个（含 architecture-review/diagram-build） | registry 过窄 |

修复：以 AGENTS.md 为准，更新 registry 的 task_types。

### P3：长期建设（持续）

#### 4.9 知识库种子数据注入

当前知识库 208 条，但分布不均：
- quality(53) / report(56) / rubric(28) / baseline(28) / case(28) / optimal_skills(28) / lesson(12)
- 按 task_type 分布不均，部分 task_type 无知识积累

建议：
- 每完成一个项目，确保 ledger 蒸馏入 KB
- 定期审查 KB 条目质量，清理低价值记录
- 为新 task_type 主动写入种子知识（基线/案例）

#### 4.10 Skill 自动抽提优化

当前 auto-* 草案质量低（多为测试产物）。优化方向：
- 提高 `skill_extract_enabled` 的触发门槛（仅成功且高质量的任务）
- 增加抽提后的质量检查（stub 检测、最小字数）
- 审批流程：auto-* → 人工审查 → 升级为正式 Skill

#### 4.11 偏好库分节化

将 USER.md 从扁平格式升级为分节格式，利用已就绪的 `preference_sections.yaml`：

```yaml
# business/config/preference_sections.yaml（已存在）
sections:
  - id: style
    description: 风格偏好
  - id: avoid
    description: 禁忌
  - id: principles
    description: 决策原则
  - id: tools
    description: 工具与库
```

---

## 五、预期效果量化

| 提升项 | 当前状态 | 修复后状态 | 预期效果 |
|--------|----------|-----------|----------|
| KB 知识注入 | 0 条/task_type | 3 条/task_type | Agent 获得同类任务历史经验 |
| 偏好库约束 | "- foo" | 4 节 16+ 条规则 | Agent 遵循团队交付标准 |
| Skill 覆盖度 | 11/15 (73%) | 15/15 (100%) | 所有 task_type 有方法论指导 |
| Agent Skill 挂载 | 6/13 角色有 Skill | 13/13 角色有 Skill | 所有角色有方法论支撑 |
| 第三方 Skill | 0 个 | 3 个包(16+ 技能) | 工程能力显著增强 |
| _pending 补丁 | 47 个待审批 | 0 个（审批完） | Skill 持续改进闭环 |
| 知识库数据量 | 208 条 | 持续增长 | 知识复利效应 |

---

## 六、实施检查清单

- [ ] P0-1：将 `memstack.enabled` 设为 `true`
- [ ] P0-2：填充 `config/USER.md` 实质内容
- [ ] P1-1：创建 data-analysis-methodology Skill
- [ ] P1-2：创建 publish-post-methodology Skill
- [ ] P1-3：审批 47 个 _pending 补丁
- [ ] P1-4：修复 prompt-optimizer 悬空路由
- [ ] P2-1：安装 superpowers Skill 包
- [ ] P2-2：安装 planning-with-files Skill 包
- [ ] P2-3：安装 webapp-testing Skill 包
- [ ] P2-4：为 research/ops/content/seo 补充方法论 Skill
- [ ] P2-5：对齐 registry 与 AGENTS.md 的 task_types
- [ ] P3-1：知识库种子数据注入
- [ ] P3-2：Skill 自动抽提质量优化
- [ ] P3-3：偏好库分节化升级

---

## 附录：关键文件索引

| 文件 | 作用 |
|------|------|
| `config/skill_config.json` | memstack / execution_harness 配置开关 |
| `config/USER.md` | 团队偏好库（唯一真相源） |
| `business/skills/catalog.yaml` | Skill 路由表（task_type → SKILL.md） |
| `business/skills/categories.yaml` | Skill 展示分类 |
| `business/config/agents_registry.json` | Agent 角色注册（skills/task_types） |
| `business/templates/templates.yaml` | task_type 定义 + Gate 规则 |
| `backend/execution_harness/pre/inject.py` | execute harness 注入入口 |
| `backend/execution_harness/config.py` | `kb_inject_allowed()` 闸门 |
| `backend/memstack/facade.py` | 统一记忆栈 Facade（H1-H5） |
| `backend/common/agent_skills.py` | Skill 上下文注入（build_skill_context） |
| `backend/common/agent_transport.py` | Worker prompt 构建（execute 分支） |
