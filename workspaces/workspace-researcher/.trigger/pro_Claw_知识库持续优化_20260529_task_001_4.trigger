{
  "phase": "execute",
  "project_id": "pro_Claw_知识库持续优化_20260529",
  "task_id": "task_001_4",
  "task_name": "项目与脚本内容盘点",
  "description": "盘点projects/、scripts/、archive/、backups/目录下的内容，评估项目状态、脚本可用性和归档内容的保留价值",
  "agent": "researcher",
  "parent_task": "task_001",
  "sub_task_index": "4/6",
  "deliverable_path": "/Users/user/.openclaw/tasks/projects/pro_Claw_知识库持续优化_20260529/deliverables/task_001_4_deliverable.md",
  "task_type": "research",
  "template": {
    "required_heading_level": 2,
    "sections": [
      {
        "name": "调研背景",
        "description": "说明本次调研的背景、目的、范围和方法论",
        "required": true,
        "example": "随着AI生成式搜索引擎（如Perplexity、ChatGPT Search）的兴起，GEO（Generative Engine Optimization）成为新的优化领域。本报告系统调研了GEO的主流优化方式和前沿手段。"
      },
      {
        "name": "信息来源",
        "description": "列出调研的数据来源，包括行业报告、官方文档、社区讨论等，评估每条来源的可信度",
        "required": true,
        "example": "| 来源类型 | 具体来源 | 可信度 |\n|----------|----------|--------|\n| 行业报告 | Moz、Ahrefs | 高 |\n| 官方文档 | Perplexity Blog | 高 |"
      },
      {
        "name": "关键发现",
        "description": "列出调研得出的核心发现，按重要性或主题分类，每个发现附证据",
        "required": true,
        "example": "发现1：GEO优化在Perplexity中的引用率比传统SEO高3倍。依据：Moz 2024年研究报告显示..."
      },
      {
        "name": "结论",
        "description": "总结调研结论，给出可操作的建议和下一步行动",
        "required": true,
        "example": "GEO优化的核心在于内容质量+结构化数据+引用策略的三位一体。建议优先建立高质量内容库..."
      },
      {
        "name": "风险评估",
        "description": "说明潜在局限、不确定性和建议关注的风险点",
        "required": false,
        "example": "当前GEO领域变化较快，主流AI搜索的算法不透明，建议每季度更新一次策略。"
      }
    ],
    "structure": [
      "H1 标题作为报告主标题",
      "每个章节使用 H2 标题",
      "数据使用表格呈现",
      "引用来源标注出处和链接"
    ]
  },
  "standard_requirements": {
    "required_sections": [
      "调研背景",
      "信息来源",
      "关键发现",
      "结论"
    ],
    "must_include_keywords": [
      "数据来源",
      "可信度"
    ],
    "min_length": 500
  },
  "created_at": "2026-05-29T18:26:24.580988",
  "continuous_context": {
    "project_name": "Claw 知识库持续优化",
    "project_goal": "对 Claw 知识库进行持续内容优化和发布：定期审核现有内容、发现知识缺口、撰写新文章、通过质量门禁审核后发布。使用 publish-post 行动在浏览器中真实执行发布流程并截图留证。",
    "current_state": "项目初始化中",
    "accumulated_learnings": "",
    "cycle_id": 4
  }
}