// ============ Knowledge Base Tab ============

let _kbItems = [];

function kbSortItems(items) {
  return [...items].sort((a, b) => {
    const ta = Date.parse(a.created_at || '') || 0;
    const tb = Date.parse(b.created_at || '') || 0;
    if (tb !== ta) return tb - ta;
    return (b.id || 0) - (a.id || 0);
  });
}

function kbFilterItems(items, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return items;
  return items.filter(m => {
    const title = (m.title || '').toLowerCase();
    const project = (m.project_id || '').toLowerCase();
    const preview = (m.preview || '').toLowerCase();
    const tags = (m.tags || []).join(' ').toLowerCase();
    return title.includes(q) || project.includes(q) || preview.includes(q) || tags.includes(q);
  });
}

function kbFormatTime(iso) {
  if (!iso) return '—';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso.slice(0, 10);
  return fmtListTime(ts);
}

async function loadKnowledgeItems() {
  try {
    const r = await fetch('/api/obs/memory?limit=200');
    const data = await r.json();
    _kbItems = kbSortItems(data.memory || []);
    return _kbItems;
  } catch (_) {
    _kbItems = [];
    return [];
  }
}

function renderKnowledge() {
  const box = DOM['kb-table'];
  if (!box) return;
  const query = DOM['kb-search']?.value || '';
  const filtered = kbFilterItems(_kbItems, query);
  if (DOM['kb-count']) DOM['kb-count'].textContent = String(filtered.length);
  if (!_kbItems.length) {
    box.innerHTML = '<div class="empty">暂无知识库条目</div>';
    return;
  }
  if (!filtered.length) {
    box.innerHTML = '<div class="empty">无匹配条目</div>';
    return;
  }
  box.innerHTML = `<table class="manage-table kb-table"><thead><tr><th>标题</th><th>项目</th><th>标签</th><th>写入时间</th><th>预览</th></tr></thead><tbody>${filtered.map(m => `
    <tr>
      <td><strong>${esc(m.title || '—')}</strong></td>
      <td><code class="cell-sub">${esc(m.project_id || '')}</code></td>
      <td>${(m.tags || []).map(t => `<span class="chip">${esc(t)}</span>`).join(' ') || '—'}</td>
      <td class="cell-meta">${esc(kbFormatTime(m.created_at))}</td>
      <td class="hint kb-preview">${esc(m.preview || '')}</td>
    </tr>`).join('')}</tbody></table>`;
}

async function loadKnowledgeTab() {
  await loadKnowledgeItems();
  renderKnowledge();
}
