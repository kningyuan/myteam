// ============ State ============
const S = {
  agents: [], backends: [], groups: [], projects: [],
  currentAgentId: null, currentGroupId: null, currentProjectId: null,
  isStreaming: false, abortCtrl: null, currentReader: null,
  streamContext: null,
  groupEventSource: null,
  agentEventSource: null,
  agentTaskBlocks: {},
  sidebarPollTimer: null,
  groupActivityTs: {},
  agentMessages: {}, groupMessages: {},
  hiddenAgents: new Set(),
  backendsCache: {},
  mentionActive: false, mentionFilter: '',
  mentionIdx: -1, groupMembers: [],
};

const CHAT_HISTORY_KEY = 'agentHub_chatHistory_v3';
const UI_STATE_KEY = 'agentHub_uiState_v1';
const THEME_KEY = 'agentHub_theme';
const CHAT_HISTORY_MAX = 300;

// ============ DOM Refs ============
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);
const DOM = {};

function cacheDom() {
  ['agent-list','group-list','messages','group-messages','welcome','chat-view',
   'group-welcome','group-chat-view','message-input','group-input','btn-send','btn-group-send',
   'btn-clear-chat','btn-delete-chat','btn-clear-group','btn-dissolve-group',
   'agent-search','agent-search-results','group-search','group-search-results',
   'chat-agent-name','chat-agent-id','chat-agent-avatar',
   'group-name','group-members','group-avatar',
   'cf-description','cf-agent-id','cf-name','cf-backend','cf-model','cf-submit','cf-cancel','cf-status','cf-result',
   'tab-chat','tab-groups','tab-projects','tab-agents','tab-settings',
   'project-list','project-count','project-welcome','project-detail-view',
   'project-title','project-meta','project-progress-text','project-progress-fill',
   'project-tasks','project-fleet','project-cost','project-events',
   'project-deliverable','deliverable-title','deliverable-meta','deliverable-body',
   'btn-new-project','btn-new-project-welcome','new-project-modal','btn-cancel-project',
   'np-goal','np-title','np-mode','np-budget','np-review','np-submit','np-cancel',
   'btn-theme','theme-dropdown',
   'modal-overlay','agent-config-modal','modal-backend','modal-model','modal-agent-info',
   'modal-save','modal-cancel','btn-agent-config',
   'group-config-modal','group-modal-name','group-modal-members','group-add-agent','btn-add-member','group-modal-close',
   'new-group-modal','ng-name','ng-desc','ng-submit','ng-cancel','btn-new-group',
   'status-badge','agent-count','btn-group-config','btn-send','btn-group-send',
   'manage-agent-table','manage-agent-count','btn-create-agent',
   'manage-tasktype-table','manage-tasktype-count','manage-memory-table','manage-memory-count',
   'create-agent-modal',
   'set-default-backend','set-default-model','set-port','set-cli-path','set-debug',
   'set-model-aliases','btn-save-settings','set-status','btn-apply-model-all',
   'set-use-project-group','set-auto-group','set-hub-url',
   'set-poll-interval','set-ack-timeout','set-task-timeout',
   'set-agent-msg-timeout','set-team-config-timeout','set-task-plan-timeout','set-max-retries',
   'mention-dropdown',
   'manage-modal','mm-id','mm-name','mm-backend','mm-model','mm-workspace','mm-save','mm-cancel','mm-status',
  ].forEach(id => DOM[id] = $(id));
}

// ============ Init ============
async function init() {
  cacheDom();
  loadChatHistory();
  loadTheme();
  await loadHiddenChats();
  setupTabs();
  setupThemeMenu();
  setupEventListeners();
  await Promise.all([loadAgents(), loadBackends(), loadGroups(), loadProjects()]);
  renderAgentList();
  renderGroupList();
  renderProjectList();
  setStatus('online');
  await restoreUiState();
  startSidebarPoll();
}

function saveUiState() {
  try {
    const tab = document.querySelector('.nav-tab.active')?.dataset.tab || 'chat';
    localStorage.setItem(UI_STATE_KEY, JSON.stringify({
      tab,
      agentId: S.currentAgentId,
      groupId: S.currentGroupId,
      projectId: S.currentProjectId,
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
      selectProject(st.projectId, { restore: true });
    }
  } catch (e) {
    console.warn('restoreUiState:', e);
  }
}

function loadTheme() {
  const theme = localStorage.getItem(THEME_KEY) || 'dark';
  applyTheme(theme);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme === 'light' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, theme);
}

function setupThemeMenu() {
  DOM['btn-theme']?.addEventListener('click', e => {
    e.stopPropagation();
    DOM['theme-dropdown']?.classList.toggle('hidden');
  });
  DOM['theme-dropdown']?.querySelectorAll('[data-theme]').forEach(btn => {
    btn.addEventListener('click', () => {
      applyTheme(btn.dataset.theme);
      DOM['theme-dropdown']?.classList.add('hidden');
    });
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.theme-menu')) DOM['theme-dropdown']?.classList.add('hidden');
  });
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

function agentLastActivityTs(agentId) {
  const msgs = S.agentMessages[agentId] || [];
  if (!msgs.length) return 0;
  return Math.max(...msgs.map(m => m.ts || 0));
}

function formatRelativeTime(ts) {
  if (!ts) return '';
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return '刚刚';
  if (sec < 3600) return `${Math.floor(sec / 60)}分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}小时前`;
  return `${Math.floor(sec / 86400)}天前`;
}

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
    if (bgA && !bgB) return -1;
    if (!bgA && bgB) return 1;
    return agentLastActivityTs(b.id) - agentLastActivityTs(a.id);
  });
  DOM['agent-list'].innerHTML = sorted.map(a => {
    const lastTs = agentLastActivityTs(a.id);
    const rel = formatRelativeTime(lastTs);
    const unread = (S.agentMessages[a.id] || []).filter(m => m._new).length;
    return `<div class="sidebar-item ${S.currentAgentId === a.id ? 'active' : ''}${unread ? ' has-new' : ''}" data-id="${a.id}">
      <span class="s-icon">${getAvatar(a.id)}</span>
      <span class="s-name">${esc(a.name)}</span>
      <span class="s-sub">${rel ? esc(rel) : ''}</span>
      ${unread ? `<span class="s-badge">${unread > 99 ? '99+' : unread}</span>` : ''}
      <span class="s-del" data-del-agent="${a.id}" title="删除对话">✕</span>
    </div>`;
  }).join('');
  DOM['agent-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('[data-del-agent]')) return;
      selectAgent(el.dataset.id);
    });
  });
  DOM['agent-list'].querySelectorAll('[data-del-agent]').forEach(el => {
    el.addEventListener('click', e => { e.stopPropagation(); deleteChatWindow(el.dataset.delAgent); });
  });
}

