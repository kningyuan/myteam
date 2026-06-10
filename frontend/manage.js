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
let _manageRegistry = {};
let _manageTaskTypes = [];
let _outcomeKinds = [];

async function loadManageMeta() {
  try {
    const [rr, rt] = await Promise.all([
      fetch('/api/agents/registry'),
      fetch('/api/task-types'),
    ]);
    const reg = await rr.json();
    _manageRegistry = reg.agents || {};
    _manageTaskTypes = (await rt.json()).task_types || [];
  } catch (_) {
    _manageRegistry = {};
    _manageTaskTypes = [];
  }
}

function taskTypeChips(taskTypes) {
  const tts = taskTypes || [];
  if (!tts.length) return '<span class="chip chip-warn">未配置任务类型</span>';
  return tts.map(t => {
    const label = taskTypeDisplayLabel(t, _manageTaskTypes);
    return `<span class="chip" title="${esc(t)}">${esc(label)}</span>`;
  }).join(' ');
}

async function syncMissingTaskTypes() {
  try {
    const r = await fetch('/api/agents/sync-task-types', { method: 'POST' });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '补全失败'));
    const n = d.count || 0;
    showToast(n ? `已为 ${n} 个 Agent 补全任务类型` : '所有 Agent 均已配置任务类型', 'success');
    await renderManageAgents();
    return d;
  } catch (e) {
    showToast('补全失败: ' + e.message, 'error');
    throw e;
  }
}

let _manageTaskTypesSynced = false;

async function renderManageAgents() {
  await loadAgents(); await loadBackends(); await loadManageMeta();
  const missingTts = S.agents.filter(a => !(_manageRegistry[a.id]?.task_types || []).length);
  if (missingTts.length && !_manageTaskTypesSynced) {
    _manageTaskTypesSynced = true;
    try {
      await syncMissingTaskTypes();
      return;
    } catch (_) { /* 仍渲染列表，便于手动补全 */ }
  }
  DOM['manage-agent-count'].textContent = S.agents.length;
  if (!S.agents.length) { DOM['manage-agent-table'].innerHTML = '<div class="empty">暂无 Agent，点击右上角「创建 Agent」开始</div>'; return; }
  const rows = S.agents.map(a => {
    const meta = _manageRegistry[a.id] || {};
    const tts = meta.task_types || [];
    return `<tr data-id="${esc(a.id)}">
      <td><div class="agent-cell"><span class="icon avatar-badge">${esc(getAvatar(a.id))}</span><span><strong>${esc(a.name || a.id)}</strong><br><span class="cell-sub">${esc(a.id)}</span></span></div></td>
      <td class="tasktype-chips-cell">${taskTypeChips(tts)}</td>
      <td><span class="cell-meta">${esc(a.backend)}</span></td>
      <td><span class="cell-mono">${esc(a.model||'').slice(0,30)}</span></td>
      <td class="cell-actions">
        <button class="btn-xs primary am-config">配置</button>
        <button class="btn-xs danger am-del">删除</button>
      </td>
    </tr>`;
  }).join('');
  DOM['manage-agent-table'].innerHTML = `<table class="manage-table"><thead><tr><th>Agent</th><th>可执行任务类型</th><th>后端</th><th>模型</th><th class="cell-actions">操作</th></tr></thead><tbody>${rows}</tbody></table>`;
  DOM['manage-agent-table'].querySelectorAll('.am-config').forEach(btn => { btn.addEventListener('click', (e) => { const tr = e.target.closest('tr'); openManageModal(tr.dataset.id); }); });
  DOM['manage-agent-table'].querySelectorAll('.am-del').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const tr = e.target.closest('tr'); const id = tr.dataset.id;
      if (!await showConfirm(`确认删除 Agent「${id}」？将删除工作目录和配置。`, {title:'删除 Agent', okText:'删除', danger:true})) return;
      try { const r = await fetch(`/api/agents/${id}`, { method: 'DELETE' }); if (!r.ok) { const d = await r.json(); throw new Error(apiErr(d, '删除失败')); } await loadAgents(); renderManageAgents(); } catch(e) { alert('删除失败: '+e.message); }
    });
  });
}

function renderMmTaskTypeChecks(selected) {
  const box = DOM['mm-task-types'];
  if (!box) return;
  const sel = new Set(selected || []);
  if (!_manageTaskTypes.length) {
    box.innerHTML = '<span class="hint">暂无任务类型，请先在下方新建。</span>';
    return;
  }
  box.innerHTML = _manageTaskTypes.map(t => {
    const id = t.task_type;
    const label = t.display_name || id;
    const checked = sel.has(id) ? 'checked' : '';
    return `<label class="tasktype-check"><input type="checkbox" value="${esc(id)}" ${checked}> <span>${esc(label)}</span> <code class="cell-sub">${esc(id)}</code></label>`;
  }).join('');
}

