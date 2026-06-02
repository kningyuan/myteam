# example.com SEO 基线调研报告

## 调研背景

本次调研旨在对 example.com 域名进行 SEO 现状、流量结构、关键词排名及竞品分析，建立可量化的基线报告。example.com 是互联网中最具标志性的"保留域名"之一，由 IANA 管理，广泛用于技术文档、代码示例和教学场景。了解其 SEO 基线对于评估保留域名在搜索引擎生态中的特殊地位具有参考价值。

## 信息来源

| 来源 | 类型 | 可信度 | 获取时间 |
|------|------|--------|----------|
| example.com 官网 | 一手数据 | ★★★★★ | 2026-06-02 |
| IANA 官方页面 (iana.org/domains/example) | 一手数据 | ★★★★★ | 2026-06-02 |
| WHOIS 查询 (whois.com) | 二手数据 | ★★★★☆ | 2026-06-02 |
| Cloudflare DNS 解析 | 一手数据 | ★★★★★ | 2026-06-02 |
| Semrush 域名分析 | 二手数据 | ★★★☆☆ | 2026-06-02 |

**备注**：部分商业 SEO 工具（如 SimilarWeb、Semrush 详细报告）对 example.com 的流量数据展示受限，因其为保留域名，不纳入常规商业流量统计体系。

## 关键发现

### 1. 域名基本信息

| 字段 | 值 |
|------|-----|
| 域名 | example.com |
| 注册日期 | 1995-08-14 |
| 到期日期 | 2026-08-13 |
| 注册商 | RESERVED-Internet Assigned Numbers Authority (IANA ID: 376) |
| 域名状态 | client delete prohibited, client transfer prohibited, client update prohibited |
| DNS 服务商 | Cloudflare (elliott.ns.cloudflare.com, hera.ns.cloudflare.com) |
| 所属规范 | RFC 2606, RFC 6761 |

### 2. SEO 现状分析

**页面结构**：
- 页面极其精简，仅包含标题 "Example Domain" 和一段说明文字
- 单一内部链接指向 IANA 官方说明页面
- 无导航栏、无页脚、无多媒体内容、无交互元素
- HTML 结构极简，无 JS 框架依赖

**技术 SEO**：
- **HTTPS**：已启用（Cloudflare 托管）
- **移动端适配**：基础响应式，但内容本身无需复杂适配
- **加载速度**：极快（静态页面 + Cloudflare CDN）
- **结构化数据**：无 Schema.org 标记
- **Meta 标签**：基础 title 和 description，无 Open Graph / Twitter Card
- **robots.txt**：未设置明确限制，允许搜索引擎抓取
- **Sitemap**：无 XML Sitemap

**内容 SEO**：
- 页面内容量极少（约 100 字），无关键词策略
- 无博客、无产品页、无落地页
- 内容目的为文档示例，非搜索引流

### 3. 流量结构

| 维度 | 评估 |
|------|------|
| 直接流量 | 主要来源——用户手动输入或从文档/代码中复制链接 |
| 搜索流量 | 极低——页面内容无搜索价值 |
| 引荐流量 | 中等——大量技术文档、教程、Stack Overflow 等引用 |
| 社交流量 | 可忽略 |
| 广告流量 | 无 |

> **说明**：商业流量分析工具（SimilarWeb、Alexa 等）对 example.com 的流量数据通常不展示或标记为"数据不足"，因为该域名不纳入商业流量排名体系。其实际流量主要来自误配置的应用程序、文档引用和开发测试场景。

### 4. 关键词排名

- **无主动关键词排名策略**：页面内容不包含任何商业或信息性关键词
- **品牌词**： "example.com" 本身在 Google 中排名第一（自有域名）
- **长尾词**：部分文档类查询可能因引用而间接出现，但无有机排名
- **AI 搜索可见性**：在 ChatGPT、Perplexity 等 AI 搜索引擎中，example.com 作为"示例域名"的权威引用源会被频繁提及

### 5. 主要竞品/对标域名

| 域名 | 关系 | 说明 |
|------|------|------|
| example.org | 同属 IANA 保留域名 | 功能相同，不同 TLD |
| example.net | 同属 IANA 保留域名 | 功能相同，不同 TLD |
| example.edu | 同属 IANA 保留域名 | 功能相同，不同 TLD |
| test.com | 商业域名 | 已被注册为商业网站，与 example.com 无直接竞争 |
| demo.com | 商业域名 | 已被注册为商业网站 |

> **核心结论**：example.com 不存在传统意义上的"竞品"。它与 example.org、example.net 等同属 IANA 保留域名体系，功能完全一致，不存在流量竞争关系。

## 结论

1. **SEO 基线定位**：example.com 是一个**零 SEO 优化**的保留域名。其页面结构、内容策略、关键词布局均不针对搜索引擎优化，完全服务于文档示例用途。

2. **流量特征**：流量主要来自**直接访问**和**外部文档引用**，而非搜索引擎有机流量。商业流量分析工具对其数据覆盖有限。

3. **技术健康度**：基础设施层面表现优秀——HTTPS 启用、Cloudflare CDN 加速、域名状态保护完善。但缺乏现代 SEO 必备元素（Sitemap、结构化数据、OG 标签等）。

4. **竞品格局**：无商业竞品。唯一对标对象为同属 IANA 保留的 example.org / example.net / example.edu。

5. **基线建议**：若将 example.com 作为 SEO 测试或基准对照对象，建议关注以下指标作为基线：
   - 有机搜索流量 ≈ 0
   - 关键词排名数量 ≈ 1（仅品牌词 "example.com"）
   - 反向链接数量：大量（来自全球技术文档），但均为非商业性质
   - Domain Authority：因 IANA 权威性，理论上较高，但无商业 SEO 工具可准确评估

---

*报告生成时间：2026-06-02 | 调研人：opencode (SenseNova 6.7 Flash-Lite)*
