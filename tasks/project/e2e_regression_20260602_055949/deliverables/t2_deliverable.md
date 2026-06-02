# example.com SEO 优化方案

> 基于 t1 基线调研（2026-06-02），制定技术 SEO、内容 SEO、外链建设等优化方案。
> 说明：example.com 为 IANA 保留域名（RFC 2606 / RFC 6761），其优化目标与商业网站有本质差异——核心是**提升文档引用可见性与 AI 搜索可理解性**，而非商业流量增长。

---

## 一、关键词研究

### 1.1 现状评估

| 指标 | 当前值 | 说明 |
|------|--------|------|
| 有机搜索关键词数 | ≈ 0 | 页面无关键词布局 |
| 品牌词排名 | 第 1 位 | "example.com" 自有域名 |
| 长尾词排名 | 无 | 内容量不足 |
| AI 搜索提及率 | 高 | 作为"示例域名"权威引用源 |

### 1.2 关键词策略

由于 example.com 的特殊属性（保留域名，非商业用途），关键词策略需重新定义目标：

**核心关键词簇（优先级 P0）**

| 关键词簇 | 搜索意图 | 预估月搜索量 | 竞争度 | 策略 |
|----------|----------|-------------|--------|------|
| "example domain" | 信息性 | 高 | 低 | 自然覆盖（页面已有） |
| "example.com" | 导航性 | 高 | 极低 | 保持品牌词首位 |
| "RFC 2606" / "RFC 6761" | 信息性 | 中 | 低 | 通过内容补充覆盖 |
| "reserved domain" | 信息性 | 中 | 中 | 内容策略补充 |
| "documentation example domain" | 信息性 | 中 | 低 | 内容策略补充 |

**长尾关键词簇（优先级 P1）**

| 关键词簇 | 搜索意图 | 策略 |
|----------|----------|------|
| "what is example.com used for" | 信息性 | FAQ 内容补充 |
| "example.com vs example.org" | 比较性 | 对比内容补充 |
| "how to use example domain in code" | 操作指导 | 代码示例页面 |
| "IANA example domains list" | 信息性 | 聚合页面 |

### 1.3 关键词布局建议

- **H1**: 保持 "Example Domain"（品牌一致性）
- **H2**: 新增 "What Is This Domain Used For?" 解释性标题
- **Meta Title**: "Example Domain — IANA Reserved Domain for Documentation"（增加权威词）
- **Meta Description**: "example.com is an IANA-reserved domain (RFC 2606, RFC 6761) used for documentation, code examples, and testing. Learn about reserved domains."
- **URL 结构**: 当前为单页，建议补充 `/faq`、`/about` 子页面覆盖长尾词

---

## 二、技术优化

### 2.1 优先级矩阵

| 优先级 | 优化项 | 当前状态 | 预期收益 | 工作量 |
|--------|--------|----------|----------|--------|
| **P0** | XML Sitemap | ❌ 缺失 | 提升爬虫效率 | 低 |
| **P0** | 结构化数据 (Schema.org) | ❌ 缺失 | AI 搜索可理解性↑ | 低 |
| **P0** | Open Graph / Twitter Card | ❌ 缺失 | 引用分享效果↑ | 低 |
| **P1** | robots.txt 明确化 | ⚠️ 未设置 | 爬虫行为可控 | 低 |
| **P1** | Canonical 标签 | ❌ 缺失 | 避免重复内容 | 低 |
| **P1** | 多语言支持 (hreflang) | ❌ 缺失 | 国际文档引用↑ | 中 |
| **P2** | Core Web Vitals 监控 | ✅ 良好 | 维持现状 | 低 |
| **P2** | 页面内 JS/CSS 压缩 | ✅ 无依赖 | 无需处理 | — |

### 2.2 详细实施方案

#### 2.2.1 XML Sitemap（P0）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2026-06-02</lastmod>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
  <!-- 未来补充: /faq, /about 等页面 -->
</urlset>
```

- 提交至 Google Search Console 和 Bing Webmaster Tools
- 在 robots.txt 中引用 Sitemap 路径

#### 2.2.2 结构化数据（P0）

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Example Domain",
  "url": "https://example.com/",
  "description": "IANA-reserved domain for documentation and testing purposes",
  "publisher": {
    "@type": "Organization",
    "name": "Internet Assigned Numbers Authority (IANA)",
    "url": "https://www.iana.org/"
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://www.iana.org/domains/example",
    "query-input": "required"
  }
}
```

- 使用 `WebSite` + `Organization` 组合 Schema
- 增加 FAQPage Schema（若补充 FAQ 页面）
- 验证工具：Google Rich Results Test

#### 2.2.3 Open Graph / Twitter Card（P0）