function getAvatar(id) {
  const m = { main:'👑', product:'📋', developer:'💻', designer:'🎨', researcher:'🔍',
    content:'✍️', ops:'⚙️', docs:'📖', consultation:'💡', coordinator:'✅',
    social:'📱', seo:'📈', email:'📧', deputy:'👥', tester:'🧪', ops2:'🛠️' };
  return m[id] || '🤖';
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

const TOOL_ICONS = {
  Read: '📖', Edit: '✏️', Write: '📝', Bash: '💻',
  Run: '⚡', Search: '🔍', Grep: '🔎', Glob: '📁',
  WebSearch: '🌐', WebFetch: '📄', Task: '📋', Think: '🧠',
};

function parseToolInputObj(input) {
  if (!input) return {};
  if (typeof input === 'object') return input;
  const s = String(input).trim();
  try { return JSON.parse(s); } catch (e) {
    try { return JSON.parse(s.replace(/^"(.*)"$/, '$1')); } catch (e2) { return { raw: s }; }
  }
}

function formatToolInputJson(input) {
  const obj = parseToolInputObj(input);
  if (obj.raw != null) return obj.raw;
  try { return JSON.stringify(obj, null, 2); } catch (e) { return String(input || ''); }
}

function shortPath(p) {
  if (!p) return '…';
  const parts = String(p).replace(/\\/g, '/').split('/').filter(Boolean);
  if (parts.length <= 2) return parts.join('/');
  return '…/' + parts.slice(-2).join('/');
}

function truncateText(s, n) {
  s = String(s || '');
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function describeToolAction(name, input) {
  const inp = parseToolInputObj(input);
  const n = name || 'tool';
  switch (n) {
    case 'Read':
      return { verb: '读取', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Write':
      return { verb: '写入', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Edit':
      return { verb: '编辑', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Bash':
    case 'Run':
      return { verb: '运行命令', target: truncateText(inp.command || inp.cmd || inp.script || inp.raw || '', 80), mono: true };
    case 'Grep':
      return { verb: '搜索', target: `"${truncateText(inp.pattern || inp.query || '', 36)}" · ${shortPath(inp.path || inp.glob || '.')}`, mono: false };
    case 'Glob':
      return { verb: '匹配文件', target: inp.pattern || inp.glob || '…', mono: true };
    case 'WebSearch':
      return { verb: 'Web 搜索', target: truncateText(inp.query || inp.q || '', 60), mono: false };
    case 'WebFetch':
      return { verb: '抓取 URL', target: truncateText(inp.url || '', 72), mono: true };
    case 'Task':
      return { verb: '子任务', target: truncateText(inp.description || inp.prompt || '', 60), mono: false };
    case 'Think':
      return { verb: '推理', target: truncateText(inp.thought || inp.content || inp.text || formatToolInputJson(input), 120), mono: false };
    default:
      return { verb: n, target: truncateText(formatToolInputJson(input).replace(/\s+/g, ' '), 60), mono: true };
  }
}

function buildActivityStep(stepNum) {
  return `<div class="activity-step"><span class="activity-step-label">步骤 ${stepNum}</span></div>`;
}

function buildActivityRow(toolUse, toolResult) {
  const act = describeToolAction(toolUse.name, toolUse.input);
  const icon = TOOL_ICONS[toolUse.name] || '🔧';
  const pending = !toolResult;
  const args = formatToolInputJson(toolUse.input);
  const targetHtml = act.mono
    ? `<code class="activity-target">${esc(act.target)}</code>`
    : `<span class="activity-target-text">${esc(act.target)}</span>`;
  let html =
    `<div class="activity-row${pending ? ' pending' : ' done'}">` +
    `<div class="activity-main">` +
    `<span class="activity-icon">${icon}</span>` +
    `<span class="activity-verb">${esc(act.verb)}</span>${targetHtml}` +
    `<span class="activity-status">${pending ? '…' : '✓'}</span>` +
    `</div>` +
    `<details class="activity-detail"><summary>参数</summary><pre class="activity-pre">${esc(args)}</pre></details>`;
  if (toolResult) html += buildActivityResultInner(toolResult);
  html += '</div>';
  return html;
}

function buildActivityResultInner(toolResult) {
  const c = toolResult.content || '';
  return `<details class="activity-detail activity-result"><summary>返回 (${c.length} 字符)</summary><pre class="activity-pre activity-pre-result">${esc(c)}</pre></details>`;
}

function buildThinkingStepFinish(d) {
  const t = d.tokens || {};
  return `<div class="activity-meta">Token ↑${t.input || 0} ↓${t.output || 0} · 步骤完成</div>`;
}

function buildThinkingBodyHtml(thinking) {
  let html = '';
  let step = 0;
  const items = thinking || [];
  for (let i = 0; i < items.length; i++) {
    const t = items[i];
    if (t.type === 'step_start') {
      step += 1;
      html += buildActivityStep(step);
    } else if (t.type === 'tool_use') {
      const next = items[i + 1];
      const paired = next?.type === 'tool_result' ? next : null;
      html += buildActivityRow(t, paired);
      if (paired) i += 1;
    } else if (t.type === 'tool_result') {
      html += `<div class="activity-row done">${buildActivityResultInner(t)}</div>`;
    } else if (t.type === 'step_finish' && t.tokens) {
      html += buildThinkingStepFinish(t);
    }
  }
  return html;
}

function countThinkingActivities(thinking) {
  return (thinking || []).filter(t => t.type === 'tool_use' || t.type === 'step_start').length;
}

function thinkingSectionTitle(thinking, streaming) {
  const n = countThinkingActivities(thinking);
  if (streaming && !n) return 'Agent 活动 · 等待中…';
  if (!n) return 'Agent 活动';
  return `Agent 活动 · ${n} 项`;
}

function appendThinkingEvent(msg, tb, d) {
  msg.thinking = msg.thinking || [];
  msg.thinking.push(d);
  if (!tb) return;

  if (d.type === 'step_start') {
    msg.__step = (msg.__step || 0) + 1;
    tb.insertAdjacentHTML('beforeend', buildActivityStep(msg.__step));
  } else if (d.type === 'tool_use') {
    tb.insertAdjacentHTML('beforeend', buildActivityRow(d, null));
  } else if (d.type === 'tool_result') {
    const pending = tb.querySelector('.activity-row.pending:last-of-type');
    if (pending) {
      pending.classList.remove('pending');
      pending.classList.add('done');
      pending.querySelector('.activity-status').textContent = '✓';
      pending.insertAdjacentHTML('beforeend', buildActivityResultInner(d));
    } else {
      tb.insertAdjacentHTML('beforeend', `<div class="activity-row done">${buildActivityResultInner(d)}</div>`);
    }
  } else if (d.type === 'step_finish' && d.tokens) {
    tb.insertAdjacentHTML('beforeend', buildThinkingStepFinish(d));
  }
}

function updateThinkingHeader(ts, msg, streaming) {
  const title = ts?.querySelector('.thinking-title');
  if (title) title.textContent = thinkingSectionTitle(msg.thinking, streaming);
}

// ============ Chat / Group Archive ============
async function loadHiddenChats() {
  try {
    const r = await fetch('/api/chat/archives/search?q=');
    const d = await r.json();
    S.hiddenAgents = new Set((d.results || []).map(x => x.agent_id));
  } catch (e) {
    console.warn('loadHiddenChats:', e);
    S.hiddenAgents = new Set();
  }
}

async function deleteChatWindow(agentId) {
  const id = agentId || S.currentAgentId;
  if (!id) return;
  const a = S.agents.find(x => x.id === id);
  const name = a ? a.name : id;
  if (!confirm(`删除与「${name}」的对话窗口？\n\n· 侧栏隐藏，可用搜索找回\n· 不会删除 Agent 配置\n· 如需清空 LLM 记忆请用「清空对话」`)) return;

  const msgs = S.agentMessages[id] || [];
  const snapshot = {
    label: name,
    messages: msgs.map(m => ({ role: m.role, content: m.content, thinking: m.thinking })),
  };
  try {
    const r = await fetch(`/api/chat/${id}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  } catch (e) {
    alert('删除失败: ' + e.message);
    return;
  }

  S.hiddenAgents.add(id);
  if (S.currentAgentId === id) {
    S.currentAgentId = null;
    DOM.welcome.classList.remove('hidden');
    DOM['chat-view'].classList.add('hidden');
    DOM.messages.innerHTML = '';
  }
  renderAgentList();
}

async function restoreChatWindow(agentId) {
  try {
    const r = await fetch(`/api/chat/${agentId}/restore`, { method: 'POST' });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '恢复失败');
    S.hiddenAgents.delete(agentId);
    if (d.snapshot?.messages?.length) {
      S.agentMessages[agentId] = d.snapshot.messages;
      saveChatHistory();
    }
    hideSearchResults('agent');
    renderAgentList();
    selectAgent(agentId);
  } catch (e) {
    alert('恢复失败: ' + e.message);
  }
}

async function searchChatArchives(q) {
  const box = DOM['agent-search-results'];
  if (!box) return;
  if (!q.trim()) { box.classList.add('hidden'); return; }
  try {
    const r = await fetch(`/api/chat/archives/search?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    const results = d.results || [];
    box.innerHTML = results.length
      ? results.map(x =>
          `<div class="search-item" data-restore-agent="${x.agent_id}">
            <div>${esc(x.label || x.agent_id)}</div>
            <div class="sub">${esc(x.agent_id)} · 点击恢复</div>
          </div>`
        ).join('')
      : '<div class="search-item"><span class="sub">无匹配归档</span></div>';
    box.querySelectorAll('[data-restore-agent]').forEach(el => {
      el.addEventListener('click', () => restoreChatWindow(el.dataset.restoreAgent));
    });
    box.classList.remove('hidden');
  } catch (e) {
    console.warn('searchChatArchives:', e);
  }
}

async function dissolveGroupWindow() {
  if (!S.currentGroupId) return;
  const g = S.groups.find(x => x.id === S.currentGroupId);
  const name = g ? g.name : S.currentGroupId;
  if (!confirm(`解散群组「${name}」？\n\n· 从列表隐藏，可搜索恢复\n· 不删除 tasks/ 项目数据\n· 消息记录将清空`)) return;

  try {
    const r = await fetch(`/api/groups/${S.currentGroupId}/dissolve`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
  } catch (e) {
    alert('解散失败: ' + e.message);
    return;
  }

  S.currentGroupId = null;
  DOM['group-welcome'].classList.remove('hidden');
  DOM['group-chat-view'].classList.add('hidden');
  await loadGroups();
  renderGroupList();
}

async function restoreGroupWindow(groupId) {
  try {
    const r = await fetch(`/api/groups/${groupId}/restore`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || '恢复失败');
    hideSearchResults('group');
    await loadGroups();
    renderGroupList();
    selectGroup(groupId);
  } catch (e) {
    alert('恢复失败: ' + e.message);
  }
}

async function searchGroupsArchive(q) {
  const box = DOM['group-search-results'];
  if (!box) return;
  if (!q.trim()) { box.classList.add('hidden'); return; }
  try {
    const r = await fetch(`/api/groups/search?q=${encodeURIComponent(q)}&include_dissolved=true`);
    const d = await r.json();
    const results = d.groups || [];
    box.innerHTML = results.length
      ? results.map(g =>
          `<div class="search-item" data-restore-group="${g.id}" data-dissolved="${g.status === 'dissolved' ? '1' : '0'}">
            <div>${esc(g.name)} ${g.status === 'dissolved' ? '（已解散）' : ''}</div>
            <div class="sub">${esc(g.id)} · ${g.member_count}人</div>
          </div>`
        ).join('')
      : '<div class="search-item"><span class="sub">无匹配群组</span></div>';
    box.querySelectorAll('[data-restore-group]').forEach(el => {
      el.addEventListener('click', () => {
        const gid = el.dataset.restoreGroup;
        if (el.dataset.dissolved === '1') restoreGroupWindow(gid);
        else { hideSearchResults('group'); selectGroup(gid); }
      });
    });
    box.classList.remove('hidden');
  } catch (e) {
    console.warn('searchGroupsArchive:', e);
  }
}

function hideSearchResults(kind) {
  const box = kind === 'group' ? DOM['group-search-results'] : DOM['agent-search-results'];
  if (box) box.classList.add('hidden');
}

// ============ Groups ============
async function loadGroups() {
  try {
    const r = await fetch('/api/groups');
    const d = await r.json();
    S.groups = d.groups || [];
    for (const g of S.groups) {
      const ts = g.last_message_at || g.created_at || 0;
      if (ts) S.groupActivityTs[g.id] = Math.max(S.groupActivityTs[g.id] || 0, ts * (ts > 1e12 ? 1 : 1000));
    }
  } catch(e) { console.error('groups:', e); }
}

function startSidebarPoll() {
  if (S.sidebarPollTimer) clearInterval(S.sidebarPollTimer);
  S.sidebarPollTimer = setInterval(async () => {
    const tab = document.querySelector('.nav-tab.active')?.dataset.tab;
    if (tab === 'groups') {
      await loadGroups();
      renderGroupList();
    } else if (tab === 'chat') {
      // 主动检测后台私聊记录，触发排序更新
      const ids = [S.currentAgentId, 'main'].filter(Boolean);
      for (const id of [...new Set(ids)]) {
        try {
          const r = await fetch(`/api/agents/${encodeURIComponent(id)}/chats`);
          const d = await r.json();
          const msgs = d.messages || [];
          let existing = S.agentMessages[id] || [];
          let changed = false;
          for (const m of msgs) {
            if (!existing.some(x => x.ts === m.ts)) {
              m._new = true;
              existing.push(m);
              changed = true;
            }
          }
          if (changed) {
            S.agentMessages[id] = existing;
            // 已删除的聊天窗口收到被动消息 → 自动恢复
            if (S.hiddenAgents.has(id)) {
              try {
                await fetch(`/api/chat/${encodeURIComponent(id)}/restore`, { method: 'POST' });
              } catch (e) { /* ignore */ }
              S.hiddenAgents.delete(id);
            }
          }
        } catch (e) { /* ignore */ }
      }
      renderAgentList();
    }
  }, 8000);
}

function groupLastActivityTs(g) {
  const cached = S.groupActivityTs[g.id];
  const apiTs = (g.last_message_at || 0) * (g.last_message_at > 1e12 ? 1 : 1000);
  return Math.max(cached || 0, apiTs || 0, (g.created_at || 0) * (g.created_at > 1e12 ? 1 : 1000));
}

function renderGroupList() {
  if (!DOM['group-list']) return;
  const active = S.groups.filter(g => g.status !== 'dissolved');
  if (!active.length) {
    DOM['group-list'].innerHTML = '<div class="empty">暂无群组<br><small>点击 + 创建，或用搜索找回已解散群组</small></div>';
    return;
  }
  const sorted = [...active].sort((a, b) => groupLastActivityTs(b) - groupLastActivityTs(a));
  DOM['group-list'].innerHTML = sorted.map(g => {
    const rel = formatRelativeTime(groupLastActivityTs(g));
    return `<div class="sidebar-item ${S.currentGroupId === g.id ? 'active' : ''}" data-id="${g.id}">
      <span class="s-icon">👥</span>
      <span class="s-name">${esc(g.name)}</span>
      <span class="s-sub">${rel || `${g.member_count}人`}</span>
    </div>`;
  }).join('');
  DOM['group-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', () => selectGroup(el.dataset.id));
  });
}

// ============ Projects ============
const PROJECT_TERMINAL = new Set(['completed', 'failed', 'partially_failed', 'aborted', 'cancelled', 'paused', 'timed_out']);

async function loadProjects() {
  try {
    const r = await fetch('/api/obs/projects');
    const d = await r.json();
    S.projects = d.projects || [];
    if (DOM['project-count']) DOM['project-count'].textContent = S.projects.length;
  } catch (e) {
    console.error('projects:', e);
    S.projects = [];
  }
}

function renderProjectList() {
  if (!DOM['project-list']) return;
  if (!S.projects.length) {
    DOM['project-list'].innerHTML = '<div class="empty">暂无项目<br><small>点击 + 发起一个项目</small></div>';
    return;
  }
  DOM['project-list'].innerHTML = S.projects.map(p =>
    `<div class="sidebar-item ${S.currentProjectId === p.id ? 'active' : ''}" data-id="${p.id}">
      <span class="s-icon">📋</span>
      <span class="s-name">${esc(p.title || p.id)}</span>
      <span class="s-sub">${Math.round((p.progress || 0) * 100)}% · ${p.task_count || 0}任务 · ${esc(p.status || '')}</span>
      <button class="s-del" data-del="${p.id}" title="删除项目">🗑</button>
    </div>`
  ).join('');
  DOM['project-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', () => selectProject(el.dataset.id));
  });
  DOM['project-list'].querySelectorAll('.s-del').forEach(btn => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); deleteProject(btn.dataset.del); });
  });
}

