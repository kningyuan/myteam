# 质量约束设计：交付模板绑定 + Gate 机器判

> 本文是 `docs/myteam-positioning-and-quality-route.md` 第四节的实现细节。
> 设计原则：约束跟交付模板绑定（不绑 task_type）；A 类结构性质量机器判，B 类内容性质量才用 review。
> 实现前必读 positioning 文档，不得与其矛盾。

## 一、现状基线（实现前的事实）

### 交付模板存储
- 目录：`business/delivery_templates/*.yaml`
- 加载：`backend/common/delivery/delivery_templates.py` 的 `load_delivery_template(template_id)`
- `DeliveryTemplate` dataclass 已有字段：`deliverable_template` / `check_rules` / `acceptance_criteria` / `task_types` / `default_for`

### research-report.yaml 现状（约束太弱）
```yaml
check_rules:
  required_sections: [调研背景, 信息来源, 关键发现, 结论]
  min_length: 200
```
只验章节标题存在 + 防 stub。不验内容质量。

### Gate 现状
- `backend/common/gate/gate.py` 的 `check_format(spec, content, ...)` 读 `FormatSpec` 验：
  - `required_sections`（章节存在）
  - `required_heading_level`
  - `file_exists`
  - `is_stub`（防 stub，非质量指标）
  - `must_include`（默认关，`enforce_must_include=False`）
- `FormatSpec` 由 `backend/common/gate/registry.py` 的 `_spec_from_delivery_template` / `_build_spec` 构造。
- **task 带了 `template_id` 时走 `_spec_from_delivery_template`**（line 59），从交付模板取 `check_rules`。→ 路径已通，约束写模板就会被 Gate 读到。

## 二、约束 schema 设计（check_rules 扩展）

> 约束规则来源：行业实战（woshipm.com 合同管理竞品分析报告 6194687 + 产品体验报告 213563）
> + 内部 r1 实测阻塞分析（pm-research-base/fast 两个项目共 8 条 🔴 阻塞）。
> 每次新增约束，在这里注明来源。

在 `check_rules` dict 加新 key，每个 key 对应一个机器可判检查。**不破坏现有 key**（required_sections/min_length/must_include/file_exists 保留）。

### 新增 key 规范

每条约束标注来源：**[S]** = 行业实战（woshipm 6194687）**[R]** = 内部实测 r1 阻塞 **[C]** = 行业常识

| key | 值类型 | 判定逻辑 | 拦的缺陷 | 来源 |
|-----|--------|----------|----------|------|
| `require_comparison_matrix` | `bool` | 指定章节（默认「关键发现」）内含 markdown 表格（`\|.*\|.*\|` 且 ≥2 行） | 缺结构化对比 | [R][S] |
| `matrix_min_rows` | `int` | 表格数据行数 ≥ N（对比对象数+1） | 对比对象不全 | [S] |
| `matrix_min_cols` | `int` | 表格列数 ≥ N（对比维度数+1） | 维度覆盖不全 | [S] |
| `matrix_no_empty_cell` | `bool` | 对比矩阵每个格子非空（不允许「」/空白/仅标点） | 对比不对称/数据缺口 | [R][S] |
| `matrix_source_in_cell` | `bool` | 矩阵每格含来源编号 `[S\d]` 或来源标记 | 矩阵数据无来源 | [S] |
| `dimension_coverage` | `list[str]` | 每个维度词在正文（指定章节或全文）出现且所在段 ≥2 句 | 维度缺失 | [R] |
| `source_inline_required` | `bool` | 每个量化数字（正则 `\d+`）后跟 `[S\d]`/`[来源]`/`(http...)` | 来源与正文脱节 | [R][S] |
| `source_table_fields` | `list[str]` | 「信息来源」表每行含指定字段（URL/采集时间/可信度） | 来源信息不全 | [S][C] |
| `source_table_min_rows` | `int` | 来源表行数 ≥ N | 来源数量不足 | [C] |
| `no_unsourced_in_findings` | `bool` | 「关键发现」章节内若含「推断/推测/可能」类词，后须跟「无公开来源」标注；不加则报警 | 推断混入事实 | [R] |
| `data_gap_labeled` | `bool` | 信息缺口/数据缺失章节存在且非空 | 数据缺口不透明 | [S][C] |
| `swot_required` | `bool` | 结论前含 SWOT 或类似综合分析（矩阵/对比总结表） | 缺综合判断 | [S] |
| `executable_p0_required` | `bool` | P0/P1 建议含行动要素（责任方/时间窗口/交付物） | 建议不可执行 | [R] |
| `anomaly_coverage` | `bool` | 结论中含异常场景/风险章节（数据缺失/时效性/口径不统一/监管风险） | 缺异常场景 | [R] |
| `format_mermaid_only` | `bool` | 流程图/架构图用 mermaid DSL，不用纯文字/ASCII描述 | 图不规范 | [C] |