```html
<!-- Open Graph -->
<meta property="og:title" content="Example Domain" />
<meta property="og:description" content="IANA-reserved domain for documentation and testing." />
<meta property="og:url" content="https://example.com/" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Example Domain" />

<!-- Twitter Card -->
<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="Example Domain" />
<meta name="twitter:description" content="IANA-reserved domain for documentation and testing." />
```

#### 2.2.4 robots.txt（P1）

```txt
User-agent: *
Allow: /

Sitemap: https://example.com/sitemap.xml

# 允许 AI 爬虫
Allow: /
```

> **注意**：当前 example.com 无 robots.txt 限制，建议显式声明以增强可控性，同时明确允许 AI 爬虫（ChatGPT、Perplexity、Claude 等）抓取。

#### 2.2.5 Canonical 标签（P1）

```html
<link rel="canonical" href="https://example.com/" />
```

防止 Cloudflare 可能产生的 HTTP/HTTPS 或 www/non-www 重复内容问题。

#### 2.2.6 Core Web Vitals 维持（P2）

当前基础设施已达标，建议：

- 保持 Cloudflare CDN 配置不变
- 设置 Lighthouse CI 定期监控（目标：LCP < 1.2s, FID < 10ms, CLS < 0.1）
- 当前页面几乎无 JS/CSS，CWV 天然优秀

---

## 三、内容策略

### 3.1 内容现状与差距

| 维度 | 当前 | 目标 | 差距 |
|------|------|------|------|
| 页面字数 | ~100 字 | ~500-800 字 | 内容量不足 |
| 页面数量 | 1 页 | 3-5 页 | 缺乏内容矩阵 |
| 多媒体 | 无 | 1-2 张信息图 | 视觉缺失 |
| 更新频率 | 永久不变 | 年度审查 | 无维护机制 |

### 3.2 内容规划（按优先级）

#### P0：基础解释页面（/about）

**目标**：覆盖 "what is example.com"、"reserved domain" 等核心信息性搜索

**内容大纲**：
1. 什么是 example.com？（RFC 2606 / RFC 6761 背景）
2. 谁管理这个域名？（IANA 角色说明）
3. 它用于什么场景？（文档示例、代码测试、教学）
4. 与其他保留域名的关系（example.org / .net / .edu）
5. 链接至 IANA 官方说明页面

**预期效果**：
- 覆盖 5-10 个信息性长尾关键词
- 提升 AI 搜索中的权威引用率
- 为外部文档提供更丰富的引用内容

#### P0：FAQ 页面（/faq）

**目标**：覆盖 "example.com vs example.org"、"how to use example domain" 等比较性和操作性搜索

**内容大纲**：
1. example.com 和 example.org 有什么区别？
2. 我可以在生产环境中使用 example.com 吗？
3. 为什么我的应用默认指向 example.com？
4. 如何在代码示例中使用 example.com？
5. example.com 有 DNS 解析吗？指向哪里？

**预期效果**：
- 覆盖 8-15 个 FAQ 类长尾关键词
- FAQ Schema 结构化数据可触发 Google 精选摘要
- 提升 AI 搜索回答中的引用概率

#### P1：技术文档聚合页（/docs）

**目标**：覆盖开发者搜索场景

**内容大纲**：
1. 在 HTTP 测试中使用 example.com
2. 在 DNS 配置中使用 example.com
3. 在代码示例中使用 example.com（多语言示例）
4. 在 API 文档中使用 example.com
5. 常见误配置排查

**预期效果**：
- 覆盖开发者搜索场景的长尾词
- 增加 Stack Overflow / GitHub 等平台的引用来源

### 3.3 内容质量标准

- **关键词密度**：核心词 1-2%，自然分布，禁止堆砌
- **标题层级**：H1 → H2 → H3 严格递进，每页 1 个 H1
- **内部链接**：主页 ↔ /about ↔ /faq ↔ /docs 互相链接
- **外部链接**：指向 IANA 官方页面（iana.org/domains/example），增强权威性
- **图片 Alt 文本**：所有图片必须有描述性 alt 属性
- **URL 结构**：`example.com/about`、`example.com/faq`、`example.com/docs`（短小清晰）

---

## 四、外链建设

### 4.1 现状评估

| 维度 | 评估 |
|------|------|
| 反向链接总量 | 极多（全球技术文档引用） |
| 链接质量 | 高（来自 MDN、Stack Overflow、GitHub、官方文档等） |
| 链接类型 | 均为自然引用，非主动建设 |
| 锚文本 | 多样化（"example.com"、"example domain"、"documentation example"） |

### 4.2 外链策略