async function deleteProject(id) {
  if (!confirm(`确认彻底删除项目「${id}」？将清除其数据库记录、交付物目录与 agent 临时文件，不可恢复。`)) return;
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '删除失败');
    if (S.currentProjectId === id) {
      stopProjectPoll();
      S.currentProjectId = null;
      DOM['project-detail-view']?.classList.add('hidden');
      DOM['project-welcome']?.classList.remove('hidden');
    }
    await loadProjects();
    renderProjectList();
  } catch (e) {
    alert('删除项目失败：' + (e.message || e));
  }
}

function stopProjectPoll() {
  if (S._projectPoll) { clearInterval(S._projectPoll); S._projectPoll = null; }
}

async function selectProject(id, opts = {}) {
  S.currentProjectId = id;
  S.currentAgentId = null;
  S.currentGroupId = null;
  stopProjectPoll();
  renderProjectList();
  DOM['project-welcome'].classList.add('hidden');
  DOM['project-detail-view'].classList.remove('hidden');
  DOM['project-deliverable']?.classList.add('hidden');
  await refreshProjectDetail(id);
  // 非终态时轮询实时刷新（内核在后台跑）
  S._projectPoll = setInterval(async () => {
    if (S.currentProjectId !== id) { stopProjectPoll(); return; }
    const done = await refreshProjectDetail(id);
    if (done) { stopProjectPoll(); loadProjects().then(renderProjectList); }
  }, 2500);
  if (!opts.restore) saveUiState();
}

async function refreshProjectDetail(id) {
  try {
    const pid = encodeURIComponent(id);
    const [ov, cost, fleet, rs, ev] = await Promise.all([
      fetch(`/api/obs/projects/${pid}/overview`).then(r => r.json()),
      fetch(`/api/obs/projects/${pid}/cost`).then(r => r.json()).catch(() => ({})),
      fetch(`/api/obs/projects/${pid}/fleet`).then(r => r.json()).catch(() => ({fleet: {}})),
      fetch(`/api/projects/run-status/${pid}`).then(r => r.json()).catch(() => ({})),
      fetch(`/api/obs/projects/${pid}/events`).then(r => r.json()).catch(() => ({events: []})),
    ]);
    const status = ov.status || (rs.running ? 'running' : 'unknown');
    const active = rs.running || !PROJECT_TERMINAL.has(status);
    DOM['btn-cancel-project']?.classList.toggle('hidden', !active);
    DOM['project-title'].textContent = ov.title || id;
    const launchErr = rs && rs.error ? ` · ⚠️ ${rs.error}` : '';
    DOM['project-meta'].textContent = `${id} · ${status}${rs.running ? ' · 运行中' : ''}${launchErr}`;
    const pct = Math.round((ov.progress || 0) * 100);
    DOM['project-progress-text'].textContent = `${pct}%`;
    DOM['project-progress-fill'].style.width = `${pct}%`;

    // 任务 & 产出（点开看交付物）
    const tasks = ov.tasks || [];
    const byTask = (cost && cost.by_task) || {};
    DOM['project-tasks'].innerHTML = tasks.length
      ? tasks.map(t => {
          const st = t.status || 'pending';
          const deps = (t.dependencies || []).join(', ');
          const tok = byTask[t.id] ? `${byTask[t.id]} tok` : '';
          const sub = t.summary ? `<small class="hint">${esc(t.summary)}</small>`
                                : (deps ? `<small class="hint">依赖: ${esc(deps)}</small>` : '');
          return `<div class="task-row status-${st} clickable" data-task="${esc(t.id)}">
            <span class="task-id">${esc(t.id)}</span>
            <span class="task-name">${esc(t.name || '')}${sub ? '<br>' + sub : ''}</span>
            <span class="task-agent">${esc(t.agent || '-')}</span>
            <span class="task-tokens">${tok}</span>
            <span class="task-status">${esc(st)}</span>
          </div>`;
        }).join('')
      : (rs.running ? '<div class="empty">内核启动中（team_config / task_plan 决策中）…</div>'
                    : '<div class="empty">暂无任务</div>');
    DOM['project-tasks'].querySelectorAll('.task-row.clickable').forEach(el => {
      el.addEventListener('click', () => openDeliverable(id, el.dataset.task));
    });

    // 舰队状态
    const fl = (fleet && fleet.fleet) || {};
    const flEntries = Object.entries(fl);
    DOM['project-fleet'].innerHTML = flEntries.length
      ? flEntries.map(([a, s]) => `<span class="fleet-chip live-${esc(s)}">${esc(a)} · ${esc(s)}</span>`).join('')
      : '<span class="hint">暂无</span>';

    // 成本
    const total = (cost && cost.project) || 0;
    const byAgent = (cost && cost.by_agent) || {};
    const agentRows = Object.entries(byAgent)
      .map(([a, n]) => `<div class="cost-row"><span>${esc(a)}</span><span>${n}</span></div>`).join('');
    DOM['project-cost'].innerHTML =
      `<div class="cost-row cost-total"><span>合计</span><span>${total} tok</span></div>${agentRows || ''}`;

    renderEventFeed((ev && ev.events) || []);

    return PROJECT_TERMINAL.has(status) && !rs.running;
  } catch (e) {
    DOM['project-meta'].textContent = `${id} · 加载失败：${String(e.message || e)}`;
    return false;
  }
}

const EVENT_LABELS = {
  gate_passed:'✅ 门禁通过', gate_failed:'⛔ 门禁未过', review_done:'🔎 评审完成',
  review_unreachable:'⚠️ 评审不可达', plan_rejected:'↩️ 计划被拒', blocked:'🚧 任务阻塞',
  budget_alert:'💰 预算告警', budget_over:'🛑 预算超限', cycle_done:'🔁 周期完成',
  watchdog_soft_idle:'😴 疑似卡住', watchdog_hard_kill:'🔪 看门狗中止',
  transport_error:'💥 传输错误', reconcile_timed_out:'⏱️ 重启对账超时',
  tool_use:'🛠️ skill 调用', prompt_sent:'📤 发送给 CLI', message:'💬 消息',
};
const INTERACTION_LABELS = {
  team_config:'组队配置', task_plan:'任务拆分', execute:'执行', review:'评审', triage:'分诊',
};

function eventDetail(e) {
  const p = e.payload || {};
  if (e.kind === 'gate_failed' && Array.isArray(p.failures)) return p.failures.join('；');
  if (e.kind === 'review_done') return (p.passed ? '通过' : '打回') + (p.feedback ? ' · ' + p.feedback : '');
  if (e.kind === 'message') return (p.sender ? p.sender + '：' : '') + (p.text || '');
  if (e.kind === 'tool_use') return p.tool || p.name || JSON.stringify(p).slice(0, 120);
  if (e.kind === 'blocked' || e.kind === 'plan_rejected') return p.reason || (p.invalid_agents || []).join(', ');
  if (e.kind === 'budget_alert' || e.kind === 'budget_over') return JSON.stringify(p);
  return p && Object.keys(p).length ? JSON.stringify(p).slice(0, 120) : '';
}

function renderEventFeed(events) {
  const box = DOM['project-events'];
  if (!box) return;
  if (!events.length) { box.innerHTML = '<span class="hint">暂无执行事件</span>'; return; }
  box.innerHTML = events.map(e => {
    const ts = (e.ts || '').replace('T', ' ').slice(5);
    const who = [e.task_id, e.agent_id].filter(Boolean).map(esc).join(' · ');
    if (e.category === 'interaction') {
      const label = INTERACTION_LABELS[e.kind] || e.kind || '交互';
      const att = e.attempt > 1 ? ` ×${e.attempt}` : '';
      const tok = e.tokens ? ` · ${e.tokens} tok` : '';
      return `<div class="feed-row feed-interaction status-${esc(e.status || '')}">
        <span class="feed-ts">${esc(ts)}</span>
        <span class="feed-kind">${esc(label)}${att}</span>
        <span class="feed-who">${who}</span>
        <span class="feed-state">${esc(e.status || '')}${tok}</span>
      </div>`;
    }
    const label = EVENT_LABELS[e.kind] || e.kind;
    const detail = eventDetail(e);
    return `<div class="feed-row feed-event evk-${esc(e.kind)}">
      <span class="feed-ts">${esc(ts)}</span>
      <span class="feed-kind">${esc(label)}</span>
      <span class="feed-detail" title="${esc(detail)}">${esc(detail)}</span>
    </div>`;
  }).join('');
}