### 约束与现有模板章节的对应

research-report.yaml 的 4 章节（调研背景/信息来源/关键发现/结论），每条约束对应的章节：

| 约束 | 主要检查章节 | 补充检查范围 |
|------|-------------|-------------|
| `require_comparison_matrix` | 关键发现 | 全文 |
| `matrix_min_rows/cols/no_empty_cell` | 关键发现 | — |
| `dimension_coverage` | 关键发现 | 全文 |
| `source_inline_required` | 关键发现 + 结论 | 全文量化数字 |
| `source_table_fields` | 信息来源 | — |
| `no_unsourced_in_findings` | 关键发现 | — |
| `data_gap_labeled` | 结论（信息缺口子章节）或独立章节 | — |
| `executable_p0_required` | 结论 | — |
| `anomaly_coverage` | 结论 | — |

### Web 来源与实测支撑

- **[S] woshipm.com 合同管理系统竞品分析报告（6194687）**：9 章节框架、11 个对比矩阵、多维对比体系（功能/技术/市场/商业/客户）、数据来源标注规范（缺失标注"待补充"、推算标"预估"）、完整性约束（定价三要素/盈利三要素）
- **[S] woshipm.com 产品体验报告（213563）**：5 章节框架（背景→概况→市场→功能→总结）、核心指标来源、流程分析必备结构
- **[R] pm-research-base / pm-research-fast 实测**：共 8 条 r1 🔴 阻塞，涵盖维度缺失/矩阵缺失/来源脱节/推断混事实/不对称/建议不可执行

### 约束写在哪（模板 vs task_type）
- **通用约束**（对所有调研成立：矩阵存在、来源内联）→ 写交付模板 `check_rules`。
- **Goal 相关约束**（3 平台 × 4 维度）→ **不硬编码数字**。Gate 解析实际矩阵行列 + Goal 文本动态算对称性，而非写死「必须 3 行 4 列」。这样换 Goal 不用改模板。
  - 若 Goal 解析不可靠，退而用 `matrix_min_rows` / `matrix_min_cols` 配最小值（软约束）。

## 三、Gate 扩展实现点

### 1. registry.py：FormatSpec 加字段
`FormatSpec`（`backend/common/gate/registry.py`）加对应字段，`_spec_from_delivery_template` 从模板 `check_rules` 读取填充。

### 2. gate.py：check_format 加检查函数
每个新 key 一个检查函数，返回 `GateResult` 的 failure 项。检查函数纯确定性（正则/markdown 解析/计数），不调 LLM。

markdown 表格解析：用正则切 `|` 分隔行，或引入轻量解析（不依赖外部库，手写 split）。

### 3. 约束违反的处理
- Gate 拦住 → task 置 `gate_failed`，走现有重试路径（`max_gate_retries`）。
- 重试时 prompt 注入「Gate 失败原因 + 该修哪条」（现有机制，不新增）。
- 不引入 review 补救 A 类——A 类由 Gate 兜底，review 只管 B 类。

## 四、最小可工作例子（先验证可行性）

**目标**：挑 4 个约束（覆盖 r1 全部 5 个阻塞），在 research-report.yaml 实现 + Gate 加检查函数，跑一次单 agent 竞品调研（competitive-research workflow，无 loop），看 Gate 能否拦住 r1 曾暴露的缺陷。

### 选这 4 个约束（覆盖 r1 全部 5 个 🔴）

