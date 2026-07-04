import { describe, it, expect } from "vitest"
import { renderMarkdown, normalizeAgentMarkdown } from "@/lib/markdown"

describe("normalizeAgentMarkdown", () => {
  it("空输入返回空串", () => {
    expect(normalizeAgentMarkdown("")).toBe("")
  })
})

describe("renderMarkdown", () => {
  it("空输入返回空串", () => {
    expect(renderMarkdown("")).toBe("")
  })

  it("转义 HTML，防止注入", () => {
    const html = renderMarkdown("<script>alert(1)</script>")
    expect(html).not.toContain("<script>")
    expect(html).toContain("&lt;script&gt;")
  })

  it("粗体 ** → <strong>", () => {
    expect(renderMarkdown("**重点**")).toContain("<strong>重点</strong>")
  })

  it("斜体 * → <em>", () => {
    expect(renderMarkdown("*文字*")).toContain("<em>文字</em>")
  })

  it("行内代码 `code` → <code>", () => {
    expect(renderMarkdown("`x`")).toContain('<code class="md-inline-code">x</code>')
  })

  it("链接正确渲染", () => {
    const html = renderMarkdown("[官网](https://example.com)")
    expect(html).toContain('href="https://example.com"')
    expect(html).toContain(">官网</a>")
  })

  it("标题 h1-h4", () => {
    expect(renderMarkdown("# 一级")).toContain("<h1")
    expect(renderMarkdown("#### 四级")).toContain("<h4")
  })

  it("无序列表", () => {
    const html = renderMarkdown("- 项A\n- 项B")
    expect(html).toContain('<ul class="md-list">')
    expect(html).toContain("<li>项A</li>")
    expect(html).toContain("<li>项B</li>")
  })

  it("代码块", () => {
    const html = renderMarkdown("```py\nprint(1)\n```")
    expect(html).toContain('<pre class="md-codeblock"')
    expect(html).toContain('data-lang="py"')
    expect(html).toContain("print(1)")
  })

  it("GFM 表格", () => {
    const html = renderMarkdown("| 名称 | 值 |\n| --- | --- |\n| a | 1 |")
    expect(html).toContain('<table class="md-table">')
    expect(html).toContain("<th>名称</th>")
    expect(html).toContain("<td>1</td>")
  })
})