async function openDeliverable(projectId, taskId) {
  const panel = DOM['project-deliverable'];
  if (!panel) return;
  panel.classList.remove('hidden');
  DOM['deliverable-title'].textContent = `交付物 · ${taskId}`;
  DOM['deliverable-meta'].textContent = '加载中…';
  DOM['deliverable-body'].innerHTML = '';
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载失败');
    if (!d.exists || !d.content) {
      DOM['deliverable-meta'].textContent = '该任务暂无交付物文件';
      DOM['deliverable-body'].innerHTML = '';
      return;
    }
    DOM['deliverable-meta'].textContent = `${d.content.length} 字符`;
    DOM['deliverable-body'].innerHTML = typeof renderAgentMarkdown === 'function'
      ? renderAgentMarkdown(d.content)
      : esc(d.content).replace(/\n/g, '<br>');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e);
  }
}

async function loadBackgroundChats(agentId) {
  try {
    const r = await fetch(`/api/agents/${encodeURIComponent(agentId)}/chats`);
    const d = await r.json();
    const msgs = d.messages || [];
    let existing = S.agentMessages[agentId] || [];
    let changed = false;
    for (const m of msgs) {
      if (!existing.some(x => x.ts === m.ts)) {
        existing.push(m);
        changed = true;
      }
    }
    if (changed) {
      S.agentMessages[agentId] = existing;
      if (agentId === S.currentAgentId) {
        DOM.messages.innerHTML = '';
        existing.forEach(m => renderAgentMsg(m, DOM.messages, agentId));
      }
    }
  } catch (e) { /* ignore */ }
}

// ============ Select Agent (1-on-1 chat) ============
function selectAgent(id, opts = {}) {
  if (S.isStreaming) { stopStream(); }
  S.currentAgentId = id;
  S.currentGroupId = null;
  S.currentProjectId = null;
  // 清除新消息标记
  (S.agentMessages[id] || []).forEach(m => { m._new = false; });
  renderAgentList();
  DOM.welcome.classList.add('hidden');
  DOM['chat-view'].classList.remove('hidden');
  const a = S.agents.find(x => x.id === id);
  if (a) {
    DOM['chat-agent-name'].textContent = a.name;
    DOM['chat-agent-id'].textContent =
      [a.id, a.backend, a.model].filter(Boolean).join(' · ');
    DOM['chat-agent-avatar'].textContent = getAvatar(id);
  }
  DOM.messages.innerHTML = '';
  if (S.agentMessages[id]) {
    S.agentMessages[id].forEach(m => renderAgentMsg(m, DOM.messages, id));
  }
  // 加载持久化的后台执行私聊记录
  loadBackgroundChats(id);
  DOM['message-input'].disabled = false;
  DOM['message-input'].focus();
  updateSendBtn();
  connectAgentEvents(id);
  if (!opts.restore) saveUiState();
}

// ============ Agent Chat Sending ============
async function sendAgentMsg() {
  const text = DOM['message-input'].value.trim();
  if (!text || S.isStreaming || !S.currentAgentId) return;

  const msg = { role:'user', content:text, ts: Date.now() };
  addAgentMsg(S.currentAgentId, msg);
  renderAgentMsg(msg, DOM.messages, S.currentAgentId);
  DOM['message-input'].value = ''; DOM['message-input'].style.height = 'auto';
  S.isStreaming = true; setStatus('busy');
  updateSendBtn();

  const aMsg = { role:'agent', content:'', thinking:[], ts: Date.now() };
  addAgentMsg(S.currentAgentId, aMsg);
  const el = renderAgentMsg(aMsg, DOM.messages, S.currentAgentId);
  const tb = el?.querySelector('.thinking-body');
  const ts = el?.querySelector('.thinking-section');
  const ce = el?.querySelector('.msg-content');

  try {
    S.abortCtrl = new AbortController();
    const resp = await fetch(`/api/chat/${S.currentAgentId}?message=${encodeURIComponent(text)}`, { signal: S.abortCtrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    S.currentReader = reader;
    S.streamContext = { mode: 'agent', userText: text, agentEl: el };
    const dec = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        const t = line.trim();
        if (!t || t === 'data: [DONE]') continue;
        if (!t.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(t.slice(6));
          handleChatEvent(ev, aMsg, ce, tb, ts, el);
        } catch(e) {}
      }
    }
    if (ce && !aMsg.content && !aMsg.thinking.length) {
      renderBubbleMarkdown(ce, '(空响应)');
    }
  } catch(e) {
    if (e.name === 'AbortError') {
      rollbackAgentTurn(text, el);
    } else {
      showAgentError(el, e.message);
    }
  } finally {
    S.currentReader = null;
    S.streamContext = null;
    S.isStreaming = false; setStatus('online');
    updateSendBtn();
    scrollBottom(DOM.messages);
    removeTyping(el);
    const tsEl = el?.querySelector('.thinking-section');
    const tbEl = el?.querySelector('.thinking-body');
    if (tsEl && tbEl && !tbEl.children.length && !S.isStreaming) tsEl.style.display = 'none';
    if (tsEl) updateThinkingHeader(tsEl, aMsg, false);
    saveChatHistory();
  }
}

function normalizeBubbleText(text) {
  if (!text) return '';
  let s = String(text);
  // OpenCode 常在步骤切换/工具调用前推送大量换行，全部进入 text 事件
  s = s.replace(/^[\n\r\s]+/, '');
  s = s.replace(/\n{4,}/g, '\n\n\n');
  return s;
}

function renderBubbleMarkdown(contentEl, text) {
  const normalized = normalizeBubbleText(text || '');
  if (!contentEl) return normalized;
  if (!normalized) {
    contentEl.innerHTML = '';
    contentEl.classList.remove('markdown-body');
    contentEl.style.display = 'none';
    return '';
  }
  contentEl.classList.add('markdown-body');
  contentEl.innerHTML = typeof renderAgentMarkdown === 'function'
    ? renderAgentMarkdown(normalized)
    : esc(normalized).replace(/\n/g, '<br>');
  contentEl.style.display = '';
  return normalized;
}

function appendBubbleText(msg, contentEl, chunk) {
  msg.content = normalizeBubbleText((msg.content || '') + (chunk || ''));
  renderBubbleMarkdown(contentEl, msg.content);
  return msg.content;
}

function handleChatEvent(ev, msg, contentEl, tb, ts, rootEl) {
  if (!ev || !rootEl) return;
  if (ev.event === 'thinking') {
    handleThinking(ev.data, msg, contentEl, tb, ts, rootEl);
  } else if (ev.event === 'error') {
    showAgentError(rootEl, ev.data?.message || '未知错误');
  } else if (ev.event === 'done') {
    msg.sessionId = ev.data?.session_id || '';
  }
}

function handleThinking(d, msg, contentEl, tb, ts, rootEl) {
  if (!d) return;

  if (d.type === 'text') {
    appendBubbleText(msg, contentEl, d.content);
    scrollBottom(DOM.messages);
    return;
  }

  if (!ts && rootEl) {
    ts = rootEl.querySelector('.thinking-section');
    tb = rootEl.querySelector('.thinking-body');
  }
  if (ts) ts.style.display = '';

  if (d.type === 'step_start' || d.type === 'tool_use' || d.type === 'tool_result' || d.type === 'step_finish') {
    appendThinkingEvent(msg, tb, d);
    updateThinkingHeader(ts, msg, true);
  }
  scrollBottom(DOM.messages);
}

function showAgentError(rootEl, message) {
  const ce = rootEl?.querySelector('.msg-content');
  if (ce) {
    ce.classList.remove('markdown-body');
    ce.textContent = message;
    ce.classList.add('error');
  }
}

function renderAgentMsg(msg, container, agentId) {
  const c = container || DOM.messages;
  const aid = agentId || S.currentAgentId;
  const div = document.createElement('div');
  if (msg.role === 'user') {
    div.className = 'message user';
    div.innerHTML = '<div class="msg-content">' + esc(msg.content) + '</div>';
  } else if (msg.role === 'agent') {
    div.className = 'message agent';
    const a = S.agents.find(x => x.id === aid);
    const nm = a ? a.name : 'Agent';
    const hasThinking = msg.thinking && msg.thinking.length;

    div.innerHTML =
      '<div class="msg-header"><span class="msg-agent-icon">' + getAvatar(aid) + '</span>' + esc(nm) + '</div>' +
      '<div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">' + esc(thinkingSectionTitle(msg.thinking, !!(msg.ts && S.isStreaming))) + '</span></div><div class="thinking-body">' + buildThinkingBodyHtml(msg.thinking) + '</div></div>' +
      '<div class="msg-content"></div>' +
      '<div class="typing-dots" style="display:none"><span></span><span></span><span></span></div>';

    const ce = div.querySelector('.msg-content');
    if (ce) renderBubbleMarkdown(ce, msg.content || '');

    const ts = div.querySelector('.thinking-section');
    if (ts && !hasThinking && !(msg.ts && S.isStreaming)) ts.style.display = 'none';
    if (ts && msg.ts && S.isStreaming) ts.style.display = '';

    if (msg.ts && S.isStreaming && !msg.content && !hasThinking) {
      const td = div.querySelector('.typing-dots');
      if (td) td.style.display = 'flex';
    }
  } else if (msg.role === 'system') {
    div.className = 'message system';
    div.textContent = msg.content;
  }
  c.appendChild(div);
  scrollBottom(c);
  return div;
}

// ============ Select Group ============
async function selectGroup(id, opts = {}) {
  S.currentGroupId = id;
  S.currentAgentId = null;
  S.currentProjectId = null;
  renderGroupList();
  DOM['group-welcome'].classList.add('hidden');
  DOM['group-chat-view'].classList.remove('hidden');
  DOM['group-messages'].innerHTML = '';

  try {
    const r = await fetch(`/api/groups/${id}`);
    const d = await r.json();
    const g = d.group;
    DOM['group-name'].textContent = g.name;
    S.groupMembers = g.members || [];
    DOM['group-members'].textContent = `成员: ${(g.members||[]).join(', ') || '无'}`;

    // Render history
    (g.messages||[]).forEach(m => {
      renderGroupMsg(m);
    });
  } catch(e) { console.error(e); }
  DOM['group-input'].disabled = false;
  DOM['group-input'].focus();
  updateGroupSendBtn();
  populateGroupMemberSelect();
  connectGroupEvents(id);
  if (!opts.restore) saveUiState();
}

// ============ @mention Autocomplete ============
function showMentionDropdown(filter) {
  const dd = DOM['mention-dropdown'];
  if (!dd || !S.groupMembers.length) return;
  const matched = S.groupMembers.filter(m => m.includes(filter));
  if (!matched.length) { dd.classList.add('hidden'); return; }
  dd.innerHTML = matched.map((m, i) => {
    const agent = S.agents.find(a => a.id === m);
    return `<div class="mention-item ${i === 0 ? 'active' : ''}" data-id="${m}">
      <span class="m-icon">${agent ? getAvatar(m) : '🤖'}</span>
      <span class="m-name">${agent ? esc(agent.name) : esc(m)}</span>
      <span class="m-id">@${esc(m)}</span>
    </div>`;
  }).join('');
  dd.classList.remove('hidden');
  S.mentionActive = true;
  S.mentionFilter = filter;
  S.mentionIdx = 0;
  // Click handler for items
  dd.querySelectorAll('.mention-item').forEach(el => {
    el.addEventListener('click', () => insertMention(el.dataset.id));
  });
}