| 约束 | 拦的 r1 阻塞 | 来源 |
|------|-------------|------|
| `require_comparison_matrix: true` | arch-P0-2 缺矩阵 | [R] |
| `dimension_coverage: [核心功能,用户画像,变现模式,用户评价]` | product-P1 核心功能缺失 + P3 评价缺失 | [R] |
| `source_inline_required: true` | product-P3 来源脱节 | [R] |
| `no_unsourced_in_findings: true` | product-P2 推断混入 + arch-P0-1 画像论据不足 | [R] |

### 验证标准
- agent 产出缺矩阵时 Gate 拦住并说「未找到对比矩阵表格」
- agent 产出缺维度时 Gate 说「维度 X 无实质内容」
- agent 产出量化数字无来源内联时 Gate 说「量化数据缺少来源编号」
- agent 在关键发现中写推断性描述时 Gate 说「推断性数据不得在关键发现」
- 拦住后重试，agent 补齐则放行。
- 全程不依赖 review loop。

### 实现顺序
1. `research-report.yaml` 加 4 个 check_rules key。
2. `registry.py` 的 `FormatSpec` + `_spec_from_delivery_template` 支持新 key。
3. `gate.py` 的 `check_format` 加 4 个检查函数。
4. 单测：构造缺矩阵/缺维度/无来源/推断入发现 4 个样本，断言 Gate 拦住。
5. 端到端：跑 competitive-research workflow，看 Gate 实际拦截。

## 五、与现有机制的关系（不矛盾确认）

- **SKILL.md**：教 agent 怎么做（软引导，方法论）。保留 `research_methodology` 的自检章节（1-7 条已验证）。
- **check_rules / Gate**：验产出是否达标（硬边界，机器判）。本次扩展。
- **acceptance_criteria**：注入 prompt 给 agent 看目标（软引导），Gate 不强制验（维持现状，除非后续要加严格模式）。
- **review loop**：降级为只抓 B 类内容性质量，不重复 A 类。轮次预期 3→1。
- **execution_harness 注入**：umbrella_skill + rubric 保留，其余 5 块默认关（positioning 文档第六节，本次不动）。

分工：SKILL.md（怎么做）+ acceptance_criteria（目标）= 软引导；check_rules + Gate（达标否）= 硬边界；review（B 类补充）= 兜底。三者不重叠。

## 六、待定问题（实现中再决）

1. `dimension_coverage` 的维度词从哪来：硬编码在模板 / 从 Goal 解析 / 从 task description？倾向模板配（research-report 固定四维度），但若要支持任意调研对象需参数化。
2. 矩阵解析的鲁棒性：agent 可能用 mermaid 表格 / HTML 表格 / 非标 markdown。先支持标准 markdown 表格，其他形态报「未识别矩阵」让 agent 改。
3. 约束违反的重试上限：`max_gate_retries` 现有配置够否，A 类约束严了可能触发更多重试。

## 七、通用约束全集 vs 业务特定约束（两层设计）

> 用户诉求：一套通用的质量检测全集，不论哪种任务的任何模板都能覆盖。
> 诚实边界：结构性质量能通用化（全集），内容性质量不可能有全集（业务特定 + review）。

### 第一层：通用结构性约束全集（Gate 提供，任何模板可配）

与具体业务无关的"结构/存在/对称"规则。任何任务类型的模板都能从这全集里勾选。

**组 A 存在性（全通用）**
- `required_sections` — 必备章节标题存在
- `min_length` — 防 stub（非占位空文）
- `file_exists` — 引用文件存在
- `must_include` — 必含关键词（默认关）

**组 B 对比矩阵（对比类模板专用）**
- `require_comparison_matrix` — 指定章节含 markdown 表格
- `matrix_min_rows` / `matrix_min_cols` — 矩阵行列数下限
- `matrix_no_empty_cell` — 矩阵每格非空（不对称检测）
- `matrix_section` — 矩阵所在章节名

**组 C 数据可信（带数据的模板专用）**
- `source_inline_required` — 量化数字后内联来源编号
- `no_unsourced_in_findings` — 关键发现内推断须标注

**组 D 维度覆盖（指定了对比维度的模板专用）**
- `dimension_coverage` — 指定维度词全覆盖且非罗列

### 第二层：业务特定约束（按 task_type 扩展，不进通用全集）

