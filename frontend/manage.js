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
    const unread = (S.agentMessages[a.id] || []).filter(m => m._new).length;
    const preview = agentLastPreview(a.id);
    return `<div class="sidebar-item ${S.currentAgentId === a.id ? 'active' : ''}${unread ? ' has-new' : ''}" data-id="${a.id}">
      <span class="s-icon avatar-badge">${esc(getAvatar(a.id))}</span>
      <span class="s-main">
        <span class="s-row1"><span class="s-name">${esc(a.name)}</span><span class="s-time">${esc(fmtListTime(lastTs))}</span></span>
        <span class="s-row2"><span class="s-preview">${preview ? esc(truncateText(preview, 48)) : '<span class="s-id">' + esc(a.name || a.id) + '</span>'}</span>
          ${unread ? `<span class="s-badge">${unread > 99 ? '99+' : unread}</span>` : ''}
          <span class="s-del" data-del-agent="${a.id}" title="删除对话">${ic('x')}</span>
        </span>
      </span>
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
    setTaskTypeRecords(_manageTaskTypes);
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

function manageFilterAgents(agents, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return agents;
  return agents.filter(a => {
    const meta = _manageRegistry[a.id] || {};
    const tts = (meta.task_types || []).join(' ').toLowerCase();
    const hay = [
      a.id, a.name, a.backend, a.model, a.model_override, tts,
    ].map(x => (x || '').toLowerCase()).join(' ');
    return hay.includes(q);
  });
}

function manageFilterTaskTypes(items, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return items;
  return items.filter(t => {
    const sections = (t.sections || []).map(s => `${s.name || ''} ${s.description || ''}`).join(' ');
    const gates = (t.gate_checks || []).join(' ');
    const hay = [
      t.task_type, t.display_name, t.outcome_kind, sections, gates,
    ].map(x => (x || '').toLowerCase()).join(' ');
    return hay.includes(q);
  });
}

function manageFormatOperatedAt(iso) {
  if (!iso) return '';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return '';
  return fmtListTime(ts);
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
  const query = DOM['manage-agent-search']?.value || '';
  const filtered = manageFilterAgents(S.agents, query);
  if (!S.agents.length) {
    DOM['manage-agent-table'].innerHTML = '<div class="empty">暂无 Agent，点击右上角「创建 Agent」开始</div>';
    return;
  }
  if (!filtered.length) {
    DOM['manage-agent-table'].innerHTML = '<div class="empty">无匹配 Agent</div>';
    return;
  }
  const rows = filtered.map(a => {
    const meta = _manageRegistry[a.id] || {};
    const tts = meta.task_types || [];
    const opHint = a.operated_at ? `<br><span class="cell-sub hint">最近操作 ${esc(manageFormatOperatedAt(a.operated_at))}</span>` : '';
    return `<tr data-id="${esc(a.id)}">
      <td><div class="agent-cell"><span class="icon avatar-badge">${esc(getAvatar(a.id))}</span><span><strong>${esc(a.name || a.id)}</strong><br><span class="cell-sub">${esc(a.id)}</span>${opHint}</span></div></td>
      <td class="tasktype-chips-cell">${taskTypeChips(tts)}</td>
      <td><span class="cell-meta">${esc(a.backend)}</span></td>
      <td><span class="cell-mono" title="${a.uses_settings_default ? '跟随设置默认' : '单独配置'}">${esc(a.uses_settings_default ? (a.model||'') + ' ⭐' : (a.model||'')).slice(0,36)}</span></td>
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
    box.innerHTML = '<span class="hint">暂无任务类型，请先在「管理 → 任务类型」新建。</span>';
    return;
  }
  box.innerHTML = _manageTaskTypes.map(t => {
    const id = t.task_type;
    const label = t.display_name || id;
    const checked = sel.has(id) ? 'checked' : '';
    return `<label class="tasktype-check" title="${esc(id)}"><input type="checkbox" value="${esc(id)}" ${checked}> <span>${esc(label)}</span></label>`;
  }).join('');
}