function hideMentionDropdown() {
  const dd = DOM['mention-dropdown'];
  if (dd) dd.classList.add('hidden');
  S.mentionActive = false;
  S.mentionFilter = '';
  S.mentionIdx = -1;
}

function insertMention(agentId) {
  const input = DOM['group-input'];
  const val = input.value;
  const pos = input.selectionStart;
  // Find the @ being typed
  let atPos = pos - 1;
  while (atPos >= 0 && val[atPos] !== '@') atPos--;
  if (atPos < 0) { hideMentionDropdown(); return; }
  // Replace from @ to cursor with @agent_id
  input.value = val.slice(0, atPos) + `@${agentId} ` + val.slice(pos);
  input.focus();
  const newPos = atPos + agentId.length + 2;
  input.setSelectionRange(newPos, newPos);
  hideMentionDropdown();
  updateGroupSendBtn();
}

// ============ Agent background task stream ============
function disconnectAgentEvents() {
  if (S.agentEventSource) {
    S.agentEventSource.close();
    S.agentEventSource = null;
  }
}

function ensureAgentTaskBlock(agentId) {
  const live = S.agentTaskBlocks[agentId];
  if (live?.el?.isConnected) return live;

  const msg = { role: 'agent', content: '', thinking: [], ts: Date.now(), background: true };
  if (!S.agentMessages[agentId]) S.agentMessages[agentId] = [];
  S.agentMessages[agentId].push(msg);

  let el = null;
  if (S.currentAgentId === agentId) {
    el = renderAgentMsg(msg, DOM.messages, agentId);
    scrollBottom(DOM.messages);
  }
  S.agentTaskBlocks[agentId] = { msg, el };
  return S.agentTaskBlocks[agentId];
}

function handleAgentBackgroundEvent(ev) {
  if (!ev || !ev.event) return;
  const agentId = ev.data?.agent_id || S.currentAgentId;
  if (!agentId) return;

  // 已删除的 agent 收到后台消息 → 自动恢复
  if (S.hiddenAgents.has(agentId)) {
    fetch(`/api/chat/${encodeURIComponent(agentId)}/restore`, { method: 'POST' }).catch(() => {});
    S.hiddenAgents.delete(agentId);
    renderAgentList();
  }

  if (S.currentAgentId !== agentId) return;

  switch (ev.event) {
    case 'agent_thinking': {
      const block = ensureAgentTaskBlock(agentId);
      if (!block.el && S.currentAgentId === agentId) {
        block.el = renderAgentMsg(block.msg, DOM.messages, agentId);
      }
      const el = block.el;
      if (!el) return;
      const tb = el.querySelector('.thinking-body');
      const ts = el.querySelector('.thinking-section');
      const ce = el.querySelector('.msg-content');
      handleThinking(ev.data, block.msg, ce, tb, ts, el);
      if (document.querySelector('.nav-tab.active')?.dataset.tab === 'chat') renderAgentList();
      break;
    }
    case 'agent_done':
      delete S.agentTaskBlocks[agentId];
      break;
    case 'error':
      if (S.currentAgentId === agentId) {
        renderAgentMsg({ role: 'agent', content: `❌ ${ev.data?.message || '错误'}`, ts: Date.now() }, DOM.messages, agentId);
      }
      break;
  }
}

function connectAgentEvents(agentId) {
  disconnectAgentEvents();
  if (!agentId) return;
  const es = new EventSource(`/api/agents/${encodeURIComponent(agentId)}/events`);
  S.agentEventSource = es;
  es.onmessage = (e) => {
    if (!e.data || e.data === '[DONE]') return;
    try { handleAgentBackgroundEvent(JSON.parse(e.data)); } catch (err) { console.warn('agent event parse:', err); }
  };
  es.onerror = () => {
    disconnectAgentEvents();
    setTimeout(() => {
      if (S.currentAgentId === agentId) connectAgentEvents(agentId);
    }, 3000);
  };
}

// ============ Group Chat ============
function disconnectGroupEvents() {
  if (S.groupEventSource) {
    S.groupEventSource.close();
    S.groupEventSource = null;
  }
}

function handleGroupStreamEvent(ev) {
  if (!ev || !ev.event) return;
  const now = Date.now();
  if (S.currentGroupId) S.groupActivityTs[S.currentGroupId] = now;
  // 已解散的群收到消息 → 自动恢复
  if (ev.data?.group_id && S.currentGroupId && ev.data.group_id === S.currentGroupId) {
    const g = S.groups.find(x => x.id === S.currentGroupId);
    if (g && g.status === 'dissolved') {
      fetch(`/api/groups/${S.currentGroupId}/restore`, { method: 'POST' }).catch(() => {});
      g.status = 'active';
    }
  }
  switch (ev.event) {
    case 'group_message':
      if (ev.data?.sender && ev.data.sender !== 'user') {
        renderGroupMsg({ sender: ev.data.sender, text: ev.data.text, id: ev.data.msg_id || `m_${Date.now()}` });
      }
      break;
    case 'routing':
      renderGroupMsg({ sender: 'system', text: `🔄 路由到 @${ev.data.to}...`, id: `r_${Date.now()}` });
      break;
    case 'agent_thinking':
      handleGroupThinking(ev.data);
      break;
    case 'agent_done':
      renderGroupMsg({ sender: 'system', text: `✅ @${ev.data.agent_id} 已完成`, id: `d_${Date.now()}` });
      break;
    case 'error':
      renderGroupMsg({ sender: 'system', text: `❌ ${ev.data.message}`, id: `e_${Date.now()}` });
      break;
  }
}

function connectGroupEvents(groupId) {
  disconnectGroupEvents();
  if (!groupId) return;
  const es = new EventSource(`/api/groups/${encodeURIComponent(groupId)}/events`);
  S.groupEventSource = es;
  es.onmessage = (e) => {
    if (!e.data || e.data === '[DONE]') return;
    try { handleGroupStreamEvent(JSON.parse(e.data)); } catch (err) { console.warn('group event parse:', err); }
  };
  es.onerror = () => {
    disconnectGroupEvents();
    setTimeout(() => {
      if (S.currentGroupId === groupId) connectGroupEvents(groupId);
    }, 3000);
  };
}

async function sendGroupMsg() {
  const text = DOM['group-input'].value.trim();
  if (!text || S.isStreaming || !S.currentGroupId) return;

  // Show user message
  const uMsg = { sender:'user', text, id:`m_${Date.now()}` };
  renderGroupMsg(uMsg);
  DOM['group-input'].value = ''; DOM['group-input'].style.height = 'auto';
  S.isStreaming = true; setStatus('busy');
  updateGroupSendBtn();

  try {
    S.abortCtrl = new AbortController();
    S.streamContext = { mode: 'group', userText: text };
    const resp = await fetch(`/api/groups/${S.currentGroupId}/chat?sender=user&text=${encodeURIComponent(text)}`, { signal: S.abortCtrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    S.currentReader = reader;
    const dec = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        const t = line.trim();
        if (!t || t === 'data: [DONE]') continue;
        if (!t.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(t.slice(6));
          handleGroupStreamEvent(ev);
        } catch(e) {}
      }
    }
  } catch(e) {
    if (e.name === 'AbortError') {
      rollbackGroupTurn(text);
    } else {
      renderGroupMsg({ sender:'system', text:`错误: ${e.message}`, id:`e_${Date.now()}` });
    }
  } finally {
    S.currentReader = null;
    S.streamContext = null;
    S.isStreaming = false; setStatus('online');
    updateGroupSendBtn();
  }
}

function handleGroupThinking(data) {
  let block = document.getElementById(`gt-${data.agent_id}`);
  if (!block) {
    const div = document.createElement('div');
    div.className = 'message agent';
    div.id = `gt-${data.agent_id}`;
    div.innerHTML = `<div class="msg-header"><span class="msg-agent-icon">${getAvatar(data.agent_id)}</span>${esc(data.agent_id)}</div>
      <div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">Agent 活动</span></div><div class="thinking-body"></div></div>
      <div class="msg-content"></div>`;
    DOM['group-messages'].appendChild(div);
    block = div;
    scrollBottom(DOM['group-messages']);
  }

  const tb = block.querySelector('.thinking-body');
  const ce = block.querySelector('.msg-content');
  const ts = block.querySelector('.thinking-section');
  if (!tb || !ce) return;

  if (data.type === 'text') {
    block.__bubbleText = normalizeBubbleText((block.__bubbleText || '') + (data.content || ''));
    renderBubbleMarkdown(ce, block.__bubbleText);
  } else {
    if (ts) ts.style.display = '';
    const fakeMsg = block.__actMsg || (block.__actMsg = { thinking: [], __step: 0 });
    appendThinkingEvent(fakeMsg, tb, data);
    updateThinkingHeader(ts, fakeMsg, true);
  }
  scrollBottom(DOM['group-messages']);
}

function renderGroupMsg(msg, container) {
  if (S.currentGroupId) {
    S.groupActivityTs[S.currentGroupId] = Date.now();
    if (document.querySelector('.nav-tab.active')?.dataset.tab === 'groups') renderGroupList();
  }
  const c = container || DOM['group-messages'];
  const div = document.createElement('div');

  if (msg.sender === 'user') {
    div.className = 'message group-user';
    div.innerHTML = `<div class="msg-header">你</div><div class="msg-content">${esc(msg.text)}</div>`;
  } else if (msg.sender === 'system') {
    div.className = 'message system';
    div.innerHTML = esc(msg.text || '').replace(/\n/g, '<br>');
  } else {
    // Agent message
    const aId = msg.sender;
    div.className = 'message group-agent';
    div.innerHTML = `<div class="msg-header"><span class="msg-agent-icon">${getAvatar(aId)}</span>@${esc(aId)}</div><div class="msg-content"></div>`;
    const ce = div.querySelector('.msg-content');
    // 通报消息包含 📋 → 保留换行；否则用 markdown
    if ((msg.text || '').includes('📋')) {
      ce.innerHTML = esc(msg.text || '').replace(/\n/g, '<br>');
    } else {
      renderBubbleMarkdown(ce, msg.text || '');
    }
  }
  c.appendChild(div);
  scrollBottom(c);
  return div;
}

