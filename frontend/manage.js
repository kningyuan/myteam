// ============ Agent List (sidebar) ============

function renderAgentList() {
  if (!DOM['agent-list']) return;
  const visible = S.agents.filter(a => !S.hiddenAgents.has(a.id));
  if (!visible.length) {
    DOM['agent-list'].innerHTML = '<div class="empty">无可见 Agent<br><small>用上方搜索找回已删对话</small></div>';
    return;
  }
  const now = Date.now();
  const sorted = [...visible].sort((a, b) => {
    const bgA = (S.agentMessages[a.id] || []).some(m => m._new);
    const bgB = (S.agentMessages[b.id] || []).some(m => m._new);
    if (bgA && !bgB) return -1; if (!bgA && bgB) return 1;
    return agentLastActivityTs(b.id) - agentLastActivityTs(a.id);
  });
  DOM['agent-list'].innerHTML = sorted.map(a => {
    const lastTs = agentLastActivityTs(a.id);
    const rel = formatRelativeTime(lastTs);
    const unread = (S.agentMessages[a.id] || []).filter(m => m._new).length;
    return `<div class="sidebar-item ${S.currentAgentId === a.id ? 'active' : ''}${unread ? ' has-new' : ''}" data-id="${a.id}">
      <span class="s-icon avatar-badge">${esc(getAvatar(a.id))}</span>
      <span class="s-name">${esc(a.name)}</span>
      <span class="s-sub">${rel ? esc(rel) : ''}</span>
      ${unread ? `<span class="s-badge">${unread > 99 ? '99+' : unread}</span>` : ''}
      <span class="s-del" data-del-agent="${a.id}" title="删除对话">${ic('x')}</span>
    </div>`;
  }).join('');
  DOM['agent-list'].querySelectorAll('.sidebar-item').forEach(el => { el.addEventListener('click', e => { if (e.target.closest('[data-del-agent]')) return; selectAgent(el.dataset.id); }); });
  DOM['agent-list'].querySelectorAll('[data-del-agent]').forEach(el => { el.addEventListener('click', e => { e.stopPropagation(); deleteChatWindow(el.dataset.delAgent); }); });
}

function startSidebarPoll() {
  if (S.sidebarPollTimer) clearInterval(S.sidebarPollTimer);
  S.sidebarPollTimer = setInterval(async () => {
    const tab = document.querySelector('.nav-tab.active')?.dataset.tab;
    if (tab === 'groups') { await loadGroups(); renderGroupList(); }
    else if (tab === 'chat') {
      const ids = [S.currentAgentId, 'main'].filter(Boolean);
      for (const id of [...new Set(ids)]) {
        try {
          const r = await fetch(`/api/agents/${encodeURIComponent(id)}/chats`);
          const d = await r.json();
          const msgs = d.messages || [];
          let existing = S.agentMessages[id] || [];
          let changed = false;
          for (const m of msgs) { if (!existing.some(x => x.ts === m.ts)) { m._new = true; existing.push(m); changed = true; } }
          if (changed) {
            S.agentMessages[id] = existing;
            if (S.hiddenAgents.has(id)) { try { await fetch(`/api/chat/${encodeURIComponent(id)}/restore`, { method: 'POST' }); } catch (e) {} S.hiddenAgents.delete(id); }
          }
        } catch (e) { /* ignore */ }
      }
      renderAgentList();
    }
  }, 8000);
}

