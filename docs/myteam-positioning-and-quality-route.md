# myteam 定位与质量边界路线（2026-07-03 讨论沉淀）

> 本文记录 2026-07-03 与用户讨论后确定的 myteam 定位澄清、病根诊断、与实现路线。
> 后续所有实现必须以本文为准，不得与本文矛盾。若方向调整，更新本文而非另起。
> 关联：`docs/quality-constraint-design.md`（约束 schema 与 Gate 扩展的实现细节）。

## 一、定位澄清（递进两部分，不可颠倒）

myteam 的最终目的分两部分，**递进依赖**：

1. **基础（第 1 部分）**：单个 agent 在边界内产出高质量成果物——可控、不越界。
2. **扩展（第 2 部分）**：每个 agent 都高质量了，往外搭工业级多 agent 协作框架，AI 团队自动化执行更复杂任务。

**第 2 部分依赖第 1 部分**。单 agent 不行，协作框架是空中楼阁。

用户原话：让 agent 在我要求框架内自由发挥创造力和能力，但不能越界（成果物要可控）。

## 二、病根诊断：为什么"越来越困难、效果没提升"

**真正的病根不是框架太重，是「不知道怎么判断成果物质量高低」**。

由此衍生的问题链：
- 不知道怎么定义质量 → 把"判断质量"的责任转嫁给 reviewer agent（多 agent 交叉评审）。
- reviewer 自己也没标准 → 3 轮 review 也收敛不稳 → 迭代慢。
- 单 agent 产出质量不可控 → 更依赖 review loop 兜底 → 第 1 部分调不好 → 继续依赖协作层。
- 精力花在加固第 2 部分（协作机制）补偿第 1 部分薄弱，而不是直接做扎实第 1 部分。

**现状的具体证据**（2026-07-03 实测）：
- `research` task_type 的边界（check_rules）只验「4 个章节标题存在 + min_length 500」。
- Gate 代码注释明确：`min_length → 防 stub，不当质量指标`；`must_include → 默认关`。
- `acceptance_criteria` 5 条只注入 prompt 给 agent 看，Gate 不强制验。
- → Gate 实际只验格式，不验内容质量。r1 review 抓的 5 个阻塞里 4 个是 Gate 本可机器判的结构性缺陷。

## 三、质量的两层划分（核心认知）

**必须分开，不能混**：

### A. 结构性质量 — 能机器判，Gate 必须验
- 对比矩阵存在（grep markdown 表格）
- 矩阵行列数 = 对比对象数 × 维度数
- 每个量化数据后内联来源编号（正则）
- Goal 要求的每个维度在正文都有段落
- 对比对象对称（矩阵每格非空）
- 信息来源每条含 URL + 采集时间 + 可信度

特征：可观测、可量化、不依赖主观判断、纯确定性代码（正则/解析/计数）。

### B. 内容性质量 — 机器判不了，靠判断
- 推断是否合理（要领域知识）
- 数据是否过时（除非硬编码时效阈值）
- 建议是否真可执行（能验结构，验不了对错）

**关键转变**：
- 质量的尺子从「reviewer agent 主观判断」变成「check_rules 确定性规则」。
- A 类由 Gate 拦，agent 产出违反即拦回重做，不进 review。
- B 类才用 review，且 review 只抓 B 类，不重复 A 类。
- → review 轮次从 3 降到 1，甚至很多 task 不需要 review。

## 四、约束绑定的设计（用户确认）

**Gate 的质量约束跟交付模板（delivery_template）绑定，不绑 task_type**：

- task_type（research）是抽象任务类型，可对应**多个交付模板**（research-report / research-brief / competitive-matrix...）。
- 每个具体任务只绑**一个**交付模板（competitive-research task 绑 research-report）。
- Gate 质量约束写在交付模板的 `check_rules` 里，针对该模板的内容结构。
- 换模板 = 换约束，一个 task_type 配多套模板互不干扰。

**模板的交付物不限于 markdown**：用户确认之后大概率使用 Word 文档（.docx）。
约束首先在 markdown 上验证闭环，再扩展 Word 支持（解析路线：python-docx 提取章节树+表格+正文，
走同一套约束检查函数）。

**为什么这样**（用户洞察）：约束和模板结构同源。research-report 模板定义了「4 章节 + 对比矩阵」，
约束就验「4 章节在 + 矩阵非空」；换 research-brief 模板（2 章节 + 指标表），约束自动跟着变。

**现状支持度**：`DeliveryTemplate` 类（`backend/common/delivery/delivery_templates.py`）已有 `check_rules` / `acceptance_criteria` / `task_types` / `default_for` 字段。数据结构已就绪，只是 `business/delivery_templates/research-report.yaml` 的 `check_rules` 内容太弱（只 4 章节名 + min_length）。

## 五、实现路线（不做的事 > 做的事）

### 做的
1. **把 A 类质量约束写进交付模板的 `check_rules`**（research-report 先行）。
2. **扩展 Gate `check_format`**：给 `check_rules` 加新 key（矩阵存在/来源内联/维度覆盖/对称性），加对应检查函数。
3. **单 agent 在边界内一次产出达标** → 不依赖 review loop 3 轮。

### 不做的（避免重蹈覆辙）
- 不重构内核（Process/AgentPort/Gate/Store/contracts/adapter 保持不动）。
- 不加新通用机制层（execution_harness 的 5 块通用注入默认关，见下）。
- 不靠加 review 轮次补质量。

## 六、已识别的"提前建的通用层"（待收窄，非本次实现）

这些是"为未来多方向通用"提前建的层，对当前未调好的方向是空转噪音：
- `execution_harness` 5 块通用注入（experience/lesson/l1/preference/kb）— 默认关，只留 umbrella_skill + rubric。
- `skill_review` 全量复盘 — review 类 task 已改跳过（2026-07-03），research 类仍跑待评估。
- 66 个 skill 里 57 个未被 task_type_skills 映射 — 死重，待删。

**待第 1 部分跑通后再决定哪些通用层值得开**。本次不动这些，专注第四节的约束绑定。

## 七、验证标准（怎么算第 1 部分做扎实）

竞品调研单 agent（competitive-research workflow，无 review loop）：
- 一次产出，Gate 拦住 r1 曾暴露的 4/5 个结构性缺陷（维度缺失/矩阵缺失/来源脱节/对称性）。
- 不依赖 review loop 即可达标。
- 单次跑 < 30 分钟。

达成即证明「单 agent 在边界内高质量」闭环成立，可往第 2 部分扩展。