// ============ Agent Config Modal ============
async function openAgentConfig() {
  if (!S.currentAgentId) return;
  const a = S.agents.find(x => x.id === S.currentAgentId);
  if (!a) return;
  DOM['modal-agent-info'].textContent = `${a.name} (${a.id})`;

  // Populate backend select
  const bSel = DOM['modal-backend'];
  bSel.innerHTML = S.backends.map(b => `<option value="${b.id}" ${b.id === a.backend ? 'selected' : ''}>${b.name}</option>`).join('');
  updateModalModels(bSel.value, a.model);

  bSel.onchange = () => updateModalModels(bSel.value);
  DOM.modalSave = () => saveAgentConfig();

  DOM['modal-overlay'].classList.remove('hidden');
}

function updateModalModels(backendId, selectedModel) {
  const models = getBackendModels(backendId);
  const mSel = DOM['modal-model'];
  mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.id === selectedModel || (!selectedModel && m.default) ? 'selected' : ''}>${m.name} (${m.provider||''})</option>`).join('');
}

async function saveAgentConfig() {
  if (!S.currentAgentId) return;
  const backend = DOM['modal-backend'].value;
  const model = DOM['modal-model'].value;
  try {
    await fetch(`/api/agents/${S.currentAgentId}/config`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ backend, model }),
    });
    await loadAgents();
    renderAgentList();
    selectAgent(S.currentAgentId);
    DOM['modal-overlay'].classList.add('hidden');
  } catch(e) { alert('保存失败: '+e.message); }
}

// ============ Group Config Modal ============
async function openGroupConfig() {
  if (!S.currentGroupId) return;
  const r = await fetch(`/api/groups/${S.currentGroupId}`);
  const d = await r.json();
  const g = d.group;
  DOM['group-modal-name'].textContent = g.name;
  DOM['group-modal-members'].innerHTML = (g.members||[]).map(m =>
    `<span class="member-tag">${esc(m)} <button class="member-remove" data-agent="${m}">✕</button></span>`
  ).join('') || '<span style="color:var(--text3);font-size:12px">暂无成员</span>';

  DOM['group-modal-members'].querySelectorAll('.member-remove').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/groups/${S.currentGroupId}/members/${btn.dataset.agent}`, { method: 'DELETE' });
      openGroupConfig();
      loadGroups();
      renderGroupList();
    });
  });
  populateGroupMemberSelect();
  DOM['group-config-modal'].classList.remove('hidden');
}

async function populateGroupMemberSelect() {
  const sel = DOM['group-add-agent'];
  if (!sel) return;
  await loadAgents();
  // Show only agents NOT already in the group
  const groupId = S.currentGroupId;
  let members = [];
  try {
    const r = await fetch(`/api/groups/${groupId}`);
    const d = await r.json();
    members = d.members || [];
  } catch(e) {}
  const available = S.agents.filter(a => !members.includes(a.id));
  sel.innerHTML = available.map(a => `<option value="${a.id}">${a.name} (${a.id})</option>`).join('');
  sel.size = Math.min(available.length || 1, 8);
}

// ============ Agent Factory ============
function resetCreateForm() {
  DOM['cf-description'].value = '';
  DOM['cf-agent-id'].value = '';
  DOM['cf-name'].value = '';
  DOM['cf-result'].classList.add('hidden');
  DOM['cf-result'].querySelector('.result-details').innerHTML = '';
  showFormStatus('', '');
  DOM['cf-submit'].disabled = false;
  DOM['cf-submit'].textContent = '🚀 创建 Agent';
}

async function openCreateModal() {
  await loadBackends();
  resetCreateForm();
  populateCreateForm();
  DOM['create-agent-modal'].classList.remove('hidden');
}

function closeCreateModal() {
  DOM['create-agent-modal'].classList.add('hidden');
}

function populateCreateForm() {
  const bSel = DOM['cf-backend'];
  bSel.innerHTML = S.backends.map(b => `<option value="${b.id}">${b.name}</option>`).join('');
  updateCreateModels(bSel.value);
  bSel.onchange = () => updateCreateModels(bSel.value);
  DOM['cf-description'].oninput = () => {
    const desc = DOM['cf-description'].value.trim();
    if (desc.length > 5) suggestId(desc);
  };
}

function updateCreateModels(backendId) {
  const models = getBackendModels(backendId);
  const mSel = DOM['cf-model'];
  mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.default?'selected':''}>${m.name}</option>`).join('');
}

async function suggestId(desc) {
  try {
    const r = await fetch(`/api/agents/suggest-id?description=${encodeURIComponent(desc)}`);
    const d = await r.json();
    if (!DOM['cf-agent-id'].value) DOM['cf-agent-id'].value = d.suggested_id;
  } catch(e) {}
}

function showFormStatus(msg, type) {
  const s = DOM['cf-status'];
  s.textContent = msg;
  s.className = 'form-status';
  if (msg) { s.style.display = 'block'; if (type) s.classList.add(type); }
  else s.style.display = 'none';
}

// ============ Agent Management ============
async function renderManageAgents() {
  await loadAgents();
  await loadBackends();
  DOM['manage-agent-count'].textContent = S.agents.length;

  if (!S.agents.length) {
    DOM['manage-agent-table'].innerHTML = '<div class="empty">暂无 Agent，点击右上角「创建 Agent」开始</div>';
    return;
  }

  const rows = S.agents.map(a => {
    return `<tr data-id="${esc(a.id)}">
      <td><div class="agent-cell"><span class="icon">${getAvatar(a.id)}</span><span><strong>${esc(a.name)}</strong><br><span style="color:var(--text3);font-size:11px">${esc(a.id)}</span></span></div></td>
      <td><span style="font-size:12px">${esc(a.backend)}</span></td>
      <td><span style="font-size:11px;color:var(--text2)">${esc(a.model||'').slice(0,30)}</span></td>
      <td><span style="font-size:10px;color:var(--text3);word-break:break-all">${esc(a.workspace||'')}</span></td>
      <td style="text-align:right;white-space:nowrap">
        <button class="btn-xs primary am-config">配置</button>
        <button class="btn-xs danger am-del">删除</button>
      </td>
    </tr>`;
  }).join('');

  DOM['manage-agent-table'].innerHTML = `<table class="manage-table">
    <thead><tr><th>Agent</th><th>后端</th><th>模型</th><th>工作目录</th><th style="text-align:right">操作</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;

  // Bind events - "配置" button opens modal
  DOM['manage-agent-table'].querySelectorAll('.am-config').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tr = e.target.closest('tr');
      openManageModal(tr.dataset.id);
    });
  });

  // Delete button
  DOM['manage-agent-table'].querySelectorAll('.am-del').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const tr = e.target.closest('tr');
      const id = tr.dataset.id;
      if (!confirm(`确认删除 Agent「${id}」？将删除工作目录和配置。`)) return;
      try {
        const r = await fetch(`/api/agents/${id}`, { method: 'DELETE' });
        if (!r.ok) { const d = await r.json(); throw new Error(d.detail); }
        await loadAgents();
        renderManageAgents();
      } catch(e) { alert('删除失败: '+e.message); }
    });
  });
}

async function renderTaskTypes() {
  const box = DOM['manage-tasktype-table'];
  if (!box) return;
  try {
    const r = await fetch('/api/obs/task-types');
    const items = (await r.json()).task_types || [];
    DOM['manage-tasktype-count'].textContent = items.length;
    if (!items.length) { box.innerHTML = '<div class="empty">暂无任务类型</div>'; return; }
    box.innerHTML = `<table class="manage-table">
      <thead><tr><th>类型</th><th>产出</th><th>必需章节</th><th>章节数</th></tr></thead>
      <tbody>${items.map(t => `<tr>
        <td><code>${esc(t.task_type)}</code></td>
        <td>${esc(t.outcome_kind)}</td>
        <td>${(t.required_sections || []).map(s => `<span class="chip">${esc(s)}</span>`).join(' ') || '—'}</td>
        <td>${t.section_count}</td></tr>`).join('')}</tbody></table>`;
  } catch(e) { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
}

async function renderMemory() {
  const box = DOM['manage-memory-table'];
  if (!box) return;
  try {
    const r = await fetch('/api/obs/memory');
    const data = await r.json();
    const items = data.memory || [];
    DOM['manage-memory-count'].textContent = data.total ?? items.length;
    if (!items.length) { box.innerHTML = '<div class="empty">暂无知识库条目</div>'; return; }
    box.innerHTML = `<table class="manage-table">
      <thead><tr><th>标题</th><th>项目</th><th>标签</th><th>预览</th></tr></thead>
      <tbody>${items.map(m => `<tr>
        <td>${esc(m.title || '')}</td>
        <td><code>${esc(m.project_id || '')}</code></td>
        <td>${(m.tags || []).map(t => `<span class="chip">${esc(t)}</span>`).join(' ') || '—'}</td>
        <td class="hint">${esc(m.preview || '')}</td></tr>`).join('')}</tbody></table>`;
  } catch(e) { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
}

function openManageModal(agentId) {
  const a = S.agents.find(x => x.id === agentId);
  if (!a) return;
  DOM['mm-id'].value = a.id;
  DOM['mm-name'].value = a.name;
  DOM['mm-workspace'].value = a.workspace;

  const bSel = DOM['mm-backend'];
  bSel.innerHTML = S.backends.map(b =>
    `<option value="${b.id}" ${b.id === a.backend ? 'selected' : ''}>${b.name}</option>`
  ).join('');

  updateManageModels(a.backend, a.model);
  bSel.onchange = () => updateManageModels(bSel.value);

  DOM['mm-status'].style.display = 'none';
  DOM['manage-modal'].classList.remove('hidden');
}

function updateManageModels(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['mm-model'];
  mSel.innerHTML = models.map(m =>
    `<option value="${m.id}" ${m.id === selected ? 'selected' : ''}>${m.name}</option>`
  ).join('');
}

async function saveManageModal() {
  const id = DOM['mm-id'].value;
  const name = DOM['mm-name'].value.trim();
  const backend = DOM['mm-backend'].value;
  const model = DOM['mm-model'].value;
  const workspace = DOM['mm-workspace'].value.trim();
  const status = DOM['mm-status'];

  if (!name) { status.textContent = '名称不能为空'; status.className = 'form-status error'; status.style.display = 'block'; return; }

  try {
    const r = await fetch(`/api/agents/${id}/manage`, {
      method: 'PUT', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name, backend, model, workspace }),
    });
    if (!r.ok) throw new Error('保存失败');
    status.textContent = '✓ 已保存'; status.className = 'form-status success'; status.style.display = 'block';
    await loadAgents();
    renderManageAgents();
    setTimeout(() => { DOM['manage-modal'].classList.add('hidden'); }, 800);
  } catch(e) {
    status.textContent = '保存失败: '+e.message; status.className = 'form-status error'; status.style.display = 'block';
  }
}