// ============ Agent Management ============
async function renderManageAgents() {
  await loadAgents(); await loadBackends();
  DOM['manage-agent-count'].textContent = S.agents.length;
  if (!S.agents.length) { DOM['manage-agent-table'].innerHTML = '<div class="empty">暂无 Agent，点击右上角「创建 Agent」开始</div>'; return; }
  const rows = S.agents.map(a => {
    return `<tr data-id="${esc(a.id)}">
      <td><div class="agent-cell"><span class="icon avatar-badge">${esc(getAvatar(a.id))}</span><span><strong>${esc(a.name)}</strong><br><span class="cell-sub">${esc(a.id)}</span></span></div></td>
      <td><span class="cell-meta">${esc(a.backend)}</span></td>
      <td><span class="cell-mono">${esc(a.model||'').slice(0,30)}</span></td>
      <td><span class="cell-path">${esc(a.workspace||'')}</span></td>
      <td class="cell-actions">
        <button class="btn-xs primary am-config">配置</button>
        <button class="btn-xs danger am-del">删除</button>
      </td>
    </tr>`;
  }).join('');
  DOM['manage-agent-table'].innerHTML = `<table class="manage-table"><thead><tr><th>Agent</th><th>后端</th><th>模型</th><th>工作目录</th><th class="cell-actions">操作</th></tr></thead><tbody>${rows}</tbody></table>`;
  DOM['manage-agent-table'].querySelectorAll('.am-config').forEach(btn => { btn.addEventListener('click', (e) => { const tr = e.target.closest('tr'); openManageModal(tr.dataset.id); }); });
  DOM['manage-agent-table'].querySelectorAll('.am-del').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const tr = e.target.closest('tr'); const id = tr.dataset.id;
      if (!await showConfirm(`确认删除 Agent「${id}」？将删除工作目录和配置。`, {title:'删除 Agent', okText:'删除', danger:true})) return;
      try { const r = await fetch(`/api/agents/${id}`, { method: 'DELETE' }); if (!r.ok) { const d = await r.json(); throw new Error(apiErr(d, '删除失败')); } await loadAgents(); renderManageAgents(); } catch(e) { alert('删除失败: '+e.message); }
    });
  });
}