function getDtSelectedTaskTypes() {
  const sel = DOM['dt-task-types'] || document.getElementById('dt-task-types');
  if (!sel) return [];
  return [...sel.selectedOptions].map(o => o.value);
}

function renderDtTaskTypeChecks(selected) {
  const sel = DOM['dt-task-types'] || document.getElementById('dt-task-types');
  if (!sel) return;
  const picked = new Set(selected || []);
  if (!_manageTaskTypes.length) {
    sel.innerHTML = '<option value="" disabled>暂无任务类型，请先在「任务类型」中新建</option>';
    return;
  }
  sel.innerHTML = _manageTaskTypes.map(t => {
    const id = t.task_type;
    const label = t.display_name || id;
    const isOn = picked.has(id) ? 'selected' : '';
    return `<option value="${esc(id)}" title="${esc(id)}" ${isOn}>${esc(label)}</option>`;
  }).join('');
}

function syncDtDefaultForSelect(preferred) {
  const sel = DOM['dt-default-for'] || document.getElementById('dt-default-for');
  if (!sel) return;
  const selected = getDtSelectedTaskTypes();
  const prev = preferred ?? sel.value;
  sel.innerHTML = '<option value="">（不设置）</option>' + selected.map(id => {
    const label = taskTypeDisplayLabel(id, _manageTaskTypes);
    return `<option value="${esc(id)}" title="${esc(id)}">${esc(label)}</option>`;
  }).join('');
  if (prev && selected.includes(prev)) sel.value = prev;
  else sel.value = '';
}

