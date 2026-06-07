// ============ Entry Point ============

// ============ Backends ============
async function loadBackends() {
  try {
    const r = await fetch('/api/backends');
    const d = await r.json();
    S.backends = d.backends || [];
    S.backends.forEach(b => {
      S.backendsCache[b.id] = b;
      b.models.forEach(m => S.backendsCache[m.id] = b);
    });
  } catch(e) { console.error('backends:', e); }
}

function getBackendModels(backendId) {
  const b = S.backendsCache[backendId] || S.backends.find(x => x.id === backendId);
  return b ? b.models : [];
}

// ============ Agents ============
async function loadAgents() {
  try {
    const r = await fetch('/api/agents');
    const d = await r.json();
    S.agents = d.agents || [];
    DOM['agent-count'].textContent = S.agents.length;
  } catch(e) { console.error('agents:', e); }
}

// ============ Tab System ============
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
}

function switchTab(tab, opts = {}) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.toggle('active', t.id === `tab-${tab}`));

  const showSidebar = (tab === 'chat' || tab === 'groups' || tab === 'projects');
  document.getElementById('sidebar').style.display = showSidebar ? 'flex' : 'none';
  document.querySelectorAll('.sidebar-panel').forEach(p => p.classList.toggle('active',
    (tab === 'chat' && p.id === 'sidebar-agents') ||
    (tab === 'groups' && p.id === 'sidebar-groups') ||
    (tab === 'projects' && p.id === 'sidebar-projects')
  ));

  if (tab === 'home') renderDashboard();
  if (tab === 'chat') renderAgentList();
  if (tab === 'groups') { renderGroupList(); loadGroups(); }
  if (tab === 'projects') { renderProjectList(); loadProjects().then(renderProjectList); }
  if (tab === 'agents') { renderManageAgents(); renderTaskTypes(); renderMemory(); }
  if (tab === 'settings') loadSettings();
  if (tab !== 'groups') disconnectGroupEvents();
  if (tab !== 'chat') disconnectAgentEvents();
  if (tab === 'chat' && S.currentAgentId) connectAgentEvents(S.currentAgentId);
  if (!opts.restore) saveUiState();
}

function saveUiState() {
  try {
    const tab = document.querySelector('.nav-tab.active')?.dataset.tab || 'chat';
    const projectPtab = document.querySelector('.project-subnav .ptab.active')?.dataset.ptab || 'overview';
    localStorage.setItem(UI_STATE_KEY, JSON.stringify({
      tab, agentId: S.currentAgentId, groupId: S.currentGroupId,
      projectId: S.currentProjectId, projectPtab,
    }));
  } catch (e) { /* ignore */ }
}

async function restoreUiState() {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY);
    if (!raw) return;
    const st = JSON.parse(raw);
    if (st.tab) switchTab(st.tab, { restore: true });
    if (st.tab === 'chat' && st.agentId && S.agents.some(a => a.id === st.agentId && !S.hiddenAgents.has(a.id))) {
      selectAgent(st.agentId, { restore: true });
    } else if (st.tab === 'groups' && st.groupId && S.groups.some(g => g.id === st.groupId && g.status !== 'dissolved')) {
      selectGroup(st.groupId, { restore: true });
    } else if (st.tab === 'projects' && st.projectId && S.projects.some(p => p.id === st.projectId)) {
      selectProject(st.projectId, { restore: true, ptab: st.projectPtab || 'overview' });
    }
  } catch (e) { console.warn('restoreUiState:', e); }
}

// ============ Init ============
async function init() {
  cacheDom();
  hydrateIcons(document);
  loadChatHistory();
  loadTheme();
  await loadHiddenChats();
  setupTabs();
  setupThemeMenu();
  setupEventListeners();
  await Promise.all([loadAgents(), loadBackends(), loadGroups(), loadProjects()]);
  renderAgentList(); renderGroupList(); renderProjectList();
  setStatus('online');
  await restoreUiState();
  if (document.querySelector('.nav-tab.active')?.dataset.tab === 'home') renderDashboard();
  startSidebarPoll();
}