async function renderTaskTypes() {
  const box = DOM['manage-tasktype-table']; if (!box) return;
  try {
    const r = await fetch('/api/obs/task-types');
    const items = (await r.json()).task_types || [];
    DOM['manage-tasktype-count'].textContent = items.length;
    if (!items.length) { box.innerHTML = '<div class="empty">暂无任务类型</div>'; return; }
    const kindLabel = { artifact: '文档', action: '动作证据', code_project: '代码工程' };
    box.innerHTML = `<table class="manage-table tasktype-table"><thead><tr><th>类型</th><th>产出形态</th><th>交付指引</th><th>门禁（客观）</th></tr></thead><tbody>${items.map(t => {
      const kind = kindLabel[t.outcome_kind] || t.outcome_kind;
      const guide = (t.sections || []).map(s => `<span class="chip" title="${esc(s.description || '')}">${esc(s.name)}</span>`).join(' ') || '—';
      const gate = (t.gate_checks || []).map(s => `<span class="chip chip-gate">${esc(s)}</span>`).join(' ') || '—';
      const structHint = (t.structure || []).length ? `<div class="hint tasktype-struct">${(t.structure || []).map(esc).join(' · ')}</div>` : '';
      return `<tr><td><code>${esc(t.task_type)}</code></td><td>${esc(kind)}</td><td>${guide}${structHint}</td><td>${gate}</td></tr>`;
    }).join('')}</tbody></table>`;
  } catch(e) { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
}

async function renderMemory() {
  const box = DOM['manage-memory-table']; if (!box) return;
  try {
    const r = await fetch('/api/obs/memory');
    const data = await r.json();
    const items = data.memory || [];
    DOM['manage-memory-count'].textContent = data.total ?? items.length;
    if (!items.length) { box.innerHTML = '<div class="empty">暂无知识库条目</div>'; return; }
    box.innerHTML = `<table class="manage-table"><thead><tr><th>标题</th><th>项目</th><th>标签</th><th>预览</th></tr></thead><tbody>${items.map(m => `<tr><td>${esc(m.title || '')}</td><td><code>${esc(m.project_id || '')}</code></td><td>${(m.tags || []).map(t => `<span class="chip">${esc(t)}</span>`).join(' ') || '—'}</td><td class="hint">${esc(m.preview || '')}</td></tr>`).join('')}</tbody></table>`;
  } catch(e) { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
}

function openManageModal(agentId) {
  const a = S.agents.find(x => x.id === agentId); if (!a) return;
  DOM['mm-id'].value = a.id; DOM['mm-name'].value = a.name; DOM['mm-workspace'].value = a.workspace;
  const bSel = DOM['mm-backend']; bSel.innerHTML = S.backends.map(b => `<option value="${b.id}" ${b.id === a.backend ? 'selected' : ''}>${b.name}</option>`).join('');
  updateManageModels(a.backend, a.model);
  bSel.onchange = () => updateManageModels(bSel.value);
  DOM['mm-status'].style.display = 'none'; DOM['manage-modal'].classList.remove('hidden');
}
function updateManageModels(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['mm-model']; mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.id === selected ? 'selected' : ''}>${m.name}</option>`).join('');
}
async function saveManageModal() {
  const id = DOM['mm-id'].value; const name = DOM['mm-name'].value.trim(); const backend = DOM['mm-backend'].value; const model = DOM['mm-model'].value; const workspace = DOM['mm-workspace'].value.trim(); const status = DOM['mm-status'];
  if (!name) { status.textContent = '名称不能为空'; status.className = 'form-status error'; status.style.display = 'block'; return; }
  try {
    const r = await fetch(`/api/agents/${id}/manage`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name, backend, model, workspace }) });
    if (!r.ok) throw new Error('保存失败');
    status.textContent = '✓ 已保存'; status.className = 'form-status success'; status.style.display = 'block';
    await loadAgents(); renderManageAgents();
    setTimeout(() => { DOM['manage-modal'].classList.add('hidden'); }, 800);
  } catch(e) { status.textContent = '保存失败: '+e.message; status.className = 'form-status error'; status.style.display = 'block'; }
}

// Agent Factory
function resetCreateForm() {
  DOM['cf-description'].value = ''; DOM['cf-agent-id'].value = ''; DOM['cf-name'].value = '';
  DOM['cf-result'].classList.add('hidden'); DOM['cf-result'].querySelector('.result-details').innerHTML = '';
  showFormStatus('', ''); DOM['cf-submit'].disabled = false; DOM['cf-submit'].innerHTML = ic('plus') + ' 创建 Agent';
}
async function openCreateModal() { await loadBackends(); resetCreateForm(); populateCreateForm(); DOM['create-agent-modal'].classList.remove('hidden'); }
function closeCreateModal() { DOM['create-agent-modal'].classList.add('hidden'); }
async function populateCreateForm() {
  let defBackend = 'opencode'; let defModel = '';
  try { const r = await fetch('/api/config'); const cfg = (await r.json()).config || {}; defBackend = cfg.system?.default_backend || defBackend; defModel = cfg.system?.default_model || ''; } catch (_) {}
  const bSel = DOM['cf-backend']; bSel.innerHTML = S.backends.map(b => `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`).join('');
  updateCreateModels(bSel.value, defModel); bSel.onchange = () => updateCreateModels(bSel.value);
  DOM['cf-description'].oninput = () => { const desc = DOM['cf-description'].value.trim(); if (desc.length > 5) suggestId(desc); };
}
function updateCreateModels(backendId, selected) {
  const models = getBackendModels(backendId); const mSel = DOM['cf-model'];
  mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`).join('');
}
async function suggestId(desc) {
  try { const r = await fetch(`/api/agents/suggest-id?description=${encodeURIComponent(desc)}`); const d = await r.json(); if (!DOM['cf-agent-id'].value) DOM['cf-agent-id'].value = d.suggested_id; } catch(e) {}
}
function showFormStatus(msg, type) {
  const s = DOM['cf-status']; s.textContent = msg; s.className = 'form-status';
  if (msg) { s.style.display = 'block'; if (type) s.classList.add(type); } else s.style.display = 'none';
}