async function renderTaskTypes() {
  const box = DOM['manage-tasktype-table']; if (!box) return;
  await loadManageMeta();
  try {
    const query = DOM['manage-tasktype-search']?.value || '';
    const items = manageFilterTaskTypes(_manageTaskTypes, query);
    DOM['manage-tasktype-count'].textContent = String(_manageTaskTypes.length);
    if (!_manageTaskTypes.length) {
      box.innerHTML = '<div class="empty">暂无任务类型，点击「新建类型」</div>';
      return;
    }
    if (!items.length) {
      box.innerHTML = '<div class="empty">无匹配任务类型</div>';
      return;
    }
    const kindLabel = {};
    _outcomeKinds.forEach(o => {
      kindLabel[o.id] = o.form_label_zh || o.label?.split(/\s+/)[0] || o.id;
    });
    box.innerHTML = `<table class="manage-table tasktype-table"><thead><tr><th>类型</th><th>产出形态</th><th>交付指引</th><th>门禁</th><th class="cell-actions">操作</th></tr></thead><tbody>${items.map(t => {
      const kind = kindLabel[t.outcome_kind] || t.outcome_kind;
      const guide = (t.sections || []).map(s => `<span class="chip" title="${esc(s.description || '')}">${esc(s.name)}</span>`).join(' ') || '—';
      const gate = (t.gate_checks || []).map(s => `<span class="chip chip-gate">${esc(s)}</span>`).join(' ') || '—';
      const label = esc(t.display_name || t.task_type);
      const opHint = t.operated_at
        ? `<br><span class="cell-sub hint">最近操作 ${esc(manageFormatOperatedAt(t.operated_at))}</span>`
        : '';
      return `<tr data-tt="${esc(t.task_type)}" title="${esc(t.task_type)}"><td><strong>${label}</strong>${opHint}</td><td>${esc(kind)}</td><td>${guide}</td><td>${gate}</td><td class="cell-actions"><button class="btn-xs primary tt-edit">编辑</button><button class="btn-xs danger tt-del">删除</button></td></tr>`;
    }).join('')}</tbody></table>`;
    box.querySelectorAll('.tt-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.target.closest('tr').dataset.tt;
        const row = _manageTaskTypes.find(x => x.task_type === id);
        openTaskTypeModal(row);
      });
    });
    box.querySelectorAll('.tt-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.closest('tr').dataset.tt;
        const ttLabel = taskTypeDisplayLabel(id, _manageTaskTypes);
        if (!await showConfirm(`删除任务类型「${ttLabel}」？已被 Agent 引用时将无法删除。`, {title:'删除任务类型', okText:'删除', danger:true})) return;
        try {
          const r = await fetch(`/api/task-types/${encodeURIComponent(id)}`, { method: 'DELETE' });
          const d = await r.json();
          if (!r.ok) throw new Error(apiErr(d, '删除失败'));
          invalidateTaskTypeRecords();
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
    invalidateTaskTypeRecords();
    await renderTaskTypes(); await renderManageAgents();
    if (window.refreshWorkflowSelect) window.refreshWorkflowSelect();
  } catch (e) {
    status.textContent = e.message || '保存失败';
    status.className = 'form-status error';
    status.style.display = 'block';
  }
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
  updateManageModels(a.backend, a.model_override || a.model, a.uses_settings_default);
  bSel.onchange = () => updateManageModels(bSel.value, '', false);
  DOM['mm-status'].style.display = 'none'; DOM['manage-modal'].classList.remove('hidden');
}
function updateManageModels(backendId, selected, usesDefault) {
  const models = getBackendModels(backendId);
  const mSel = DOM['mm-model'];
  const opts = models.map(m => `<option value="${m.id}" ${m.id === selected ? 'selected' : ''}>${m.name}</option>`).join('');
  const hint = usesDefault ? '<option value="" selected>（跟随设置默认）</option>' : '';
  mSel.innerHTML = hint + opts;
  if (usesDefault && !selected) mSel.value = '';
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

// ============ Manage sub-tabs ============
let _manageMtab = 'agents';

function switchManageTab(mtab, opts = {}) {
  _manageMtab = mtab || 'agents';
  document.querySelectorAll('.manage-subnav .mtab').forEach(b => {
    b.classList.toggle('active', b.dataset.mtab === _manageMtab);
  });
  document.querySelectorAll('.mtab-panel').forEach(p => {
    p.classList.toggle('active', p.dataset.mtab === _manageMtab);
  });
  if (_manageMtab === 'agents') renderManageAgents();
  else if (_manageMtab === 'tasktypes') renderTaskTypes();
  else if (_manageMtab === 'templates') renderDeliveryTemplates();
  else if (_manageMtab === 'knowledge') loadKnowledgeTab();
  if (!opts.restore && typeof saveUiState === 'function') saveUiState();
}

function loadManageTab(mtab) {
  const valid = ['agents', 'tasktypes', 'templates', 'knowledge'];
  if (mtab && valid.includes(mtab)) _manageMtab = mtab;
  switchManageTab(_manageMtab, { restore: true });
}

function setupManageSubnav() {
  document.querySelectorAll('.manage-subnav .mtab').forEach(btn => {
    if (btn.dataset.mtabBound) return;
    btn.dataset.mtabBound = '1';
    btn.addEventListener('click', () => switchManageTab(btn.dataset.mtab));
  });
}

function setupManagePanelActions() {
  const panel = document.getElementById('tab-manage');
  if (!panel || panel.dataset.manageBound) return;
  panel.dataset.manageBound = '1';
  panel.addEventListener('click', (e) => {
    if (e.target.closest('#btn-new-dt')) {
      e.preventDefault();
      openDtModal(null);
      return;
    }
    if (e.target.closest('#btn-new-tasktype')) {
      e.preventDefault();
      openTaskTypeModal(null);
    }
  });
}

// ============ Delivery Templates ============
let _deliveryTemplates = [];

function manageFilterDeliveryTemplates(items, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return items;
  return items.filter(t => {
    const tts = (t.task_types || []).join(' ');
    const hay = [t.id, t.display_name, t.description, tts, t.default_for]
      .map(x => (x || '').toLowerCase()).join(' ');
    return hay.includes(q);
  });
}

async function loadDeliveryTemplates() {
  try {
    const r = await fetch('/api/delivery-templates');
    const d = await r.json();
    _deliveryTemplates = d.templates || [];
  } catch (_) {
    _deliveryTemplates = [];
  }
  return _deliveryTemplates;
}

async function renderDeliveryTemplates() {
  const box = DOM['manage-dt-table'];
  if (!box) return;
  await loadManageMeta();
  await loadDeliveryTemplates();
  const query = DOM['manage-dt-search']?.value || '';
  const items = manageFilterDeliveryTemplates(_deliveryTemplates, query);
  if (DOM['manage-dt-count']) DOM['manage-dt-count'].textContent = String(_deliveryTemplates.length);
  if (!_deliveryTemplates.length) {
    box.innerHTML = '<div class="empty">暂无交付模板，点击「新建模板」或导入模板文件</div>';
    return;
  }
  if (!items.length) {
    box.innerHTML = '<div class="empty">无匹配模板</div>';
    return;
  }
  box.innerHTML = `<table class="manage-table"><thead><tr><th>模板</th><th>绑定任务类型</th><th>章节</th><th>默认类型</th><th>流程引用</th><th class="cell-actions">操作</th></tr></thead><tbody>${items.map(t => {
    const tts = (t.task_types || []).map(x => {
      const label = taskTypeDisplayLabel(x, _manageTaskTypes);
      return `<span class="chip">${esc(label)}</span>`;
    }).join(' ') || '<span class="hint">未绑定</span>';
    const secs = (t.sections || []).slice(0, 5).map(s => `<span class="chip">${esc(s)}</span>`).join(' ');
    const more = (t.section_count || 0) > 5 ? `<span class="hint">+${t.section_count - 5}</span>` : '';
    const opHint = t.operated_at ? `<br><span class="cell-sub hint">最近操作 ${esc(manageFormatOperatedAt(t.operated_at))}</span>` : '';
    const refs = t.used_by_workflows || [];
    const refCell = refs.length
      ? refs.map(w => `<span class="chip chip-warn">${esc(w)}</span>`).join(' ')
      : '<span class="hint">—</span>';
    const canDel = t.can_delete !== false;
    const delTitle = canDel ? '删除模板' : `被流程引用（${refs.join('、')}），请先在流程里取消绑定`;
    return `<tr data-dt="${esc(t.id)}"><td><strong>${esc(t.display_name || t.id)}</strong><br><code class="cell-sub">${esc(t.id)}</code>${opHint}</td><td>${tts}</td><td>${secs}${more}</td><td>${t.default_for ? `<span class="chip">${esc(taskTypeDisplayLabel(t.default_for, _manageTaskTypes))}</span>` : '—'}</td><td>${refCell}</td><td class="cell-actions"><button class="btn-xs primary dt-edit">编辑</button><button class="btn-xs danger dt-del"${canDel ? '' : ' disabled'} title="${esc(delTitle)}">删除</button></td></tr>`;
  }).join('')}</tbody></table>`;
  box.querySelectorAll('.dt-edit').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const id = e.target.closest('tr').dataset.dt;
      openDtModal(_deliveryTemplates.find(x => x.id === id));
    });
  });
  box.querySelectorAll('.dt-del').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      if (btn.disabled) return;
      const id = e.target.closest('tr').dataset.dt;
      const rec = _deliveryTemplates.find(x => x.id === id);
      const refs = rec?.used_by_workflows || [];
      if (refs.length || rec?.can_delete === false) {
        alert(`无法删除：模板「${id}」仍被流程引用：${refs.join('、')}。\n请先在「流程」里取消各任务的交付模板绑定后再删。`);
        return;
      }
      if (!await showConfirm(`删除交付模板「${id}」？此操作不可恢复。`, { title: '删除模板', okText: '删除', danger: true })) return;
      try {
        const r = await fetch(`/api/delivery-templates/${encodeURIComponent(id)}`, { method: 'DELETE' });
        const d = await r.json();
        if (!r.ok) throw new Error(apiErr(d, '删除失败'));
        await renderDeliveryTemplates();
        if (typeof window.refreshWorkflowSelect === 'function') window.refreshWorkflowSelect();
      } catch (err) { alert('删除失败：' + (err.message || err)); }
    });
  });
}