// ============ Event Listeners ============
function setupEventListeners() {
  DOM['btn-send'].addEventListener('click', () => {
    if (S.isStreaming) cancelActiveStream(); else sendAgentMsg();
  });
  DOM['message-input'].addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (S.isStreaming) cancelActiveStream(); else sendAgentMsg(); }
  });
  DOM['message-input'].addEventListener('input', () => {
    DOM['message-input'].style.height = 'auto';
    DOM['message-input'].style.height = Math.min(DOM['message-input'].scrollHeight, 120) + 'px';
    updateSendBtn();
  });
  DOM['btn-clear-chat'].addEventListener('click', () => { DOM['chat-more-dropdown']?.classList.add('hidden'); clearChat(); });
  DOM['btn-delete-chat']?.addEventListener('click', () => { DOM['chat-more-dropdown']?.classList.add('hidden'); deleteChatWindow(); });
  DOM['btn-chat-more']?.addEventListener('click', e => {
    e.stopPropagation();
    const dd = DOM['chat-more-dropdown']; if (!dd) return;
    if (dd.classList.contains('hidden')) {
      const rect = e.currentTarget.getBoundingClientRect();
      dd.style.right = (window.innerWidth - rect.right) + 'px'; dd.style.top = (rect.bottom + 6) + 'px';
      dd.classList.remove('hidden');
    } else { dd.classList.add('hidden'); }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.more-menu')) DOM['chat-more-dropdown']?.classList.add('hidden'); });
  DOM['btn-agent-config'].addEventListener('click', openAgentConfig);
  DOM['agent-search']?.addEventListener('input', e => searchChatArchives(e.target.value));
  DOM['agent-search']?.addEventListener('blur', () => setTimeout(() => hideSearchResults('agent'), 200));

  DOM['btn-group-send'].addEventListener('click', () => { if (S.isStreaming) cancelActiveStream(); else sendGroupMsg(); });
  DOM['group-input'].addEventListener('keydown', e => {
    if (S.mentionActive) {
      const dd = DOM['mention-dropdown']; const items = dd ? dd.querySelectorAll('.mention-item') : [];
      if (e.key === 'ArrowDown') { e.preventDefault(); S.mentionIdx = Math.min(S.mentionIdx + 1, items.length - 1); items.forEach((el, i) => el.classList.toggle('active', i === S.mentionIdx)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); S.mentionIdx = Math.max(S.mentionIdx - 1, 0); items.forEach((el, i) => el.classList.toggle('active', i === S.mentionIdx)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); if (items[S.mentionIdx]) insertMention(items[S.mentionIdx].dataset.id); return; }
      if (e.key === 'Escape') { hideMentionDropdown(); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendGroupMsg(); }
  });
  DOM['group-input'].addEventListener('input', () => {
    DOM['group-input'].style.height = 'auto'; DOM['group-input'].style.height = Math.min(DOM['group-input'].scrollHeight, 120) + 'px';
    updateGroupSendBtn();
    const val = DOM['group-input'].value; const pos = DOM['group-input'].selectionStart; const beforeCursor = val.slice(0, pos);
    const atIdx = beforeCursor.lastIndexOf('@');
    if (atIdx >= 0 && (atIdx === 0 || beforeCursor[atIdx - 1] === ' ' || beforeCursor[atIdx - 1] === '\n')) {
      const filter = beforeCursor.slice(atIdx + 1);
      if (!filter.includes(' ')) showMentionDropdown(filter); else hideMentionDropdown();
    } else { hideMentionDropdown(); }
  });
  DOM['btn-clear-group'].addEventListener('click', () => { DOM['group-more-dropdown']?.classList.add('hidden'); clearGroupChat(); });
  DOM['btn-dissolve-group']?.addEventListener('click', () => { DOM['group-more-dropdown']?.classList.add('hidden'); dissolveGroupWindow(); });
  DOM['btn-group-more']?.addEventListener('click', e => {
    e.stopPropagation(); const dd = DOM['group-more-dropdown']; if (!dd) return;
    if (dd.classList.contains('hidden')) { const rect = e.currentTarget.getBoundingClientRect(); dd.style.right = (window.innerWidth - rect.right) + 'px'; dd.style.top = (rect.bottom + 6) + 'px'; dd.classList.remove('hidden'); } else { dd.classList.add('hidden'); }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.more-menu')) DOM['group-more-dropdown']?.classList.add('hidden'); });
  DOM['btn-group-config'].addEventListener('click', openGroupConfig);
  DOM['group-search']?.addEventListener('input', e => searchGroupsArchive(e.target.value));
  DOM['group-search']?.addEventListener('blur', () => setTimeout(() => hideSearchResults('group'), 200));

  DOM['modal-save'].addEventListener('click', saveAgentConfig);
  DOM['modal-cancel'].addEventListener('click', () => DOM['modal-overlay'].classList.add('hidden'));
  DOM['modal-overlay'].querySelector('.modal-close')?.addEventListener('click', () => DOM['modal-overlay'].classList.add('hidden'));

  DOM['btn-add-member']?.addEventListener('click', async () => {
    const sel = DOM['group-add-agent']; if (!sel || !S.currentGroupId) return;
    const selected = Array.from(sel.selectedOptions).map(o => o.value);
    if (!selected.length) return;
    for (const agentId of selected) { await fetch(`/api/groups/${S.currentGroupId}/members`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ agent_id: agentId }) }); }
    openGroupConfig(); loadGroups(); renderGroupList();
  });
  DOM['group-modal-close']?.addEventListener('click', () => DOM['group-config-modal'].classList.add('hidden'));
  DOM['group-config-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['group-config-modal'].classList.add('hidden'));

  DOM['btn-new-group']?.addEventListener('click', () => DOM['new-group-modal'].classList.remove('hidden'));
  DOM['ng-submit']?.addEventListener('click', async () => {
    const name = DOM['ng-name'].value.trim(); if (!name) return;
    await fetch('/api/groups', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name, description: DOM['ng-desc'].value.trim() }) });
    DOM['new-group-modal'].classList.add('hidden'); DOM['ng-name'].value = ''; DOM['ng-desc'].value = '';
    await loadGroups(); renderGroupList(); switchTab('groups');
  });
  DOM['ng-cancel']?.addEventListener('click', () => DOM['new-group-modal'].classList.add('hidden'));
  DOM['new-group-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['new-group-modal'].classList.add('hidden'));

  const openNewProject = async () => { DOM['new-project-modal'].classList.remove('hidden'); DOM['np-goal']?.focus(); if (DOM['np-review']) DOM['np-review'].checked = !!(await getSysConfig()).default_review; };
  const closeNewProject = () => DOM['new-project-modal'].classList.add('hidden');
  document.querySelectorAll('.project-subnav .ptab').forEach(b => b.addEventListener('click', () => switchProjectTab(b.dataset.ptab)));
  DOM['btn-deliverable-copy']?.addEventListener('click', copyDeliverable);
  DOM['btn-deliverable-download']?.addEventListener('click', downloadDeliverable);
  DOM['btn-open-group']?.addEventListener('click', () => { if (_boundGroupId) { switchTab('groups'); selectGroup(_boundGroupId); } });
  DOM['btn-open-project']?.addEventListener('click', () => { if (_boundProjectId) { switchTab('projects'); selectProject(_boundProjectId); } });
  DOM['btn-sidebar-toggle']?.addEventListener('click', () => document.body.classList.toggle('sidebar-open'));
  DOM['sidebar-backdrop']?.addEventListener('click', () => document.body.classList.remove('sidebar-open'));
  DOM['sidebar']?.addEventListener('click', (e) => { if (e.target.closest('.sidebar-item, .search-item')) document.body.classList.remove('sidebar-open'); });
  DOM['btn-new-project']?.addEventListener('click', openNewProject);
  DOM['btn-new-project-welcome']?.addEventListener('click', openNewProject);
  DOM['btn-home-new-project']?.addEventListener('click', openNewProject);
  DOM['np-cancel']?.addEventListener('click', closeNewProject);
  DOM['new-project-modal']?.querySelector('.modal-close')?.addEventListener('click', closeNewProject);
  DOM['btn-resume-project']?.addEventListener('click', async () => {
    const id = S.currentProjectId; if (!id) return;
    if (!await showConfirm('从断点续跑该项目？将回收磁盘上的已完成响应并继续未完成任务，无需重发 goal。', {title:'续跑项目', okText:'续跑'})) return;
    try { const r = await fetch(`/api/projects/${encodeURIComponent(id)}/resume`, { method: 'POST' }); const d = await r.json(); if (!r.ok) throw new Error(apiErr(d, '续跑失败')); if (d.resumed === false) throw new Error(d.reason || '项目已终态，无需续跑'); connectProjectStream(id); await refreshProjectDetail(id); } catch (e) { alert('续跑失败：' + (e.message || e)); }
  });
  DOM['btn-cancel-project']?.addEventListener('click', async () => {
    const id = S.currentProjectId; if (!id) return;
    if (!await showConfirm('取消该项目？当前正在执行的任务会跑完，之后不再派发新任务。', {title:'取消项目', okText:'取消项目', danger:true})) return;
    try { const r = await fetch(`/api/projects/${encodeURIComponent(id)}/cancel`, { method: 'POST' }); const d = await r.json(); if (!r.ok || d.success === false) throw new Error(apiErr(d, d.message || '取消失败')); await refreshProjectDetail(id); } catch (e) { alert('取消失败：' + (e.message || e)); }
  });
  DOM['np-submit']?.addEventListener('click', async () => {
    const goal = DOM['np-goal'].value.trim(); if (!goal) return;
    const payload = { goal, title: DOM['np-title'].value.trim(), mode: DOM['np-mode'].value };
    const budget = parseInt(DOM['np-budget'].value, 10); if (!isNaN(budget) && budget > 0) payload.budget = budget;
    if (DOM['np-review']?.checked) payload.review = true;
    DOM['np-submit'].disabled = true;
    try { const r = await fetch('/api/projects/run', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }); const d = await r.json(); if (!r.ok) throw new Error(apiErr(d, '发起失败')); closeNewProject(); DOM['np-goal'].value = ''; DOM['np-title'].value = ''; DOM['np-budget'].value = ''; await loadProjects(); renderProjectList(); switchTab('projects'); selectProject(d.project_id); } catch (e) { alert('发起项目失败：' + (e.message || e)); } finally { DOM['np-submit'].disabled = false; }
  });
  DOM['btn-save-settings']?.addEventListener('click', saveSettings);
  DOM['btn-apply-model-all']?.addEventListener('click', applyModelToAll);
  DOM['mm-save']?.addEventListener('click', saveManageModal);
  DOM['mm-cancel']?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));
  DOM['manage-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));
  DOM['btn-create-agent']?.addEventListener('click', openCreateModal);
  DOM['cf-cancel']?.addEventListener('click', closeCreateModal);
  DOM['create-agent-modal']?.querySelector('.modal-close')?.addEventListener('click', closeCreateModal);
  DOM['cf-submit'].addEventListener('click', async (e) => {
    e.preventDefault(); const desc = DOM['cf-description'].value.trim(); if (!desc) { showFormStatus('请输入 Agent 描述', 'error'); return; }
    const aid = DOM['cf-agent-id'].value.trim(); if (!aid) { showFormStatus('请输入 Agent ID', 'error'); return; }
    DOM['cf-submit'].disabled = true; DOM['cf-submit'].textContent = '创建中...'; showFormStatus('', '');
    try {
      const r = await fetch('/api/agents/create', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ description: desc, agent_id: aid, chinese_name: DOM['cf-name'].value.trim(), backend: DOM['cf-backend'].value, model: DOM['cf-model'].value }) });
      if (!r.ok) { const e = await r.json(); throw new Error(apiErr(e, '创建失败')); }
      const d = await r.json(); const a = d.agent;
      DOM['cf-result'].classList.remove('hidden'); DOM['cf-result'].querySelector('.result-details').innerHTML = `<div>📁 工作目录: ${esc(a.workspace)}</div><div>📝 文件: ${(a.files||[]).join(', ')}</div><div>⚙️ 后端: ${a.backend} / ${a.model}</div>`;
      showFormStatus('✓ Agent 已创建', 'success'); await loadAgents(); renderAgentList(); renderManageAgents();
      setTimeout(closeCreateModal, 1200);
    } catch(e) { showFormStatus(e.message, 'error'); } finally { DOM['cf-submit'].disabled = false; DOM['cf-submit'].textContent = '🚀 创建 Agent'; }
  });
  DOM.messages.addEventListener('click', e => {
    const thHeader = e.target.closest('.thinking-header');
    if (thHeader) { const sec = thHeader.closest('.thinking-section'); if (!sec) return; sec.classList.toggle('collapsed'); sec.setAttribute('aria-expanded', !sec.classList.contains('collapsed')); return; }
    const cp = e.target.closest('.msg-copy');
    if (cp) { const mc = cp.closest('.message')?.querySelector('.msg-content'); const txt = mc ? (mc.innerText || mc.textContent || '') : ''; if (txt && navigator.clipboard) { navigator.clipboard.writeText(txt).then(() => { cp.textContent = '✓'; setTimeout(() => { cp.textContent = '⧉'; }, 1200); }).catch(() => {}); } }
  });
  DOM.messages.addEventListener('scroll', () => { if (isNearBottom(DOM.messages)) hideNewMsgFloater(); });
}

// ============ Bootstrap ============
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}