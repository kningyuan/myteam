/** Agent 气泡 Markdown 渲染（GFM 子集，无外部依赖） */
(function (global) {
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderInline(text) {
    let s = escapeHtml(text);
    s = s.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return s;
  }

  function splitTableRow(line) {
    let t = line.trim();
    if (!t.includes('|')) return null;
    if (t.startsWith('|')) t = t.slice(1);
    if (t.endsWith('|')) t = t.slice(0, -1);
    return t.split('|').map(c => c.trim());
  }

  function isTableSep(line) {
    const cells = splitTableRow(line);
    if (!cells || !cells.length) return false;
    return cells.every(c => /^:?-{3,}:?$/.test(c));
  }

  function parseTable(lines, start) {
    const header = splitTableRow(lines[start]);
    if (!header || start + 1 >= lines.length || !isTableSep(lines[start + 1])) return null;
    const rows = [];
    let i = start + 2;
    while (i < lines.length) {
      const row = splitTableRow(lines[i]);
      if (!row) break;
      rows.push(row);
      i += 1;
    }
    if (!rows.length && !header.length) return null;

    let html = '<div class="md-table-wrap"><table class="md-table"><thead><tr>';
    header.forEach(c => { html += `<th>${renderInline(c)}</th>`; });
    html += '</tr></thead><tbody>';
    rows.forEach(r => {
      html += '<tr>';
      r.forEach(c => { html += `<td>${renderInline(c)}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    return { html, next: i };
  }

  function renderMarkdown(text) {
    if (!text) return '';
    const lines = String(text).replace(/\r\n/g, '\n').split('\n');
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      if (line.trim().startsWith('```')) {
        const lang = line.trim().slice(3).trim();
        i += 1;
        const buf = [];
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          buf.push(lines[i]);
          i += 1;
        }
        if (i < lines.length) i += 1;
        out.push(`<pre class="md-codeblock"${lang ? ` data-lang="${escapeHtml(lang)}"` : ''}><code>${escapeHtml(buf.join('\n'))}</code></pre>`);
        continue;
      }

      const table = parseTable(lines, i);
      if (table) {
        out.push(table.html);
        i = table.next;
        continue;
      }

      const hm = line.match(/^(#{1,4})\s+(.+)$/);
      if (hm) {
        const lvl = hm[1].length;
        out.push(`<h${lvl} class="md-h${lvl}">${renderInline(hm[2])}</h${lvl}>`);
        i += 1;
        continue;
      }

      if (/^>\s?/.test(line)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          buf.push(lines[i].replace(/^>\s?/, ''));
          i += 1;
        }
        out.push(`<blockquote class="md-quote">${renderInline(buf.join(' '))}</blockquote>`);
        continue;
      }

      if (/^[-*]\s+/.test(line)) {
        out.push('<ul class="md-list">');
        while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
          out.push(`<li>${renderInline(lines[i].replace(/^[-*]\s+/, ''))}</li>`);
          i += 1;
        }
        out.push('</ul>');
        continue;
      }

      if (/^\d+\.\s+/.test(line)) {
        out.push('<ol class="md-list md-olist">');
        while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
          out.push(`<li>${renderInline(lines[i].replace(/^\d+\.\s+/, ''))}</li>`);
          i += 1;
        }
        out.push('</ol>');
        continue;
      }

      if (!line.trim()) {
        i += 1;
        continue;
      }

      const buf = [];
      while (i < lines.length && lines[i].trim() && !lines[i].trim().startsWith('```')
        && !/^(#{1,4})\s/.test(lines[i]) && !/^>\s?/.test(lines[i])
        && !/^[-*]\s+/.test(lines[i]) && !/^\d+\.\s+/.test(lines[i])) {
        const maybeTable = parseTable(lines, i);
        if (maybeTable) break;
        if (splitTableRow(lines[i]) && i + 1 < lines.length && isTableSep(lines[i + 1])) break;
        buf.push(lines[i]);
        i += 1;
      }
      if (buf.length) {
        out.push(`<p class="md-p">${renderInline(buf.join(' '))}</p>`);
      }
    }

    return out.join('\n');
  }

  global.renderAgentMarkdown = renderMarkdown;
})(window);