由于 example.com 的特殊性，传统外链建设（主动 outreach、交换链接等）**不适用且不建议**。策略重点应为：

#### 4.2.1 自然引用维护（P0）

- **目标**：维持现有高权威链接的自然增长
- **措施**：
  - 确保页面内容准确、权威（与 IANA 官方信息一致）
  - 补充 FAQ 和 /about 页面，为引用提供更丰富的内容目标
  - 保持 HTTPS 和 Cloudflare 基础设施稳定

#### 4.2.2 AI 搜索可见性优化（P0）

| 平台 | 策略 |
|------|------|
| ChatGPT / GPT Store | 确保结构化数据完整，FAQ 内容清晰，便于 AI 提取 |
| Perplexity | 通过 FAQPage Schema 提升答案引用概率 |
| Claude | 保持内容简洁、权威、可引用 |
| Google SGE | 结构化数据 + FAQ 精选摘要 |

#### 4.2.3 文档引用促进（P1）

- 在 IANA 官方页面（iana.org/domains/example）增加对 example.com 的明确引用
- 推动主流技术文档平台（MDN、W3C 规范）在示例代码中使用 example.com 作为标准示例域名
- 与开源项目维护者沟通，在 README 和文档中使用 example.com 作为示例

### 4.3 外链质量监控指标

| 指标 | 当前（估算） | 目标（6 个月） |
|------|-------------|---------------|
| 反向链接总数 | 极多（不可精确统计） | 维持 + 自然增长 |
| 高权威链接占比 | 高（.edu / .gov / 技术权威） | 维持 ≥ 80% |
| 锚文本多样性 | 高 | 维持 |
| AI 搜索提及率 | 高 | 进一步提升 |

---

## 五、效果预估

### 5.1 量化预期（6 个月）

| 指标 | 当前基线 | 6 个月目标 | 预期增幅 |
|------|----------|-----------|---------|
| 有机搜索关键词数 | ≈ 0 | 15-25 | 新增 |
| 有机搜索流量（估算） | ≈ 0 | 低（保留域名属性限制） | 新增 |
| 页面收录数 | 1 | 3-5 | +200-400% |
| 结构化数据覆盖率 | 0% | 100%（核心页面） | 新增 |
| FAQ 精选摘要触发 | 无 | 1-2 个 | 新增 |
| AI 搜索提及率 | 高 | 更高（内容补充后） | +20-30% |
| 外部文档引用质量 | 高 | 更高（内容更丰富） | +10-15% |

### 5.2 定性预期

1. **技术 SEO**：从"零现代 SEO 元素"到"完整覆盖 Sitemap + Schema + OG + Canonical"，达到保留域名的最佳实践标准。

2. **内容 SEO**：从单页 ~100 字到 3-5 页 ~2000-3000 字的内容矩阵，覆盖核心信息性搜索和开发者场景。

3. **AI 搜索可见性**：通过结构化数据和 FAQ 内容，显著提升在 ChatGPT、Perplexity、Google SGE 等 AI 搜索引擎中的引用率和答案准确性。

4. **品牌权威性**：强化 example.com 作为"保留域名标准参考"的定位，与 IANA 官方信息保持一致。

### 5.3 风险与限制

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| 保留域名属性限制 | IANA 可能不允许大幅修改页面内容 | 所有优化方案需经 IANA 审核批准 |
| 商业流量工具不可用 | SimilarWeb/Semrush 等对保留域名数据覆盖有限 | 依赖 GSC + 自建监控 |
| 无商业转化目标 | 无法用 ROI 衡量效果 | 以"引用质量"和"AI 可见性"为核心指标 |
| 竞品无意义 | example.org/net/edu 功能完全一致 | 不做竞品对标，专注自身优化 |

---

## 六、执行路线图

| 阶段 | 时间 | 任务 | 负责人 |
|------|------|------|--------|
| **Phase 1** | 第 1-2 周 | P0 技术优化：Sitemap、Schema、OG、Canonical、robots.txt | SEO 技术 |
| **Phase 2** | 第 3-4 周 | P0 内容创建：/about 页面 + /faq 页面 | 内容团队 |
| **Phase 3** | 第 5-6 周 | P1 技术优化：hreflang、多语言支持 | SEO 技术 |
| **Phase 4** | 第 7-8 周 | P1 内容创建：/docs 页面 + 代码示例 | 内容团队 |
| **Phase 5** | 第 9-12 周 | 效果监控、数据收集、迭代优化 | 全团队 |

---

*方案制定时间：2026-06-02 | 制定人：opencode (SenseNova 6.7 Flash-Lite)*
*基于 t1 基线调研报告 | 交互 ID: e2e_regression_20260602_055949:t2:execute:1*