async function renderTaskTypes() {
  const box = DOM['manage-tasktype-table']; if (!box) return;
  await loadManageMeta();
  try {
    const items = _manageTaskTypes;
    DOM['manage-tasktype-count'].textContent = items.length;
    if (!items.length) { box.innerHTML = '<div class="empty">暂无任务类型，点击「新建类型」</div>'; return; }
    const kindLabel = { artifact: '文档', action: '动作证据', code_project: '代码工程' };
    box.innerHTML = `<table class="manage-table tasktype-table"><thead><tr><th>类型</th><th>产出形态</th><th>交付指引</th><th>门禁</th><th class="cell-actions">操作</th></tr></thead><tbody>${items.map(t => {
      const kind = kindLabel[t.outcome_kind] || t.outcome_kind;
      const guide = (t.sections || []).map(s => `<span class="chip" title="${esc(s.description || '')}">${esc(s.name)}</span>`).join(' ') || '—';
      const gate = (t.gate_checks || []).map(s => `<span class="chip chip-gate">${esc(s)}</span>`).join(' ') || '—';
      const label = esc(t.display_name || t.task_type);
      const key = t.display_name && t.display_name !== t.task_type
        ? `<br><code class="cell-sub">${esc(t.task_type)}</code>` : '';
      return `<tr data-tt="${esc(t.task_type)}"><td><strong>${label}</strong>${key}</td><td>${esc(kind)}</td><td>${guide}</td><td>${gate}</td><td class="cell-actions"><button class="btn-xs primary tt-edit">编辑</button><button class="btn-xs danger tt-del">删除</button></td></tr>`;
    }).join('')}</tbody></table>`;
    box.querySelectorAll('.tt-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.target.closest('tr').dataset.tt;
        const row = items.find(x => x.task_type === id);
        openTaskTypeModal(row);
      });
    });
    box.querySelectorAll('.tt-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.closest('tr').dataset.tt;
        if (!await showConfirm(`删除任务类型「${id}」？已被 Agent 引用时将无法删除。`, {title:'删除任务类型', okText:'删除', danger:true})) return;
        try {
          const r = await fetch(`/api/task-types/${encodeURIComponent(id)}`, { method: 'DELETE' });
          const d = await r.json();
          if (!r.ok) throw new Error(apiErr(d, '删除失败'));
          await renderTaskTypes(); await renderManageAgents();
          if (window.refreshWorkflowSelect) window.refreshWorkflowSelect();
        } catch (err) { alert('删除失败：' + (err.message || err)); }
      });
    });
  } catch(e) { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
}

async function loadOutcomeKinds() {
  if (_outcomeKinds.length) return;
  try {
    const r = await fetch('/api/task-types/outcome-kinds');
    const d = await r.json();
    _outcomeKinds = d.outcome_kinds || [];
  } catch (_) {
    _outcomeKinds = [
      { id: 'artifact', label: '文档报告 artifact', summary: 'Markdown 结构化交付物', covers: [] },
      { id: 'action', label: '动作证据 action', summary: 'URL + 截图等外部动作证据', covers: [] },
      { id: 'code_project', label: '代码工程 code_project', summary: '可运行代码目录交付', covers: [] },
    ];
  }
}

function renderOutcomeSelect(selected) {
  const sel = DOM['tt-outcome'];
  if (!sel) return;
  sel.innerHTML = _outcomeKinds.map(o => {
    const covers = (o.covers || []).slice(0, 4).join('；');
    const title = [o.summary, covers ? `覆盖：${covers}` : '', (o.examples || []).length ? `示例：${o.examples.join(', ')}` : ''].filter(Boolean).join('\n');
    return `<option value="${esc(o.id)}" title="${esc(title)}">${esc(o.label)}</option>`;
  }).join('');
  sel.value = selected || 'artifact';
  updateOutcomeHint();
}

function updateOutcomeHint() {
  const hint = DOM['tt-outcome-hint'];
  const sel = DOM['tt-outcome'];
  if (!hint || !sel) return;
  const o = _outcomeKinds.find(x => x.id === sel.value);
  if (!o) { hint.textContent = ''; return; }
  const covers = (o.covers || []).join(' · ');
  hint.textContent = [o.summary, covers ? `常见：${covers}` : ''].filter(Boolean).join(' — ');
}

