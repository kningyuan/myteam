/** GFM 子集 Markdown 渲染（与 v1 markdown.js 同源逻辑） */

function splitTabRow(line: string): string[] | null {
  if (!line.includes("\t")) return null
  const cells = line.split("\t").map((c) => c.trim())
  if (cells.length < 2) return null
  if (cells.every((c) => !c)) return null
  return cells
}

/** 连续 2+ 空格分列（Agent 有时不用 Tab） */
function splitSpaceRow(line: string): string[] | null {
  if (!/\s{2,}/.test(line)) return null
  const cells = line.split(/\s{2,}/).map((c) => c.trim())
  if (cells.length < 2) return null
  if (cells.every((c) => !c)) return null
  if (cells.some((c) => c.length > 120)) return null
  return cells
}

function splitTableLikeRow(line: string): string[] | null {
  return splitTabRow(line) ?? splitSpaceRow(line)
}

function looksLikeSectionTitle(line: string): boolean {
  const t = line.trim()
  if (!t || t.length > 48) return false
  if (splitTableLikeRow(t) || t.startsWith("|") || t.startsWith("#")) return false
  if (/^[>\-*\d]/.test(t)) return false
  if (/[。！？.!?]$/.test(t)) return false
  return true
}

/** Agent 常输出 TSV 块；转为 GFM 表格并给分节标题加 ### */
export function normalizeAgentMarkdown(text: string): string {
  if (!text) return ""
  const lines = String(text).replace(/\r\n/g, "\n").split("\n")
  const out: string[] = []
  let i = 0

  while (i < lines.length) {
    const tabRow = splitTableLikeRow(lines[i])
    if (tabRow) {
      if (out.length > 0 && looksLikeSectionTitle(out[out.length - 1])) {
        out[out.length - 1] = `### ${out[out.length - 1].trim()}`
      }
      const tableRows: string[][] = [tabRow]
      i += 1
      while (i < lines.length) {
        const next = splitTableLikeRow(lines[i])
        if (!next || next.length !== tabRow.length) break
        tableRows.push(next)
        i += 1
      }
      const width = Math.max(...tableRows.map((r) => r.length))
      const pad = (cells: string[]) => {
        const next = [...cells]
        while (next.length < width) next.push("")
        return next.slice(0, width)
      }
      out.push(`| ${pad(tableRows[0]).join(" | ")} |`)
      out.push(`| ${pad(tableRows[0]).map(() => "---").join(" | ")} |`)
      for (let r = 1; r < tableRows.length; r += 1) {
        out.push(`| ${pad(tableRows[r]).join(" | ")} |`)
      }
      out.push("")
      continue
    }
    out.push(lines[i])
    i += 1
  }
  return out.join("\n")
}

function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function renderInline(text: string): string {
  let s = escapeHtml(text)
  s = s.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>")
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  return s
}

function splitTableRow(line: string): string[] | null {
  let t = line.trim()
  if (!t.includes("|")) return null
  if (t.startsWith("|")) t = t.slice(1)
  if (t.endsWith("|")) t = t.slice(0, -1)
  return t.split("|").map((c) => c.trim())
}

function isTableSep(line: string): boolean {
  const cells = splitTableRow(line)
  if (!cells?.length) return false
  return cells.every((c) => /^:?-{3,}:?$/.test(c))
}

function buildTableHtml(header: string[], rows: string[][]): string {
  const width = header.length
  const padRow = (cells: string[]) => {
    const next = [...cells]
    while (next.length < width) next.push("")
    return next.slice(0, width)
  }
  let html = '<div class="md-table-wrap"><table class="md-table"><thead><tr>'
  header.forEach((c) => {
    html += `<th>${renderInline(c)}</th>`
  })
  html += "</tr></thead><tbody>"
  rows.forEach((r) => {
    html += "<tr>"
    padRow(r).forEach((c) => {
      html += `<td>${renderInline(c)}</td>`
    })
    html += "</tr>"
  })
  html += "</tbody></table></div>"
  return html
}

