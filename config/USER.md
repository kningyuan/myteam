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
