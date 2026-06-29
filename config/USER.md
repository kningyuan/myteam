# 团队交付规则

## style（风格偏好）
- 交付物用中文撰写，技术术语保留英文原文
- Markdown 格式，章节标题用 ## 二级标题
- 代码块标注语言类型（python/bash/json/yaml）
- 数据和结论必须标注来源（报告名+年份+页码 或 URL）
- 表格用于对比/参数说明，列表用于步骤/清单，不混用
- 中文字体显式声明 Noto Sans CJK SC，英文用 Inter
- 交付物标题用结论性语句（"Q3营收增长42%"而非"营收分析"）

## avoid（禁忌）
- 禁止使用"有潜力""建议完善""逐步优化"等空话替代可验证结论
- 禁止编造数据或路径
- 禁止忽略 intent 中的硬性要求（数量、格式、范围）
- 禁止交付 stub（"待补充""TODO""占位"）
- 禁止只给方案不给替代方案对比
- 禁止无数据支撑的判断（"用户可能需要""市场应该很大"）
- 禁止紫色渐变+Inter字体+rounded-2xl 的 AI 同质化设计
- 禁止 3D 饼图和双 Y 轴图表

## principles（决策原则）
- 先扫描清单再动手，不即兴发挥
- 结论必须 Pass/Fail，不给模糊评价
- 每个发现须有可复现命令或代码路径佐证
- Out of Scope 须明确列出，不少于 3 条
- 方案须含至少 2 个替代方案对比
- 预期效果须为 SMART 目标（具体/可度量/可达成/相关/有时限）
- 风险评估须含概率+影响+应对策略三要素
- 调试须先复现再定位，禁止随机改代码试

## quality（质量标准）
- 函数不超过 30 行（Python）/ 20 行（TypeScript）
- 圈复杂度 ≤ 10，嵌套深度 ≤ 3 层
- 测试覆盖率：核心逻辑 ≥90%，工具函数 ≥95%，API ≥70%
- 代码审查清单须逐项标注 Pass/Fail
- 交付物须有质量检查清单，逐条走查

## communication（协作规范）
- 任务交接须包含：上下文摘要 + 交付物清单 + 待办事项
- 代码提交用 conventional commits（feat/fix/docs/refactor/perf/test/chore）
- Code Review 24 小时内完成，区分 blocking 和 non-blocking
- 事故复盘须含：时间线 + 根因 + 改进项 + 责任人
- 知识沉淀：每个完成的任务须有可复用的经验写入 KB

## tools（工具与库）
- 调研类任务：优先用 WebSearch + WebFetch
- 代码类任务：遵循 backend/frontend-engineering-methodology
- 文档类任务：遵循 technical-writing-methodology 的交付模板
- 测试类任务：用 Playwright + pytest
- 设计类任务：遵循 frontend-design-aesthetics 的反 AI 审美清单
- 数据可视化：遵循 data-visualization-methodology 的图表选型矩阵
- 方案撰写：遵循 proposal-writing-methodology 的黄金七段式
- 演示文稿：遵循 presentation-design-methodology 的一页一观点原则
- 竞品分析：遵循 competitive-analysis-methodology 的六步闭环流程
- 部署运维：遵循 devops-cicd-methodology 的 GitOps + 渐进式交付
- 设计系统：遵循 design-system-methodology 的 Token 分层原则
- 技术债务：遵循 tech-debt-management 的 ROI 矩阵排序

## architecture（架构规范）
- 新增 CLI 后端只加 adapters/<cli>/ 目录，不改上层逻辑
- 系统内核/策略注册表/Skill Pack 三层硬隔离，不跨层
- 结构在代码（Pydantic），约束在配置（templates.yaml）
- Gate 验收用同一 registry spec，down-link 与 check-link 共用一份
- 新 task_type 须先注册到 templates.yaml，不能只写 Skill

## security（安全规范）
- 密钥禁止硬编码，须用 Vault 或环境变量
- CI 须集成 SAST/DAST/依赖漏洞扫描
- 生产环境禁止手动部署，须通过 CI/CD
- 上线须含回滚预案（触发条件+步骤+验证）
- 告警须可执行、有优先级、避免告警风暴

## role-product（产品专家专属）
- PRD 须含黄金七段式：背景目标/用户画像/需求清单(P0/P1/P2)/功能设计/数据指标/风险评估/里程碑
- 需求优先级用 RICE 评分（Reach×Impact×Confidence/Effort）或 MoSCoW 法
- 竞品分析须横向对比≥3个竞品，能力矩阵标注有/无/优/劣
- 业务诊断用 5Whys 根因分析，每个 Why 基于事实而非猜测
- 头脑风暴：实现前先产出设计方案，须含≥2个替代方案对比

## role-architect（系统架构师专属）
- 架构评审逐项标注 Pass/Fail：分层/接口契约/依赖方向/循环依赖/水平扩展/单点故障/数据一致性
- 技术选型须对比≥3个方案，维度：功能/性能/社区/学习曲线/运维/许可证
- Well-Architected 六支柱：卓越运营/安全/可靠性/性能效率/成本优化/可持续性
- 架构图须用结构化 DSL（Mermaid/PlantUML/Graphviz），禁止纯文字描述
- 渐进式交付：蓝绿/金丝雀，监控错误率/P99延迟/吞吐量

## role-developer（研发工程师专属）
- TDD 强制：先写失败测试(RED)→最小实现(GREEN)→重构(REFACTOR)
- 重构信号：函数>30行、圈复杂度>10、嵌套>3层、重复代码、参数>5个
- API 设计：RESTful 名词复数、版本化、cursor 分页、统一错误结构、幂等键
- 错误处理三原则：快速失败/fail-safe/可观测(traceId+上下文)
- 代码审查：早审查勤审查，Critical 立即修，Important 继续前修

## role-tester（测试工程师专属）
- 测试用例设计：等价类划分/边界值分析/决策表/状态迁移/错误猜测/组合测试(PICT)
- 测试金字塔：单元70%/集成20%/E2E10%，反模式：冰淇淋/沙漏
- 覆盖率：核心逻辑≥90%，工具≥95%，API≥70%
- 回归测试须 Red-Green 验证（写→通过→还原→失败→恢复→通过）
- 验收报告逐项对照标准标注 Pass/Fail，须含测试证据

## role-designer（UI设计工程师专属）
- 设计系统 Token 三层：Global(色板/字号/间距)/Alias(语义化)/Component(组件级)
- 禁止组件中硬编码颜色值，须引用 Token
- 反 AI 审美：禁止紫色渐变+Inter+rounded-2xl、3D饼图、双Y轴、毛玻璃滥用
- 交互原型须标注：页面状态(默认/加载/空/错误/成功)、交互触发、状态转换、边缘情况
- 数据可视化遵循 data-ink 比例，克制动画仅在解释时用