function parseTable(lines: string[], start: number): { html: string; next: number } | null {
  const header = splitTableRow(lines[start])
  if (!header) return null

  if (start + 1 < lines.length && isTableSep(lines[start + 1])) {
    const rows: string[][] = []
    let i = start + 2
    while (i < lines.length) {
      const row = splitTableRow(lines[i])
      if (!row) break
      rows.push(row)
      i += 1
    }
    return { html: buildTableHtml(header, rows), next: i }
  }

  const nextRow = start + 1 < lines.length ? splitTableRow(lines[start + 1]) : null
  if (nextRow && !isTableSep(lines[start + 1])) {
    const rows: string[][] = [nextRow]
    let i = start + 2
    while (i < lines.length) {
      const row = splitTableRow(lines[i])
      if (!row) break
      rows.push(row)
      i += 1
    }
    return { html: buildTableHtml(header, rows), next: i }
  }

  return null
}

export function renderMarkdown(text: string): string {
  if (!text) return ""
  const lines = normalizeAgentMarkdown(text).replace(/\r\n/g, "\n").split("\n")
  const out: string[] = []
  let i = 0
  let sectionOpen = false

  const closeSection = () => {
    if (sectionOpen) {
      out.push("</section>")
      sectionOpen = false
    }
  }

  const openSectionIfHeading = (lvl: number) => {
    if (lvl >= 3 && lvl <= 4) {
      closeSection()
      out.push('<section class="md-section">')
      sectionOpen = true
    } else {
      closeSection()
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim().startsWith("```")) {
      closeSection()
      const lang = line.trim().slice(3).trim()
      i += 1
      const buf: string[] = []
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i])
        i += 1
      }
      if (i < lines.length) i += 1
      out.push(
        `<pre class="md-codeblock"${lang ? ` data-lang="${escapeHtml(lang)}"` : ""}><code>${escapeHtml(buf.join("\n"))}</code></pre>`,
      )
      continue
    }

    const table = parseTable(lines, i)
    if (table) {
      if (!sectionOpen) {
        out.push('<section class="md-section">')
        sectionOpen = true
      }
      out.push(table.html)
      i = table.next
      continue
    }

    const hm = line.match(/^(#{1,4})\s+(.+)$/)
    if (hm) {
      const lvl = hm[1].length
      openSectionIfHeading(lvl)
      out.push(`<h${lvl} class="md-h md-h${lvl}">${renderInline(hm[2])}</h${lvl}>`)
      i += 1
      continue
    }

    if (/^>\s?/.test(line)) {
      closeSection()
      const buf: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ""))
        i += 1
      }
      out.push(`<blockquote class="md-quote">${renderInline(buf.join(" "))}</blockquote>`)
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      closeSection()
      out.push('<ul class="md-list">')
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        out.push(`<li>${renderInline(lines[i].replace(/^[-*]\s+/, ""))}</li>`)
        i += 1
      }
      out.push("</ul>")
      continue
    }

    if (/^\d+\.\s+/.test(line)) {
      closeSection()
      out.push('<ol class="md-list md-olist">')
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        out.push(`<li>${renderInline(lines[i].replace(/^\d+\.\s+/, ""))}</li>`)
        i += 1
      }
      out.push("</ol>")
      continue
    }

    if (!line.trim()) {
      i += 1
      continue
    }

    const buf: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !/^(#{1,4})\s/.test(lines[i]) &&
      !/^>\s?/.test(lines[i]) &&
      !/^[-*]\s+/.test(lines[i]) &&
      !/^\d+\.\s+/.test(lines[i])
    ) {
      const maybeTable = parseTable(lines, i)
      if (maybeTable) break
      if (splitTableRow(lines[i]) && i + 1 < lines.length && isTableSep(lines[i + 1])) break
      buf.push(lines[i])
      i += 1
    }
    if (buf.length) {
      closeSection()
      out.push(`<p class="md-p">${renderInline(buf.join(" "))}</p>`)
    }
  }

  closeSection()
  return out.join("\n")
}