async function openDtModal(row) {
  const modal = DOM['dt-modal'] || document.getElementById('dt-modal');
  if (!modal) {
    showToast('模板弹窗未就绪，请硬刷新页面', 'error');
    return;
  }
  await loadManageMeta();
  const isNew = !row;
  const set = (key, elId, fn) => {
    const el = DOM[key] || document.getElementById(elId);
    if (el && typeof fn === 'function') fn(el);
    return el;
  };
  set('dt-modal-title', 'dt-modal-title', el => { el.textContent = isNew ? '新建交付模板' : '编辑交付模板'; });
  set('dt-id', 'dt-id', el => {
    el.value = row?.id || '';
    el.readOnly = !isNew;
  });
  set('dt-display-name', 'dt-display-name', el => { el.value = row?.display_name || ''; });
  set('dt-description', 'dt-description', el => { el.value = row?.description || ''; });
  renderDtTaskTypeChecks(row?.task_types || []);
  syncDtDefaultForSelect(row?.default_for || '');
  set('dt-sections', 'dt-sections', el => { el.value = (row?.sections || []).join(', '); });
  set('dt-yaml', 'dt-yaml', el => { el.value = ''; });
  set('dt-status', 'dt-status', el => { el.style.display = 'none'; });
  modal.querySelector('.dt-yaml-details')?.removeAttribute('open');
  modal.classList.remove('hidden');
  modal.dataset.mode = isNew ? 'create' : 'edit';
  hydrateIcons(modal);
  if (!isNew && row?.id) {
    try {
      const r = await fetch(`/api/delivery-templates/${encodeURIComponent(row.id)}`);
      const d = await r.json();
      if (r.ok && d.yaml) {
        const ta = DOM['dt-yaml'] || document.getElementById('dt-yaml');
        if (ta) ta.value = d.yaml;
        modal.querySelector('.dt-yaml-details')?.setAttribute('open', '');
      }
      if (r.ok && d.template) {
        renderDtTaskTypeChecks(d.template.task_types || row?.task_types || []);
        syncDtDefaultForSelect(d.template.default_for || row?.default_for || '');
      }
    } catch (_) { /* ignore */ }
  }
}