async function suggestTaskTypeFromDesc() {
  const desc = DOM['tt-description']?.value.trim();
  const status = DOM['tt-status'];
  if (!desc) {
    status.textContent = '请先填写任务描述';
    status.className = 'form-status error';
    status.style.display = 'block';
    return;
  }
  status.style.display = 'none';
  try {
    const r = await fetch('/api/task-types/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '推导失败'));
    if (DOM['tasktype-modal']?.dataset.mode === 'create') {
      DOM['tt-id'].value = d.task_type || '';
    }
    DOM['tt-display-name'].value = d.display_name || '';
    if (d.outcome_catalog?.length) _outcomeKinds = d.outcome_catalog;
    renderOutcomeSelect(d.outcome_kind || 'artifact');
    DOM['tt-sections'].value = (d.required_sections || []).join(', ');
    status.textContent = `已推导（${d.pattern || 'rules'}）— 字段可继续编辑`;
    status.className = 'form-status success';
    status.style.display = 'block';
  } catch (e) {
    status.textContent = e.message || '推导失败';
    status.className = 'form-status error';
    status.style.display = 'block';
  }
}

async function openTaskTypeModal(row) {
  const isNew = !row;
  await loadOutcomeKinds();
  DOM['tt-modal-title'].textContent = isNew ? '新建任务类型' : '编辑任务类型';
  DOM['tt-description'].value = isNew ? '' : (row?.display_name || row?.task_type || '');
  DOM['tt-id'].value = row?.task_type || '';
  DOM['tt-id'].readOnly = !isNew;
  DOM['tt-display-name'].value = row?.display_name || '';
  renderOutcomeSelect(row?.outcome_kind || 'artifact');
  DOM['tt-sections'].value = (row?.required_sections || []).join(', ');
  DOM['tt-status'].style.display = 'none';
  DOM['tasktype-modal'].classList.remove('hidden');
  DOM['tasktype-modal'].dataset.mode = isNew ? 'create' : 'edit';
}

function closeTaskTypeModal() { DOM['tasktype-modal']?.classList.add('hidden'); }

async function saveTaskTypeModal() {
  const mode = DOM['tasktype-modal']?.dataset.mode || 'create';
  const taskType = DOM['tt-id'].value.trim();
  const displayName = DOM['tt-display-name'].value.trim();
  const outcome = DOM['tt-outcome'].value;
  const sections = DOM['tt-sections'].value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  const status = DOM['tt-status'];
  if (!taskType) { status.textContent = '类型 ID 不能为空'; status.className = 'form-status error'; status.style.display = 'block'; return; }
  const body = { display_name: displayName || taskType, outcome_kind: outcome, required_sections: sections.length ? sections : ['正文'] };
  try {
    const url = mode === 'create' ? '/api/task-types' : `/api/task-types/${encodeURIComponent(taskType)}`;
    const method = mode === 'create' ? 'POST' : 'PUT';
    const payload = mode === 'create' ? { task_type: taskType, ...body } : body;
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '保存失败'));
    closeTaskTypeModal();
    await renderTaskTypes(); await renderManageAgents();
    if (window.refreshWorkflowSelect) window.refreshWorkflowSelect();
  } catch (e) {
    status.textContent = e.message || '保存失败';
    status.className = 'form-status error';
    status.style.display = 'block';
  }
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

async function suggestManageTaskTypes() {
  const id = DOM['mm-id']?.value;
  const meta = _manageRegistry[id] || {};
  const desc = meta.description || '';
  const name = DOM['mm-name']?.value?.trim() || meta.name || id;
  if (!desc && !name) {
    DOM['mm-status'].textContent = '请先在注册表中填写 Agent 描述，或创建时写入职责说明';
    DOM['mm-status'].className = 'form-status error';
    DOM['mm-status'].style.display = 'block';
    return;
  }
  try {
    const r = await fetch('/api/agents/suggest-task-types', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc || name, name, agent_id: id }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '推导失败'));
    renderMmTaskTypeChecks(d.task_types || []);
    DOM['mm-status'].textContent = `✓ 已勾选 ${(d.task_types || []).length} 项（请确认后保存）`;
    DOM['mm-status'].className = 'form-status success';
    DOM['mm-status'].style.display = 'block';
  } catch (e) {
    DOM['mm-status'].textContent = e.message;
    DOM['mm-status'].className = 'form-status error';
    DOM['mm-status'].style.display = 'block';
  }
}

function openManageModal(agentId) {
  const a = S.agents.find(x => x.id === agentId); if (!a) return;
  const meta = _manageRegistry[agentId] || {};
  DOM['mm-id'].value = a.id; DOM['mm-name'].value = a.name; DOM['mm-workspace'].value = a.workspace;
  renderMmTaskTypeChecks(meta.task_types || []);
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
  const taskTypes = [...(DOM['mm-task-types']?.querySelectorAll('input[type=checkbox]:checked') || [])].map(el => el.value);
  if (!name) { status.textContent = '显示名称不能为空'; status.className = 'form-status error'; status.style.display = 'block'; return; }
  try {
    const r = await fetch(`/api/agents/${id}/manage`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name, backend, model, workspace, task_types: taskTypes }) });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '保存失败'));
    status.textContent = '✓ 已保存'; status.className = 'form-status success'; status.style.display = 'block';
    await loadAgents(); await renderManageAgents();
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
