# MEMORY.md - 项目协调专家

## 项目调度经验

### 任务依赖模式识别
| 任务类型 | 典型依赖链 | 并行建议 |
|---------|-----------|---------|
| 产品开发 | researcher → product → designer → developer → ops → docs | researcher 与 consultation 可并行 |
| 内容营销 | researcher → content → seo → social → email | 无强依赖，可串行 |
| 商业策划 | researcher → consultation → product → coordinator | coordinator 在关键节点介入 |

### Skill 定义参考
| Skill ID | 适用 Agent | 用途 |
|---------|-----------|------|
| research-competitor-analysis | researcher | 竞品调研，输出对比表 |
| product-prd-writing | product | PRD 撰写 |
| developer-technical-solution | developer | 技术方案编写 |
| ops-deployment-checklist | ops | 部署检查清单 |
| content-copywriting | content | 文案创作 |
| main-geo-workflow | main | GEO 全流程编排 |

### GEO 优化技能体系
| Skill ID | 适用 Agent | 用途 |
|---------|-----------|------|
| content-geo-content-optimization | content | GEO 内容优化 |
| research-geo-competitive-analysis | researcher | GEO 竞品分析 |
| seo-geo-technical-audit | seo | GEO 技术审计 |
| developer-geo-structured-data | developer | GEO 结构化数据 |
| social-geo-brand-presence | social | GEO 品牌曝光 |
| ops-geo-monitoring | ops | GEO 持续监控 |
| tester-geo-validation | tester | GEO 效果验证 |
| analyst-geo-metrics | analyst | GEO 指标分析 |
| docs-geo-documentation | docs | GEO 文档优化 |
| main-geo-workflow | main | GEO 全流程编排 |

### 关键决策点
- **Phase 2 确认**：用户说"同意"才能进入 Phase 3，说"变更"则回到 Phase 1
- **依赖设置**：首任务依赖为空，后续依赖已存在的 task_id
- **子任务拆分**：Worker 自主拆分，Main 不干涉拆分细节
- **waiting_for_input**：Worker 需要用户输入时释放队列，Main 调度其他任务

### 禁止行为（Main 特有）
- ❌ 代替 Worker 写交付物
- ❌ 跳过确认直接调度
- ❌ 同时分派多个任务
- ❌ 手拼 project_id
- ❌ 直接调用 update-project completed