function closeDtModal() { DOM['dt-modal']?.classList.add('hidden'); }

async function saveDtModal() {
  const mode = DOM['dt-modal']?.dataset.mode || 'create';
  const id = DOM['dt-id'].value.trim();
  const status = DOM['dt-status'];
  if (!id) {
    status.textContent = '模板 ID 不能为空';
    status.className = 'form-status error';
    status.style.display = 'block';
    return;
  }
  const taskTypes = getDtSelectedTaskTypes();
  if (!taskTypes.length) {
    status.textContent = '请至少绑定一个任务类型';
    status.className = 'form-status error';
    status.style.display = 'block';
    return;
  }
  const body = {
    id,
    display_name: DOM['dt-display-name'].value.trim() || id,
    description: DOM['dt-description'].value.trim(),
    task_types: taskTypes,
    default_for: DOM['dt-default-for'].value.trim(),
    required_sections: DOM['dt-sections'].value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    yaml: DOM['dt-yaml'].value.trim(),
  };
  const url = mode === 'create' ? '/api/delivery-templates' : `/api/delivery-templates/${encodeURIComponent(id)}`;
  const method = mode === 'create' ? 'POST' : 'PUT';
  try {
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '保存失败'));
    closeDtModal();
    await renderDeliveryTemplates();
    if (typeof window.refreshWorkflowSelect === 'function') window.refreshWorkflowSelect();
  } catch (e) {
    status.textContent = e.message || '保存失败';
    status.className = 'form-status error';
    status.style.display = 'block';
  }
}

async function handleDtUpload(file) {
  if (!file) return;
  try {
    const text = await file.text();
    const r = await fetch('/api/delivery-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml: text }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '上传失败'));
    showToast('模板已导入', 'success');
    await renderDeliveryTemplates();
    if (typeof window.refreshWorkflowSelect === 'function') window.refreshWorkflowSelect();
  } catch (e) {
    showToast('上传失败: ' + e.message, 'error');
  }
}

function setupDtModal() {
  const sel = DOM['dt-task-types'] || document.getElementById('dt-task-types');
  if (!sel || sel.dataset.dtBound) return;
  sel.dataset.dtBound = '1';
  sel.addEventListener('change', () => syncDtDefaultForSelect());
}

setupManageSubnav();
setupManagePanelActions();
setupDtModal();