// ============ System Settings ============
async function loadSettings() {
  await loadBackends();
  try {
    const [rSys, rSkill] = await Promise.all([
      fetch('/api/config'),
      fetch('/api/skill-config'),
    ]);
    const cfg = (await rSys.json()).config || {};
    const skillCfg = (await rSkill.json()).config || {};

    const defBackend = cfg.system?.default_backend || 'opencode';
    const bSel = DOM['set-default-backend'];
    bSel.innerHTML = S.backends.map(b =>
      `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`
    ).join('');

    const defModel = cfg.system?.default_model || '';
    updateDefaultModelSelect(defBackend, defModel);
    bSel.onchange = () => updateDefaultModelSelect(bSel.value);

    DOM['set-port'].value = cfg.system?.port || 8765;
    DOM['set-cli-path'].value = cfg.backends?.opencode?.cli_path || '';
    DOM['set-debug'].checked = !!cfg.system?.debug;
    DOM['set-model-aliases'].value = JSON.stringify(cfg.backends?.opencode?.model_aliases || {}, null, 2);

    DOM['set-use-project-group'].checked = skillCfg.notifications?.use_project_group !== false;
    DOM['set-auto-group'].checked = skillCfg.auto_group?.enabled !== false;
    DOM['set-hub-url'].value = skillCfg.hub?.url || 'http://127.0.0.1:8765';
    DOM['set-poll-interval'].value = skillCfg.executor?.poll_interval ?? 5;
    DOM['set-ack-timeout'].value = skillCfg.executor?.ack_timeout ?? 300;
    DOM['set-task-timeout'].value = skillCfg.executor?.task_timeout ?? 3600;
    DOM['set-agent-msg-timeout'].value = skillCfg.executor?.agent_msg_timeout ?? 1800;
    DOM['set-team-config-timeout'].value = skillCfg.executor?.team_config_timeout ?? 600;
    DOM['set-task-plan-timeout'].value = skillCfg.executor?.task_plan_timeout ?? 600;
    DOM['set-max-retries'].value = skillCfg.executor?.max_retries ?? 3;
  } catch(e) { showSetStatus('加载配置失败: '+e.message, 'error'); }
}

function updateDefaultModelSelect(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['set-default-model'];
  mSel.innerHTML = models.map(m =>
    `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`
  ).join('');
}

async function applyModelToAll() {
  const backend = DOM['set-default-backend'].value;
  const model = DOM['set-default-model'].value;
  if (!model) { showSetStatus('请先选择模型', 'error'); return; }
  if (!confirm(`把后端「${backend}」下的所有 agent 模型都改成：\n${model}\n\n（其它后端的 agent 不受影响）`)) return;
  try {
    const r = await fetch('/api/agents/apply-model', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ backend, model }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '应用失败');
    showSetStatus(`✓ 已应用到 ${d.applied.length} 个 agent，跳过 ${d.skipped.length} 个（非 ${backend}）`, 'success');
  } catch(e) { showSetStatus('应用失败: '+e.message, 'error'); }
}

async function saveSettings() {
  const backend = DOM['set-default-backend'].value;
  const model = DOM['set-default-model'].value;
  const port = parseInt(DOM['set-port'].value) || 8765;
  const cliPath = (DOM['set-cli-path']?.value || '').trim();
  let aliases = {};
  try {
    aliases = JSON.parse(DOM['set-model-aliases'].value || '{}');
  } catch(e) {
    showSetStatus('模型别名 JSON 格式错误', 'error');
    return;
  }

  try {
    const r0 = await fetch('/api/config');
    const cfg = (await r0.json()).config || {};

    cfg.system = cfg.system || {};
    cfg.system.default_backend = backend;
    cfg.system.default_model = model;
    cfg.system.port = port;
    cfg.system.debug = !!DOM['set-debug']?.checked;
    cfg.backends = cfg.backends || {};
    cfg.backends.opencode = cfg.backends.opencode || {};
    cfg.backends.opencode.model_aliases = aliases;
    cfg.backends.opencode.cli_path = cliPath;

    const allModels = getBackendModels(backend);
    cfg.models = cfg.models || {};
    cfg.models[backend] = allModels.map(m => ({
      id: m.id, name: m.name, provider: m.provider, default: m.id === model,
    }));

    const rSkill0 = await fetch('/api/skill-config');
    const existingSkill = (await rSkill0.json()).config || {};

    const skillCfg = {
      ...existingSkill,
      notifications: {
        ...(existingSkill.notifications || {}),
        enable_telegram: false,
        use_project_group: DOM['set-use-project-group']?.checked !== false,
      },
      hub: { ...(existingSkill.hub || {}), url: (DOM['set-hub-url']?.value || '').trim() || 'http://127.0.0.1:8765' },
      executor: {
        ...(existingSkill.executor || {}),
        poll_interval: parseInt(DOM['set-poll-interval']?.value) || 5,
        ack_timeout: parseInt(DOM['set-ack-timeout']?.value) || 300,
        task_timeout: parseInt(DOM['set-task-timeout']?.value) || 3600,
        agent_msg_timeout: parseInt(DOM['set-agent-msg-timeout']?.value) || 1800,
        team_config_timeout: parseInt(DOM['set-team-config-timeout']?.value) || 600,
        task_plan_timeout: parseInt(DOM['set-task-plan-timeout']?.value) || 600,
        max_retries: parseInt(DOM['set-max-retries']?.value) || 3,
      },
      auto_group: {
        ...(existingSkill.auto_group || {}),
        enabled: DOM['set-auto-group']?.checked !== false,
        include_main: existingSkill.auto_group?.include_main !== false,
        name_prefix: existingSkill.auto_group?.name_prefix ?? '',
      },
    };

    const [rSys, rSkill] = await Promise.all([
      fetch('/api/config', {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ config: cfg }),
      }),
      fetch('/api/skill-config', {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ config: skillCfg }),
      }),
    ]);
    if (!rSys.ok || !rSkill.ok) throw new Error('保存失败');
    showSetStatus('✓ 已保存（端口变更需重启 Hub）', 'success');
  } catch(e) {
    showSetStatus('保存失败: '+e.message, 'error');
  }
}

function showSetStatus(msg, type) {
  const s = DOM['set-status'];
  s.textContent = msg;
  s.className = 'form-status';
  if (msg) { s.style.display = 'block'; if (type) s.classList.add(type); }
  else s.style.display = 'none';
}

// ============ Utilities ============
function loadChatHistory() {
  try {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data && typeof data === 'object') S.agentMessages = data;
  } catch (e) {
    console.warn('loadChatHistory:', e);
    S.agentMessages = {};
  }
}

function saveChatHistory() {
  try {
    const cleaned = {};
    for (const [id, msgs] of Object.entries(S.agentMessages)) {
      cleaned[id] = (msgs || []).slice(-CHAT_HISTORY_MAX).map(m => {
        const copy = { ...m };
        delete copy.__curStep;
        delete copy.__stepIdx;
        return copy;
      });
    }
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(cleaned));
  } catch (e) {
    console.warn('saveChatHistory:', e);
  }
}

function addAgentMsg(id, msg) {
  if (!S.agentMessages[id]) S.agentMessages[id] = [];
  S.agentMessages[id].push(msg);
  if (S.agentMessages[id].length > CHAT_HISTORY_MAX) {
    S.agentMessages[id] = S.agentMessages[id].slice(-CHAT_HISTORY_MAX);
  }
  saveChatHistory();
  if (document.querySelector('.nav-tab.active')?.dataset.tab === 'chat') renderAgentList();
}

function rollbackAgentTurn(userText, agentEl) {
  const msgs = S.agentMessages[S.currentAgentId];
  if (msgs?.length >= 2 && msgs[msgs.length - 1].role === 'agent') {
    msgs.pop();
    if (msgs[msgs.length - 1]?.role === 'user') msgs.pop();
  }
  const userEl = agentEl?.previousElementSibling;
  if (userEl?.classList.contains('user')) userEl.remove();
  agentEl?.remove();
  DOM['message-input'].value = userText;
  DOM['message-input'].style.height = 'auto';
  saveChatHistory();
}

function rollbackGroupTurn(userText) {
  const users = DOM['group-messages']?.querySelectorAll('.message.group-user');
  users?.[users.length - 1]?.remove();
  DOM['group-messages']?.querySelectorAll('[id^="gt-"]').forEach(el => el.remove());
  renderGroupMsg({ sender:'system', text:'⏹ 已中断', id:`x_${Date.now()}` });
  DOM['group-input'].value = userText;
  DOM['group-input'].style.height = 'auto';
}

function cancelActiveStream() {
  if (!S.isStreaming) return;
  stopStream();
}

function stopStream() {
  if (S.abortCtrl) {
    S.abortCtrl.abort();
    S.abortCtrl = null;
  }
  if (S.currentReader) {
    S.currentReader.cancel().catch(() => {});
    S.currentReader = null;
  }
}

function setSendBtnMode(btn, streaming, hasText, enabled) {
  if (!btn) return;
  if (streaming) {
    btn.disabled = false;
    btn.textContent = '停止';
    btn.classList.add('stop-mode');
    return;
  }
  btn.classList.remove('stop-mode');
  btn.textContent = '发送';
  btn.disabled = !hasText || !enabled;
}

function setStatus(s) {
  const badge = DOM['status-badge'];
  badge.className = `status ${s}`;
  badge.textContent = s === 'online' ? '就绪' : s === 'busy' ? '处理中' : '离线';
}

function updateSendBtn() {
  setSendBtnMode(
    DOM['btn-send'],
    S.isStreaming,
    !!DOM['message-input'].value.trim(),
    !!S.currentAgentId,
  );
}

function updateGroupSendBtn() {
  setSendBtnMode(
    DOM['btn-group-send'],
    S.isStreaming,
    !!DOM['group-input'].value.trim(),
    !!S.currentGroupId,
  );
}