跟业务强相关、不可通用化的检查。例：
- code-deliverable：代码能跑、测试覆盖
- requirements：用户故事符合 INVEST
- PRD：验收标准可测

这些不进通用全集，跟 task_type 走，未来按需扩展。

### 覆盖度评估（第一层全集对不同任务的适用性）

| 任务类型 | 通用约束适用度 | 说明 |
|---------|---------------|------|
| 竞品调研 | 高（11/11） | 矩阵+维度+来源+推断全用得上 |
| PRD | 中（6/11） | 章节+来源+stub，矩阵/维度看场景 |
| 需求分析 | 中（6/11） | 章节+stub+必含关键词 |
| 代码交付 | 低（4/11） | 章节+file_exists+stub |
| 评审报告 | 低（4/11） | 章节+stub |

**结论**：通用全集覆盖任何模板的"结构性质量"（全覆盖），"内容质量"由 review 兜底（不可能有全集）。

## 八、Gate 注册表化 + UI 全集渲染（实现方向）

### Gate 注册表化
- 检查函数从写死在 `check_format` 改为注册表：`{key: (检查函数, 元信息)}`。
- `check_format` 遍历 spec 里配的 key，调对应注册函数。
- 新增约束 = 注册一个函数，不改 `check_format` 主流程。

### UI 全集渲染
- `CheckRulesEditor` 不再写死 9 个 bool 列表。
- 从 Gate 注册表（或前端镜像的约束目录）读全集，按组渲染（A/B/C/D）。
- 每个约束显示：名称 + 说明 + 类型（bool/int/str/list）+ 是否启用。
- 用户勾选/填值配置，所见即所验。

### 假约束清理
- 5 个未实现的（data_gap_labeled/swot_required/executable_p0_required/anomaly_coverage/format_mermaid_only）：
  从 UI 删除（不进注册表），或补实现后加入。
- 原则：UI 能配的 = Gate 真验的。

## 九、多模板扩展（远期）

> 用户确认设计：task_type（竞品分析）可对应多个交付模板，不同竞品类型配不同模板。
> 例：竞品分析-面向资本市场（关注财务/估值/市占率）vs 竞品分析-面向功能设计（关注功能矩阵/交互/技术指标）。
> 每个模板有独立 check_rules，互不干扰。当前先生成一个模板（research-report）验证闭环。

### 多模板场景举例

| 模板 id | 适用场景 | 核心关注维度 | 特有约束 |
|---------|---------|-------------|---------|
| `research-report` | 通用竞品对调研 | 核心功能/用户画像/变现/评价 | dimension_coverage, matrix |
| `research-capital` | 面向资本市场 | 财务/估值/市占率/增速 | financial_metrics_required, growth_rates |
| `research-functional` | 面向功能设计 | 功能矩阵/交互/技术架构 | feature_matrix_full, tech_stack_detail |

### 模板发现与选择
- **发现**：`list_delivery_template_ids()` 按 `task_types: [research]` 过滤
- **选择**：用户在创建项目时选 "交付模板"（避开模版参数化，直接按模板名选）
- **没选时的回退**：`default_for: research` 的模板作为默认值（若配置）

## 十、Word 文档支持（远期）

> 用户明确：交付模板不限于 markdown，之后大概率使用 Word 文档（.docx）。
> Word 支持下放到独立阶段实现。当前最小可工作例子先用 markdown 验证约束规则本身。

### 约束与文档格式解耦
- **约束在 design 阶段定义**，与格式无关。同一条 `require_comparison_matrix` 对 markdown 和 docx 都适用。
- **Gate 先解析文档为统一结构**（章节树 + 矩阵集 + 正文），再跑约束检查。约束函数不直接感知 .md vs .docx。

### Word 解析路线（python-docx）
1. **章节识别**：遍历 heading 段落（`paragraph.style.name.startswith('Heading')`），提取章节树
2. **表格解析**：遍历 `doc.tables`，每张表转 markdown 兼容矩阵格式（rows × cells）
3. **内容提取**：章节正文按段落拼接为纯文本，走与 markdown 相同的检查函数

### 时间点
- 先跑通 markdown 版本的最小闭环（4 条约束 + Gate 检查 + agent 重试补齐）
- 再评估 Word 集成优先级