function scrollBottom(el) {
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

function removeTyping(el) {
  const td = el?.querySelector('.typing-dots');
  if (td) td.style.display = 'none';
}

async function clearChat() {
  if (!S.currentAgentId) return;
  if (S.isStreaming) cancelActiveStream();
  const ok = confirm(
    '清空后将删除：\n\n' +
    '· 本页所有对话记录（浏览器本地）\n' +
    '· Agent 多轮上下文（OpenCode Session）\n\n' +
    '下次对话 Agent 不会记得之前聊过什么。'
  );
  if (!ok) return;

  try {
    const r = await fetch(`/api/chat/${S.currentAgentId}/clear`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || d.message || `HTTP ${r.status}`);
  } catch (e) {
    alert('清空失败: ' + e.message);
    return;
  }

  S.agentMessages[S.currentAgentId] = [];
  DOM.messages.innerHTML = '';
  saveChatHistory();
  DOM['message-input'].focus();
}

async function clearGroupChat() {
  if (!S.currentGroupId) return;
  if (S.isStreaming) cancelActiveStream();
  const ok = confirm(
    '清空后将删除本群组的所有消息记录。\n\n' +
    '说明：各 Agent 的私聊上下文需在对应 Agent 对话里单独清空。'
  );
  if (!ok) return;

  try {
    const r = await fetch(`/api/groups/${S.currentGroupId}/clear`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || d.message || `HTTP ${r.status}`);
  } catch (e) {
    alert('清空失败: ' + e.message);
    return;
  }

  DOM['group-messages'].innerHTML = '';
}

// ============ Event Listeners ============
function setupEventListeners() {
  // Agent chat
  DOM['btn-send'].addEventListener('click', () => {
    if (S.isStreaming) cancelActiveStream();
    else sendAgentMsg();
  });
  DOM['message-input'].addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (S.isStreaming) cancelActiveStream();
      else sendAgentMsg();
    }
  });
  DOM['message-input'].addEventListener('input', () => {
    DOM['message-input'].style.height = 'auto';
    DOM['message-input'].style.height = Math.min(DOM['message-input'].scrollHeight, 120) + 'px';
    updateSendBtn();
  });
  DOM['btn-clear-chat'].addEventListener('click', clearChat);
  DOM['btn-delete-chat']?.addEventListener('click', () => deleteChatWindow());
  DOM['btn-agent-config'].addEventListener('click', openAgentConfig);
  DOM['agent-search']?.addEventListener('input', e => searchChatArchives(e.target.value));
  DOM['agent-search']?.addEventListener('blur', () => setTimeout(() => hideSearchResults('agent'), 200));

  // Group chat
  DOM['btn-group-send'].addEventListener('click', () => {
    if (S.isStreaming) cancelActiveStream();
    else sendGroupMsg();
  });
  DOM['group-input'].addEventListener('keydown', e => {
    if (S.mentionActive) {
      const dd = DOM['mention-dropdown'];
      const items = dd ? dd.querySelectorAll('.mention-item') : [];
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        S.mentionIdx = Math.min(S.mentionIdx + 1, items.length - 1);
        items.forEach((el, i) => el.classList.toggle('active', i === S.mentionIdx));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        S.mentionIdx = Math.max(S.mentionIdx - 1, 0);
        items.forEach((el, i) => el.classList.toggle('active', i === S.mentionIdx));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (items[S.mentionIdx]) insertMention(items[S.mentionIdx].dataset.id);
        return;
      }
      if (e.key === 'Escape') { hideMentionDropdown(); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendGroupMsg(); }
  });
  DOM['group-input'].addEventListener('input', () => {
    DOM['group-input'].style.height = 'auto';
    DOM['group-input'].style.height = Math.min(DOM['group-input'].scrollHeight, 120) + 'px';
    updateGroupSendBtn();
    // @mention detection
    const val = DOM['group-input'].value;
    const pos = DOM['group-input'].selectionStart;
    const beforeCursor = val.slice(0, pos);
    const atIdx = beforeCursor.lastIndexOf('@');
    if (atIdx >= 0 && (atIdx === 0 || beforeCursor[atIdx - 1] === ' ' || beforeCursor[atIdx - 1] === '\n')) {
      const filter = beforeCursor.slice(atIdx + 1);
      if (!filter.includes(' ')) showMentionDropdown(filter);
      else hideMentionDropdown();
    } else {
      hideMentionDropdown();
    }
  });
  DOM['btn-clear-group'].addEventListener('click', clearGroupChat);
  DOM['btn-dissolve-group']?.addEventListener('click', dissolveGroupWindow);
  DOM['btn-group-config'].addEventListener('click', openGroupConfig);
  DOM['group-search']?.addEventListener('input', e => searchGroupsArchive(e.target.value));
  DOM['group-search']?.addEventListener('blur', () => setTimeout(() => hideSearchResults('group'), 200));

  // Agent Config Modal
  DOM['modal-save'].addEventListener('click', saveAgentConfig);
  DOM['modal-cancel'].addEventListener('click', () => DOM['modal-overlay'].classList.add('hidden'));
  DOM['modal-overlay'].querySelector('.modal-close')?.addEventListener('click', () => DOM['modal-overlay'].classList.add('hidden'));

  // Group Config Modal
  DOM['btn-add-member']?.addEventListener('click', async () => {
    const sel = DOM['group-add-agent'];
    if (!sel || !S.currentGroupId) return;
    const selected = Array.from(sel.selectedOptions).map(o => o.value);
    if (!selected.length) return;
    for (const agentId of selected) {
      await fetch(`/api/groups/${S.currentGroupId}/members`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ agent_id: agentId }),
      });
    }
    openGroupConfig();
    loadGroups();
    renderGroupList();
  });
  DOM['group-modal-close']?.addEventListener('click', () => DOM['group-config-modal'].classList.add('hidden'));
  DOM['group-config-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['group-config-modal'].classList.add('hidden'));

  // New Group Modal
  DOM['btn-new-group']?.addEventListener('click', () => DOM['new-group-modal'].classList.remove('hidden'));
  DOM['ng-submit']?.addEventListener('click', async () => {
    const name = DOM['ng-name'].value.trim();
    if (!name) return;
    await fetch('/api/groups', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name, description: DOM['ng-desc'].value.trim() }),
    });
    DOM['new-group-modal'].classList.add('hidden');
    DOM['ng-name'].value = '';
    DOM['ng-desc'].value = '';
    await loadGroups();
    renderGroupList();
    switchTab('groups');
  });
  DOM['ng-cancel']?.addEventListener('click', () => DOM['new-group-modal'].classList.add('hidden'));
  DOM['new-group-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['new-group-modal'].classList.add('hidden'));

  // New project (发起项目 → 编排内核)
  const openNewProject = () => { DOM['new-project-modal'].classList.remove('hidden'); DOM['np-goal']?.focus(); };
  const closeNewProject = () => DOM['new-project-modal'].classList.add('hidden');
  DOM['btn-new-project']?.addEventListener('click', openNewProject);
  DOM['btn-new-project-welcome']?.addEventListener('click', openNewProject);
  DOM['np-cancel']?.addEventListener('click', closeNewProject);
  DOM['new-project-modal']?.querySelector('.modal-close')?.addEventListener('click', closeNewProject);
  DOM['btn-cancel-project']?.addEventListener('click', async () => {
    const id = S.currentProjectId;
    if (!id) return;
    if (!confirm('取消该项目？当前正在执行的任务会跑完，之后不再派发新任务。')) return;
    try {
      const r = await fetch(`/api/projects/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || '取消失败');
      await refreshProjectDetail(id);
    } catch (e) {
      alert('取消失败：' + (e.message || e));
    }
  });
  DOM['np-submit']?.addEventListener('click', async () => {
    const goal = DOM['np-goal'].value.trim();
    if (!goal) return;
    const payload = {
      goal,
      title: DOM['np-title'].value.trim(),
      mode: DOM['np-mode'].value,
    };
    const budget = parseInt(DOM['np-budget'].value, 10);
    if (!isNaN(budget) && budget > 0) payload.budget = budget;
    if (DOM['np-review']?.checked) payload.review = true;
    DOM['np-submit'].disabled = true;
    try {
      const r = await fetch('/api/projects/run', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || '发起失败');
      closeNewProject();
      DOM['np-goal'].value = ''; DOM['np-title'].value = ''; DOM['np-budget'].value = '';
      await loadProjects();
      renderProjectList();
      switchTab('projects');
      selectProject(d.project_id);
    } catch (e) {
      alert('发起项目失败：' + (e.message || e));
    } finally {
      DOM['np-submit'].disabled = false;
    }
  });

  // Settings save
  DOM['btn-save-settings']?.addEventListener('click', saveSettings);
  DOM['btn-apply-model-all']?.addEventListener('click', applyModelToAll);

  // Manage modal
  DOM['mm-save']?.addEventListener('click', saveManageModal);
  DOM['mm-cancel']?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));
  DOM['manage-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));

  // Create agent modal
  DOM['btn-create-agent']?.addEventListener('click', openCreateModal);
  DOM['cf-cancel']?.addEventListener('click', closeCreateModal);
  DOM['create-agent-modal']?.querySelector('.modal-close')?.addEventListener('click', closeCreateModal);

  // Agent Factory (create agent form)
  DOM['cf-submit'].addEventListener('click', async (e) => {
    e.preventDefault();
    const desc = DOM['cf-description'].value.trim();
    if (!desc) { showFormStatus('请输入 Agent 描述', 'error'); return; }
    const aid = DOM['cf-agent-id'].value.trim();
    if (!aid) { showFormStatus('请输入 Agent ID', 'error'); return; }

    DOM['cf-submit'].disabled = true;
    DOM['cf-submit'].textContent = '创建中...';
    showFormStatus('', '');

    try {
      const r = await fetch('/api/agents/create', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          description: desc,
          agent_id: aid,
          chinese_name: DOM['cf-name'].value.trim(),
          backend: DOM['cf-backend'].value,
          model: DOM['cf-model'].value,
        }),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
      const d = await r.json();
      const a = d.agent;
      DOM['cf-result'].classList.remove('hidden');
      DOM['cf-result'].querySelector('.result-details').innerHTML =
        `<div>📁 工作目录: ${esc(a.workspace)}</div>
         <div>📝 文件: ${(a.files||[]).join(', ')}</div>
         <div>⚙️ 后端: ${a.backend} / ${a.model}</div>`;
      showFormStatus('✓ Agent 已创建', 'success');
      await loadAgents();
      renderAgentList();
      renderManageAgents();
      setTimeout(closeCreateModal, 1200);
    } catch(e) {
      showFormStatus(e.message, 'error');
    } finally {
      DOM['cf-submit'].disabled = false;
      DOM['cf-submit'].textContent = '🚀 创建 Agent';
    }
  });

  // Thinking section toggle (delegated)
  DOM.messages.addEventListener('click', e => {
    const thHeader = e.target.closest('.thinking-header');
    if (thHeader) { thHeader.closest('.thinking-section')?.classList.toggle('collapsed'); }
  });
  DOM['group-messages'].addEventListener('click', e => {
    const thHeader = e.target.closest('.thinking-header');
    if (thHeader) { thHeader.closest('.thinking-section')?.classList.toggle('collapsed'); }
  });

  // Close mention dropdown on outside click
  document.addEventListener('click', e => {
    if (S.mentionActive && !e.target.closest('#group-input') && !e.target.closest('.mention-dropdown')) {
      hideMentionDropdown();
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && S.isStreaming) {
      e.preventDefault();
      cancelActiveStream();
      return;
    }
    if (e.ctrlKey && e.shiftKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault();
      const idx = S.agents.findIndex(a => a.id === S.currentAgentId);
      if (idx === -1) return;
      const next = e.key === 'ArrowUp' ? (idx - 1 + S.agents.length) % S.agents.length : (idx + 1) % S.agents.length;
      selectAgent(S.agents[next].id);
    }
  });
}

// ============ Start ============
document.addEventListener('DOMContentLoaded', init);