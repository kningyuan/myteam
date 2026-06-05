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
   'btn-chat-more','chat-more-dropdown','new-msg-floater',
   'btn-group-more','group-more-dropdown',
   'agent-search','agent-search-results','group-search','group-search-results',
   'chat-agent-name','chat-agent-id','chat-agent-avatar',
   'group-name','group-members','group-avatar',
   'cf-description','cf-agent-id','cf-name','cf-backend','cf-model','cf-submit','cf-cancel','cf-status','cf-result',
   'tab-chat','tab-groups','tab-projects','tab-agents','tab-settings',
   'project-list','project-count','project-welcome','project-detail-view',
   'project-title','project-meta','project-progress-text','project-progress-fill',
   'project-tasks','project-fleet','project-cost','project-events',
   'project-trace','trace-title','trace-body','trace-close',
   'home-stats','home-projects','btn-home-new-project',
   'project-deliverable','deliverable-title','deliverable-task-nav','deliverable-meta','deliverable-files','deliverable-body',
   'btn-deliverable-copy','btn-deliverable-download',
   'btn-sidebar-toggle','sidebar-backdrop','sidebar','btn-open-group','btn-open-project',
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
   'set-default-backend','set-default-model','set-port','set-cli-path','set-debug','set-price',
   'set-model-aliases','btn-save-settings','set-status','btn-apply-model-all',
   'set-use-project-group','set-auto-group','set-hub-url','set-default-review',
   'set-poll-interval','set-ack-timeout','set-task-timeout',
   'set-agent-msg-timeout','set-team-config-timeout','set-task-plan-timeout','set-max-retries',
   'mention-dropdown',
   'manage-modal','mm-id','mm-name','mm-backend','mm-model','mm-workspace','mm-save','mm-cancel','mm-status',
  ].forEach(id => DOM[id] = $(id));
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
  renderAgentList();
  renderGroupList();
  renderProjectList();
  setStatus('online');
  await restoreUiState();
  if (document.querySelector('.nav-tab.active')?.dataset.tab === 'home') renderDashboard();
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
    const dd = DOM['theme-dropdown'];
    if (!dd) return;
    if (dd.classList.contains('hidden')) {
      const rect = e.currentTarget.getBoundingClientRect();
      dd.style.right = (window.innerWidth - rect.right) + 'px';
      dd.style.top = (rect.bottom + 6) + 'px';
      dd.classList.remove('hidden');
    } else {
      dd.classList.add('hidden');
    }
  });
  DOM['theme-dropdown']?.querySelectorAll('[data-theme]').forEach(btn => {
    btn.addEventListener('click', () => {
      applyTheme(btn.dataset.theme);
      DOM['theme-dropdown']?.classList.add('hidden');
    });
  });
  document.addEventListener('click', e => {
    const dd = DOM['theme-dropdown'];
    if (!dd) return;
    if (!e.target.closest('#theme-dropdown') && e.target.id !== 'btn-theme' && !e.target.closest('#btn-theme')) {
      dd.classList.add('hidden');
    }
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
      <span class="s-del" data-del-agent="${a.id}" title="删除对话">${ic('x')}</span>
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

/** 将 payload（对象或 JSON 字符串）统一格式化为可读的 pre 块内容 */
function formatPayloadPretty(value, maxLen = 8000) {
  if (value == null || value === '') return '';
  let parsed = value;
  if (typeof value === 'string') {
    const s = value.trim();
    try { parsed = JSON.parse(s); } catch {
      try { parsed = JSON.parse(s.replace(/^"(.*)"$/, '$1')); } catch { parsed = s; }
    }
  }
  if (typeof parsed === 'string') return parsed.slice(0, maxLen);
  try { return JSON.stringify(parsed, null, 2).slice(0, maxLen); } catch { return String(value).slice(0, maxLen); }
}

function renderPayloadPre(value, maxLen = 8000) {
  const text = formatPayloadPretty(value, maxLen);
  if (!text) return '<span class="hint">（空）</span>';
  return `<pre class="trace-pre">${esc(text)}</pre>`;
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
  if (!await showConfirm(`删除与「${name}」的对话窗口？\n· 侧栏隐藏，可用搜索找回\n· 不会删除 Agent 配置\n· 如需清空 LLM 记忆请用「清空对话」`, {title:'删除对话', okText:'删除', danger:true})) return;

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
  if (!await showConfirm(`解散群组「${name}」？\n· 从列表隐藏，可搜索恢复\n· 不删除 tasks/ 项目数据\n· 消息记录将清空`, {title:'解散群组', okText:'解散', danger:true})) return;

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
    const projTag = g.project_id ? '<span class="s-tag" title="属于一个项目（自动建群）">📋</span>' : '';
    return `<div class="sidebar-item ${S.currentGroupId === g.id ? 'active' : ''}" data-id="${g.id}">
      <span class="s-icon">👥</span>
      <span class="s-name">${esc(g.name)}${projTag}</span>
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

// ============ Dashboard / 成本 ============
let _sysCfg = null;  // 缓存 system 配置（¥费率 / 默认评审等）

async function getSysConfig() {
  if (_sysCfg) return _sysCfg;
  try {
    _sysCfg = (await (await fetch('/api/config')).json()).config?.system || {};
  } catch { _sysCfg = {}; }
  return _sysCfg;
}

async function getPriceRate() {
  return Number((await getSysConfig()).price_per_mtok) || 0;
}

function fmtYuan(tokens, rate) {
  if (!rate) return '';
  return ` · ¥${(tokens / 1e6 * rate).toFixed(2)}`;
}

function budgetBar(tokens, budget, ratio, state) {
  if (!budget) return `<div class="budget-none">${tokens} tok · 无预算上限</div>`;
  const pct = Math.min(100, Math.round((ratio || 0) * 100));
  return `<div class="budget-wrap budget-${esc(state || 'ok')}">
    <div class="budget-track"><div class="budget-fill" style="width:${pct}%"></div></div>
    <div class="budget-label">${tokens} / ${budget} tok · ${pct}%${state === 'over' ? ' · 超限' : state === 'alert' ? ' · 接近上限' : ''}</div>
  </div>`;
}

const PROJ_STATUS_LABEL = {
  in_progress:'运行中', running:'运行中', pending:'排队', completed:'已完成',
  needs_review:'待确认', failed:'失败', cancelled:'已取消', blocked:'阻塞',
};

async function renderDashboard() {
  const stats = DOM['home-stats'], cards = DOM['home-projects'];
  if (!stats || !cards) return;
  const rate = await getPriceRate();
  try {
    const d = await (await fetch('/api/obs/summary')).json();
    const t = d.totals || {};
    stats.innerHTML = `
      <div class="stat-card"><div class="stat-num">${t.projects || 0}</div><div class="stat-lbl">项目总数</div></div>
      <div class="stat-card"><div class="stat-num stat-run">${t.running || 0}</div><div class="stat-lbl">运行中</div></div>
      <div class="stat-card"><div class="stat-num">${(t.tokens || 0).toLocaleString()}</div><div class="stat-lbl">总 Token</div></div>
      ${rate ? `<div class="stat-card"><div class="stat-num">¥${((t.tokens || 0) / 1e6 * rate).toFixed(2)}</div><div class="stat-lbl">预估成本</div></div>` : ''}`;
    const ps = d.projects || [];
    if (!ps.length) { cards.innerHTML = '<div class="empty">还没有项目，点右上角「发起项目」开始。</div>'; return; }
    cards.innerHTML = ps.map(p => {
      const pct = Math.round((p.progress || 0) * 100);
      const sl = PROJ_STATUS_LABEL[p.status] || p.status || '—';
      return `<div class="home-card clickable" data-pid="${esc(p.id)}">
        <div class="home-card-top">
          <span class="home-card-title">${esc(p.title || p.id)}</span>
          <span class="status-chip s-${esc(p.status || '')}">${esc(sl)}</span>
        </div>
        <div class="home-card-prog"><div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div><span>${pct}%</span></div>
        ${budgetBar(p.tokens || 0, p.budget, p.budget_ratio, p.budget_state)}
        <div class="home-card-foot">${p.task_count || 0} 任务 · ${(p.tokens || 0).toLocaleString()} tok${fmtYuan(p.tokens || 0, rate)}</div>
      </div>`;
    }).join('');
    cards.querySelectorAll('.home-card.clickable').forEach(el => {
      el.addEventListener('click', () => { switchTab('projects'); selectProject(el.dataset.pid); });
    });
  } catch (e) {
    cards.innerHTML = `<div class="empty">加载失败：${esc(e.message || e)}</div>`;
  }
}

async function deleteProject(id) {
  if (!await showConfirm(`确认彻底删除项目「${id}」？将清除其数据库记录、交付物目录与 agent 临时文件，不可恢复。`, {title:'删除项目', okText:'彻底删除', danger:true})) return;
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
    showToast(`已删除项目「${id}」`, 'success');
  } catch (e) {
    showToast('删除项目失败：' + (e.message || e), 'error');
  }
}

function stopProjectPoll() {
  if (S._projectPoll) { clearInterval(S._projectPoll); S._projectPoll = null; }
  if (S._projectStream) { try { S._projectStream.close(); } catch (e) {} S._projectStream = null; }
}

// 固定间隔轮询（SSE 不可用时的兜底）
function startProjectPoll(id) {
  S._projectPoll = setInterval(async () => {
    if (S.currentProjectId !== id) { stopProjectPoll(); return; }
    const done = await refreshProjectDetail(id);
    if (done) { stopProjectPoll(); loadProjects().then(renderProjectList); }
  }, 2500);
}

// 优先用项目级 SSE：服务端只在变化时推 tick，前端据此刷新；连接失败回退轮询
function connectProjectStream(id) {
  if (typeof EventSource === 'undefined') { startProjectPoll(id); return; }
  let es;
  try {
    es = new EventSource(`/api/obs/projects/${encodeURIComponent(id)}/stream`);
  } catch (e) { startProjectPoll(id); return; }
  S._projectStream = es;
  es.onmessage = async (ev) => {
    if (S.currentProjectId !== id) { stopProjectPoll(); return; }
    if (ev.data === '[DONE]') {
      await refreshProjectDetail(id);
      stopProjectPoll();
      loadProjects().then(renderProjectList);
      return;
    }
    const done = await refreshProjectDetail(id);
    if (done) { stopProjectPoll(); loadProjects().then(renderProjectList); }
  };
  es.onerror = () => {
    // 连接中断：关掉 SSE，退回轮询（避免 EventSource 自动重连风暴）
    try { es.close(); } catch (e) {}
    if (S._projectStream === es) S._projectStream = null;
    if (S.currentProjectId === id && !S._projectPoll) startProjectPoll(id);
  };
}

let _boundGroupId = '';
let _boundProjectId = '';

async function updateBoundGroupButton(projectId) {
  const btn = DOM['btn-open-group'];
  if (!btn) return;
  if (!S.groups || !S.groups.length) { try { await loadGroups(); } catch (e) {} }
  const grp = (S.groups || []).find(g => g.project_id === projectId && g.status !== 'dissolved');
  _boundGroupId = grp ? grp.id : '';
  btn.classList.toggle('hidden', !grp);
}

function switchProjectTab(ptab, opts = {}) {
  document.querySelectorAll('.project-subnav .ptab').forEach(b =>
    b.classList.toggle('active', b.dataset.ptab === ptab));
  document.querySelectorAll('.ptab-panel').forEach(p =>
    p.classList.toggle('active', p.dataset.ptab === ptab));
  if (ptab === 'deliverable' && !opts.skipDeliverableLoad) {
    void ensureDeliverablePanel();
  }
}

// 幂等渲染：内容没变就不动 DOM（消除轮询导致的闪烁/丢滚动/丢 hover）
const _renderSig = {};
function setHtmlIfChanged(el, key, html) {
  if (!el) return false;
  if (_renderSig[key] === html) return false;
  _renderSig[key] = html;
  el.innerHTML = html;
  return true;
}
function setTextIfChanged(el, val) {
  if (el && el.textContent !== val) el.textContent = val;
}

async function selectProject(id, opts = {}) {
  S.currentProjectId = id;
  S.currentAgentId = null;
  S.currentGroupId = null;
  stopProjectPoll();
  for (const k in _renderSig) delete _renderSig[k];  // 换项目清签名，避免跨项目误判
  renderProjectList();
  DOM['project-welcome'].classList.add('hidden');
  DOM['project-detail-view'].classList.remove('hidden');
  switchProjectTab('overview');
  if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '选择任务或从「概览」点任务查看交付物。';
  if (DOM['deliverable-body']) DOM['deliverable-body'].innerHTML = '';
  if (DOM['deliverable-files']) { DOM['deliverable-files'].innerHTML = ''; DOM['deliverable-files'].classList.add('hidden'); }
  if (DOM['deliverable-task-nav']) { DOM['deliverable-task-nav'].innerHTML = ''; DOM['deliverable-task-nav'].classList.add('hidden'); }
  _deliverable = { content: '', taskId: '' };
  setDeliverableActions(false);
  await updateBoundGroupButton(id);
  const done = await refreshProjectDetail(id);
  // 非终态时用 SSE 实时刷新（内核在后台跑）；终态则不连
  if (!done) connectProjectStream(id);
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
    setTextIfChanged(DOM['project-title'], ov.title || id);
    const launchErr = rs && rs.error ? ` · ⚠️ ${rs.error}` : '';
    setTextIfChanged(DOM['project-meta'], `${id} · ${status}${rs.running ? ' · 运行中' : ''}${launchErr}`);
    const pct = Math.round((ov.progress || 0) * 100);
    setTextIfChanged(DOM['project-progress-text'], `${pct}%`);
    if (DOM['project-progress-fill'].style.width !== `${pct}%`) DOM['project-progress-fill'].style.width = `${pct}%`;

    // 任务 & 产出（点开看交付物）
    const tasks = ov.tasks || [];
    const byTask = (cost && cost.by_task) || {};
    const tasksHtml = tasks.length
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
    if (setHtmlIfChanged(DOM['project-tasks'], 'tasks', tasksHtml)) {
      DOM['project-tasks'].querySelectorAll('.task-row.clickable').forEach(el => {
        el.addEventListener('click', () => openDeliverable(id, el.dataset.task));
      });
    }
    _deliverableTasks = tasks.map(t => ({ id: t.id, name: t.name || t.id }));
    if (document.querySelector('.ptab-panel[data-ptab="deliverable"]')?.classList.contains('active')) {
      void ensureDeliverablePanel();
    }

    // 舰队状态
    const fl = (fleet && fleet.fleet) || {};
    const flEntries = Object.entries(fl);
    const fleetHtml = flEntries.length
      ? flEntries.map(([a, s]) => `<span class="fleet-chip live-${esc(s)}">${esc(a)} · ${esc(s)}</span>`).join('')
      : '<span class="hint">暂无</span>';
    setHtmlIfChanged(DOM['project-fleet'], 'fleet', fleetHtml);

    // 成本 + 预算
    const total = (cost && cost.project) || 0;
    const byAgent = (cost && cost.by_agent) || {};
    const rate = await getPriceRate();
    const agentRows = Object.entries(byAgent)
      .map(([a, n]) => `<div class="cost-row"><span>${esc(a)}</span><span>${n} tok${fmtYuan(n, rate)}</span></div>`).join('');
    const costHtml = budgetBar(total, ov.budget, ov.budget_ratio, ov.budget_state) +
      `<div class="cost-row cost-total"><span>合计</span><span>${total} tok${fmtYuan(total, rate)}</span></div>${agentRows || ''}`;
    setHtmlIfChanged(DOM['project-cost'], 'cost', costHtml);

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

const EXEC_TIMELINE_KINDS = new Set([
  'tool_use', 'text', 'gate_passed', 'gate_failed', 'review_done', 'review_unreachable',
  'error', 'transport_error', 'watchdog_soft_idle', 'watchdog_hard_kill',
  'step_finish', 'prompt_sent', 'plan_rejected',
]);
const EXEC_CHILD_LABELS = {
  tool_use: 'skill 调用', text: '模型输出', step_finish: 'Token 计量', prompt_sent: '发送给 CLI',
  error: '错误', transport_error: '传输错误',
};

function eventDetail(e) {
  const p = e.payload || {};
  if (e.kind === 'gate_failed' && Array.isArray(p.failures)) return p.failures.join('；');
  if (e.kind === 'review_done') return (p.passed ? '通过' : '打回') + (p.feedback ? ' · ' + p.feedback : '');
  if (e.kind === 'message') return (p.sender ? p.sender + '：' : '') + (p.text || '');
  if (e.kind === 'tool_use') return toolUseSummary(p);
  if (e.kind === 'blocked' || e.kind === 'plan_rejected') return p.reason || (p.invalid_agents || []).join(', ');
  if (e.kind === 'budget_alert' || e.kind === 'budget_over') return JSON.stringify(p);
  if (e.kind === 'text') return String(p.content || '').slice(0, 160);
  if (e.kind === 'step_finish') {
    const t = p.tokens;
    if (t && typeof t === 'object') return `${t.total || t.input + t.output || 0} tok`;
    return t ? `${t} tok` : '';
  }
  return p && Object.keys(p).length ? JSON.stringify(p).slice(0, 160) : '';
}

function toolUseSummary(p) {
  const name = p.name || p.tool || 'tool';
  const act = describeToolAction(name, p.input);
  return `${name} · ${act.verb} ${act.target}`.trim().slice(0, 120);
}

function _execOpenState(box) {
  const nodes = new Set();
  const children = new Set();
  const cache = {};
  box.querySelectorAll('.exec-node.open').forEach(n => {
    nodes.add(n.dataset.iid);
    const body = n.querySelector('.exec-node-body');
    if (body && body.dataset.loaded && body.innerHTML) cache[n.dataset.iid] = body.innerHTML;
  });
  box.querySelectorAll('.exec-child.open').forEach(c => children.add(c.dataset.childId));
  return { nodes, children, cache };
}

function _interactionIds(events) {
  const s = new Set();
  for (const e of events) {
    if (e.category === 'interaction' && e.interaction_id) s.add(e.interaction_id);
  }
  return s;
}

function renderInteractionNode(e) {
  const label = INTERACTION_LABELS[e.kind] || e.kind || '交互';
  const att = e.attempt > 1 ? ` ×${e.attempt}` : '';
  const who = [e.task_id, e.agent_id].filter(Boolean).map(esc).join(' · ');
  const tok = e.tokens ? `${e.tokens} tok` : '';
  const ts = (e.ts || '').replace('T', ' ').slice(5, 16);
  const iid = e.interaction_id || '';
  return `<div class="exec-node status-${esc(e.status || '')}" data-iid="${esc(iid)}">
    <div class="exec-node-head" role="button" tabindex="0" aria-expanded="false">
      <span class="exec-chevron">▸</span>
      <span class="exec-node-title">${esc(label)}${att}</span>
      <span class="exec-node-meta">${who ? esc(who) : ''}</span>
      <span class="exec-node-status">${esc(e.status || '')}${tok ? ' · ' + esc(tok) : ''}</span>
      <span class="exec-node-ts">${esc(ts)}</span>
    </div>
    <div class="exec-node-body hidden" data-body-for="${esc(iid)}"></div>
  </div>`;
}

function renderStandaloneEvent(e) {
  const label = EVENT_LABELS[e.kind] || e.kind;
  const detail = eventDetail(e);
  const ts = (e.ts || '').replace('T', ' ').slice(5, 16);
  const childId = `standalone:${e.kind}:${e.ts}:${ts}`;
  return `<div class="exec-standalone evk-${esc(e.kind)}" data-child-id="${esc(childId)}">
    <div class="exec-child-head" role="button" tabindex="0">
      <span class="exec-chevron">▸</span>
      <span class="exec-child-label">${esc(label)}</span>
      <span class="exec-child-summary">${esc(detail)}</span>
      <span class="exec-child-ts">${esc(ts)}</span>
    </div>
    <div class="exec-child-body hidden">${renderEventDetailBody(e)}</div>
  </div>`;
}

function renderEventFeed(events) {
  const box = DOM['project-events'];
  if (!box) return;
  const sig = JSON.stringify(events.map(e => [e.category, e.kind, e.interaction_id, e.status, e.ts]));
  const prev = _execOpenState(box);
  if (_renderSig.execTree === sig && prev.nodes.size) return;
  _renderSig.execTree = sig;

  const iids = _interactionIds(events);
  let html = '';
  if (!events.length) {
    html = '<span class="hint">暂无执行事件</span>';
  } else {
    for (const e of events) {
      if (e.category === 'interaction') html += renderInteractionNode(e);
      else if (e.category === 'event') {
        const iid = e.interaction_id || '';
        if (!iid || !iids.has(iid)) html += renderStandaloneEvent(e);
      }
    }
  }
  box.innerHTML = html;
  bindExecTree(box);

  for (const iid of prev.nodes) {
    const node = box.querySelector(`.exec-node[data-iid="${cssEsc(iid)}"]`);
    if (!node) continue;
    setExecNodeOpen(node, true);
    const body = node.querySelector('.exec-node-body');
    if (body && prev.cache[iid]) {
      body.innerHTML = prev.cache[iid];
      body.dataset.loaded = '1';
      bindExecChildToggles(body);
      for (const cid of prev.children) {
        const ch = body.querySelector(`.exec-child[data-child-id="${cssEsc(cid)}"]`);
        if (ch) setExecChildOpen(ch, true);
      }
    } else if (body) {
      loadExecNodeBody(iid, body).then(() => {
        for (const cid of prev.children) {
          const ch = body.querySelector(`.exec-child[data-child-id="${cssEsc(cid)}"]`);
          if (ch) setExecChildOpen(ch, true);
        }
      });
    }
  }
  for (const cid of prev.children) {
    const el = box.querySelector(`[data-child-id="${cssEsc(cid)}"]`);
    if (el && el.classList.contains('exec-standalone')) setExecChildOpen(el, true);
  }
}

function cssEsc(s) {
  return (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/"/g, '\\"');
}

function bindExecTree(box) {
  if (box.dataset.execBound) return;
  box.dataset.execBound = '1';
  box.addEventListener('click', ev => {
    const nodeHead = ev.target.closest('.exec-node-head');
    if (nodeHead) {
      ev.preventDefault();
      toggleExecNode(nodeHead.closest('.exec-node'));
      return;
    }
    const childHead = ev.target.closest('.exec-child-head');
    if (childHead) {
      ev.preventDefault();
      toggleExecChild(childHead.closest('.exec-child, .exec-standalone'));
    }
  });
}

function setExecNodeOpen(node, open) {
  if (!node) return;
  const body = node.querySelector('.exec-node-body');
  const head = node.querySelector('.exec-node-head');
  const chev = node.querySelector('.exec-chevron');
  node.classList.toggle('open', open);
  body?.classList.toggle('hidden', !open);
  if (head) head.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (chev) chev.textContent = open ? '▾' : '▸';
}

async function toggleExecNode(node) {
  if (!node) return;
  const open = !node.classList.contains('open');
  setExecNodeOpen(node, open);
  if (open) await loadExecNodeBody(node.dataset.iid, node.querySelector('.exec-node-body'));
}

function setExecChildOpen(el, open) {
  if (!el) return;
  const body = el.querySelector('.exec-child-body');
  const chev = el.querySelector('.exec-chevron');
  el.classList.toggle('open', open);
  body?.classList.toggle('hidden', !open);
  if (chev) chev.textContent = open ? '▾' : '▸';
}

function toggleExecChild(el) {
  if (!el) return;
  setExecChildOpen(el, !el.classList.contains('open'));
}

function bindExecChildToggles(container) {
  /* 事件委托在 bindExecTree，无需逐条绑定 */
}

async function loadExecNodeBody(iid, bodyEl) {
  if (!iid || !bodyEl || bodyEl.dataset.loaded) return;
  bodyEl.innerHTML = '<div class="exec-loading hint">加载明细…</div>';
  try {
    const r = await fetch(`/api/obs/interactions/${encodeURIComponent(iid)}/timeline`);
    const d = await r.json();
    const tl = (d.timeline || []).filter(e => EXEC_TIMELINE_KINDS.has(e.kind));
    if (!tl.length) {
      bodyEl.innerHTML = '<div class="exec-empty hint">该步骤暂无 skill 调用或其它明细</div>';
    } else {
      bodyEl.innerHTML = tl.map((ev, idx) => renderExecChild(ev, iid, idx)).join('');
    }
    bodyEl.dataset.loaded = '1';
  } catch (e) {
    bodyEl.innerHTML = `<div class="exec-empty">加载失败：${esc(e.message || String(e))}</div>`;
  }
}

function renderExecChild(ev, iid, idx) {
  const childId = `${iid}:${ev.seq ?? idx}`;
  const p = ev.payload || {};
  const summary = eventDetail({ kind: ev.kind, payload: p });
  if (ev.kind === 'tool_use') {
    const name = p.name || p.tool || 'tool';
    return `<div class="exec-child exec-child-tool" data-child-id="${esc(childId)}">
      <div class="exec-child-head" role="button" tabindex="0">
        <span class="exec-chevron">▸</span>
        <span class="exec-child-label">🛠️ ${esc(name)}</span>
        <span class="exec-child-summary">${esc(summary)}</span>
      </div>
      <div class="exec-child-body hidden">${renderToolDetailBody(p)}</div>
    </div>`;
  }
  const label = EVENT_LABELS[ev.kind] || EXEC_CHILD_LABELS[ev.kind] || ev.kind;
  const cls = ev.kind === 'text' ? 'exec-child-text'
    : (['error', 'transport_error', 'watchdog_hard_kill'].includes(ev.kind) ? 'exec-child-error' : 'exec-child-mile');
  return `<div class="exec-child ${cls}" data-child-id="${esc(childId)}">
    <div class="exec-child-head" role="button" tabindex="0">
      <span class="exec-chevron">▸</span>
      <span class="exec-child-label">${esc(label)}</span>
      <span class="exec-child-summary">${esc(summary)}</span>
    </div>
    <div class="exec-child-body hidden">${renderTimelineDetailBody(ev)}</div>
  </div>`;
}

function renderToolDetailBody(p) {
  const name = p.name || p.tool || 'tool';
  const act = describeToolAction(name, p.input);
  const icon = TOOL_ICONS[name] || '🔧';
  const targetHtml = act.mono
    ? `<code class="activity-target">${esc(act.target)}</code>`
    : `<span class="activity-target-text">${esc(act.target)}</span>`;
  const summary =
    `<div class="exec-tool-summary">` +
    `<span class="activity-icon">${icon}</span>` +
    `<span class="activity-verb">${esc(act.verb)}</span>${targetHtml}` +
    `</div>`;
  const args = `<div class="trace-section"><span class="trace-tag">参数</span>${renderPayloadPre(p.input)}</div>`;
  const out = p.output
    ? `<div class="trace-out"><span class="trace-tag">CLI 返回</span>${renderPayloadPre(p.output)}</div>`
    : '<div class="trace-out trace-noout">（无返回 / 未完成）</div>';
  return summary + args + out;
}

function renderTimelineDetailBody(ev) {
  const p = ev.payload || {};
  if (ev.kind === 'text') {
    return `<div class="trace-section"><span class="trace-tag">输出</span><div class="trace-msg">${esc(String(p.content || '').slice(0, 8000))}</div></div>`;
  }
  if (ev.kind === 'gate_failed' && Array.isArray(p.failures)) {
    return `<ul class="exec-fail-list">${p.failures.map(f => `<li>${esc(f)}</li>`).join('')}</ul>`;
  }
  if (ev.kind === 'step_finish') {
    return `<div class="trace-section"><span class="trace-tag">Token 计量</span>${renderPayloadPre(p)}</div>`;
  }
  if (ev.kind === 'tool_use') {
    return renderToolDetailBody(p);
  }
  if (typeof p.text === 'string' && p.text) {
    return `<div class="trace-msg">${esc(p.text)}</div>`;
  }
  return `<div class="trace-section"><span class="trace-tag">详情</span>${renderPayloadPre(p)}</div>`;
}

function renderEventDetailBody(e) {
  return renderTimelineDetailBody({ kind: e.kind, payload: e.payload || {} });
}

let _deliverable = { content: '', taskId: '', projectId: '', files: [], activePath: '' };
let _deliverableTasks = [];

const DELIV_KIND_LABELS = { script: '脚本', doc: '文档', output: '产出', test: '测试', data: '数据', file: '文件' };

function _deliverableTasksFromDom() {
  const rows = DOM['project-tasks']?.querySelectorAll('.task-row.clickable') || [];
  return [...rows].map(el => ({
    id: el.dataset.task,
    name: el.querySelector('.task-name')?.textContent?.split('\n')[0]?.trim() || el.dataset.task,
  })).filter(t => t.id);
}

async function _fetchProjectTasks(projectId) {
  try {
    const ov = await fetch(`/api/obs/projects/${encodeURIComponent(projectId)}/overview`).then(r => r.json());
    return (ov.tasks || []).map(t => ({ id: t.id, name: t.name || t.id }));
  } catch (_) {
    return [];
  }
}

function renderDeliverableTaskNav(projectId, activeTaskId, tasks) {
  const nav = DOM['deliverable-task-nav'];
  if (!nav) return;
  if (!tasks || !tasks.length) {
    nav.innerHTML = '';
    nav.classList.add('hidden');
    return;
  }
  nav.classList.remove('hidden');
  nav.innerHTML = tasks.map(t => {
    const active = t.id === activeTaskId ? ' active' : '';
    const label = t.name && t.name !== t.id ? `${t.id} · ${esc(t.name)}` : esc(t.id);
    return `<button type="button" class="task-chip${active}" data-task="${esc(t.id)}">${label}</button>`;
  }).join('');
  nav.querySelectorAll('.task-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.task && btn.dataset.task !== _deliverable.taskId) {
        void openDeliverable(projectId, btn.dataset.task);
      }
    });
  });
}

async function ensureDeliverablePanel() {
  const pid = S.currentProjectId;
  if (!pid) return;

  const bodyReady = !!(DOM['deliverable-body']?.innerHTML || '').trim();
  const filesReady = _deliverable.projectId === pid && !!_deliverable.files.length;
  if (_deliverable.projectId === pid && _deliverable.taskId && bodyReady && filesReady) {
    renderDeliverableTaskNav(pid, _deliverable.taskId, _deliverableTasks);
    renderDeliverableFileList(_deliverable.files, _deliverable.activePath);
    return;
  }

  if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '加载中…';

  let tasks = _deliverableTasks.length ? _deliverableTasks : _deliverableTasksFromDom();
  if (!tasks.length) tasks = await _fetchProjectTasks(pid);
  _deliverableTasks = tasks;

  const taskId = (_deliverable.projectId === pid && _deliverable.taskId)
    ? _deliverable.taskId
    : (tasks[0]?.id || '');
  if (!taskId) {
    if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '暂无任务，交付物将在任务完成后出现。';
    return;
  }
  try {
    await openDeliverable(pid, taskId, { fromTabSwitch: true });
  } catch (e) {
    if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e);
  }
}

function setDeliverableActions(visible) {
  DOM['btn-deliverable-copy']?.classList.toggle('hidden', !visible);
  DOM['btn-deliverable-download']?.classList.toggle('hidden', !visible);
}

function renderDeliverablePreview(content, path) {
  const body = DOM['deliverable-body'];
  if (!body) return;
  const low = (path || '').toLowerCase();
  if (low.endsWith('.md') && typeof renderAgentMarkdown === 'function') {
    body.innerHTML = renderAgentMarkdown(content);
  } else if (low.endsWith('.sh') || low.endsWith('.py') || low.endsWith('.js')) {
    body.innerHTML = `<pre class="trace-pre code-preview">${esc(content)}</pre>`;
  } else {
    body.innerHTML = `<pre class="trace-pre">${esc(content)}</pre>`;
  }
}

function sortDeliverableFiles(files) {
  const kindOrder = { doc: 0, script: 1, test: 2, data: 3, output: 4, file: 5 };
  return [...files].sort((a, b) => {
    const ad = (a.path || '').includes('/') ? (a.path || '').split('/').slice(0, -1).join('/') : '';
    const bd = (b.path || '').includes('/') ? (b.path || '').split('/').slice(0, -1).join('/') : '';
    if (ad !== bd) return ad.localeCompare(bd);
    if (a.path === 'README.md') return -1;
    if (b.path === 'README.md') return 1;
    const ka = kindOrder[a.kind] ?? 9;
    const kb = kindOrder[b.kind] ?? 9;
    return ka - kb || (a.path || '').localeCompare(b.path || '');
  });
}

function renderDeliverableFileList(files, activePath) {
  const box = DOM['deliverable-files'];
  if (!box) return;
  if (!files || !files.length) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  const sorted = sortDeliverableFiles(files);
  const groups = new Map();
  for (const f of sorted) {
    const parts = (f.path || '').split('/');
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '';
    if (!groups.has(dir)) groups.set(dir, []);
    groups.get(dir).push(f);
  }
  let html = '';
  for (const [dir, items] of groups) {
    html += `<div class="deliverable-dir">${dir ? `<div class="deliverable-dir-label">${esc(dir)}/</div>` : ''}`;
    html += items.map(f => {
      const kind = DELIV_KIND_LABELS[f.kind] || f.kind || '文件';
      const loc = f.location === 'legacy' ? '旧' : (f.location === 'workspace' ? 'ws' : '');
      const active = f.path === activePath ? ' active' : '';
      return `<button type="button" class="deliverable-file${active}" data-path="${esc(f.path)}">` +
        `<span class="deliverable-file-kind">${esc(kind)}</span>` +
        `<span class="deliverable-file-name">${esc(f.name || f.path)}</span>` +
        (loc ? `<span class="deliverable-file-badge">${esc(loc)}</span>` : '') +
        `</button>`;
    }).join('');
    html += '</div>';
  }
  box.innerHTML = html;
  box.querySelectorAll('.deliverable-file').forEach(btn => {
    btn.addEventListener('click', () => loadDeliverableFile(_deliverable.projectId, _deliverable.taskId, btn.dataset.path));
  });
}

async function loadDeliverableFile(projectId, taskId, path) {
  if (!path) return;
  DOM['deliverable-meta'].textContent = `加载 ${path}…`;
  try {
    const r = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}/file?path=${encodeURIComponent(path)}`
    );
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载失败');
    if (!d.exists) {
      DOM['deliverable-meta'].textContent = `文件不存在：${path}`;
      DOM['deliverable-body'].innerHTML = '';
      setDeliverableActions(false);
      return;
    }
    _deliverable.content = d.content || '';
    _deliverable.activePath = path;
    setDeliverableActions(!!_deliverable.content);
    DOM['deliverable-title'].textContent = `交付物 · ${taskId} · ${path}`;
    DOM['deliverable-meta'].textContent =
      `${DELIV_KIND_LABELS[d.kind] || '文件'} · ${(d.content || '').length} 字符 · ${path}`;
    renderDeliverablePreview(d.content || '', path);
    renderDeliverableFileList(_deliverable.files, path);
  } catch (e) {
    DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e);
  }
}

async function openDeliverable(projectId, taskId, opts = {}) {
  const panel = DOM['project-deliverable'];
  if (!panel) return;
  if (!opts.fromTabSwitch) switchProjectTab('deliverable', { skipDeliverableLoad: true });

  let tasks = _deliverableTasksFromDom();
  if (!tasks.length) tasks = await _fetchProjectTasks(projectId);
  _deliverableTasks = tasks.length ? tasks : [{ id: taskId, name: taskId }];
  renderDeliverableTaskNav(projectId, taskId, _deliverableTasks);
  DOM['deliverable-title'].textContent = `交付物 · ${taskId}`;
  DOM['deliverable-meta'].textContent = '加载中…';
  DOM['deliverable-body'].innerHTML = '';
  DOM['deliverable-files']?.classList.add('hidden');
  _deliverable = { content: '', taskId, projectId, files: [], activePath: '' };
  setDeliverableActions(false);
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载失败');
    const files = d.files || [];
    const primary = d.primary || {};
    _deliverable.files = files;

    if (!files.length && !primary.exists && !d.exists) {
      DOM['deliverable-meta'].textContent = '该任务暂无交付物';
      return;
    }

    const taskName = (S.projects || []).find(p => p.id === projectId)?.title || '';
    const baseHint = d.base === 'code_project'
      ? `deliverables/${d.project_dir || taskId + '/'}`
      : 'deliverables/*.md';
    DOM['deliverable-title'].textContent = `交付物 · ${taskId}${taskName ? ' · ' + taskName : ''}`;
    DOM['deliverable-meta'].textContent =
      `${d.task_type || '任务'} · ${baseHint} · ${files.length} 个文件 · 左侧选文件预览`;

    renderDeliverableFileList(files, '');

    const defaultPath = primary.path || (files[0] && files[0].path) || '';
    if (defaultPath) {
      await loadDeliverableFile(projectId, taskId, defaultPath);
    } else if (d.content) {
      _deliverable.content = d.content;
      setDeliverableActions(true);
      renderDeliverablePreview(d.content, `${taskId}_deliverable.md`);
    }
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e);
  }
}

async function copyDeliverable() {
  if (!_deliverable.content) return;
  try {
    await navigator.clipboard.writeText(_deliverable.content);
    showToast('已复制交付物正文', 'success');
  } catch (e) {
    showToast('复制失败：' + (e.message || e), 'error');
  }
}

function downloadDeliverable() {
  if (!_deliverable.content) return;
  const blob = new Blob([_deliverable.content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const ext = (_deliverable.activePath || '').includes('.')
    ? _deliverable.activePath.split('.').pop()
    : 'md';
  a.download = `${(_deliverable.taskId || 'deliverable').replace(/[^\w.\-]/g, '_')}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
        scrollBottom(DOM.messages, true);
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
  // 本地缓存即时渲染（离线兜底），随后 loadDmHistory 以后端库刷新为准 + 合并后台私聊
  if (S.agentMessages[id]) {
    S.agentMessages[id].forEach(m => renderAgentMsg(m, DOM.messages, id));
    scrollBottom(DOM.messages, true);
  }
  hideNewMsgFloater();
  loadDmHistory(id);
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
  scrollBottom(DOM.messages, true);
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
  } else if (ev.event === 'citations') {
    const cites = Array.isArray(ev.data) ? ev.data : [];
    if (cites.length) {
      msg.parts = cites;
      const bubble = rootEl.querySelector('.bubble');
      if (bubble) {
        bubble.querySelector('.citations')?.remove();
        renderCitations(bubble, cites, bubble.querySelector('.msg-meta'));
      }
      scrollBottom(DOM.messages);
    }
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

// ---- DM 时间/分组工具 ----
function fmtMsgTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d)) return '';
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}
function dayKeyOf(ts) {
  const d = new Date(ts || Date.now());
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}
function dayLabelOf(ts) {
  const d = new Date(ts || Date.now()), now = new Date();
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (dayKeyOf(ts) === dayKeyOf(now.getTime())) return '今天';
  if (dayKeyOf(ts) === dayKeyOf(y.getTime())) return '昨天';
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}
function tsFromIso(s) { const t = Date.parse(s); return isNaN(t) ? 0 : t; }

// 与上一条不同天则插入居中日期分隔 pill（DM/群组共用）
function _dateSep(c, mts) {
  const last = c.lastElementChild;
  const lastDay = last && last.dataset ? last.dataset.day : null;
  const thisDay = dayKeyOf(mts);
  if (lastDay !== thisDay) {
    const sep = document.createElement('div');
    sep.className = 'date-sep'; sep.dataset.day = thisDay;
    sep.textContent = dayLabelOf(mts);
    c.appendChild(sep);
  }
}
// 连续同发送者（5 分钟内）分组（DM/群组共用）
function _grouped(c, gkey, mts) {
  const prev = c.lastElementChild;
  if (prev && prev.classList && prev.classList.contains('message') && prev.dataset.gkey === gkey) {
    const lt = parseInt(prev.dataset.ts || '0', 10);
    return (mts && lt) ? Math.abs(mts - lt) < 300000 : (!mts && !lt);
  }
  return false;
}

// ============ 线性图标（内联 SVG，currentColor，零依赖）============
const ICONS = {
  menu: '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.3 7.3L4 21l1.7-5.7A8 8 0 1 1 21 12Z"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5.5a3 3 0 0 1 0 5.5"/><path d="M17.5 14a6 6 0 0 1 3.5 6"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="16" y2="14"/><line x1="8" y1="18" x2="13" y2="18"/>',
  sliders: '<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2" class="fill"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2" class="fill"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="8" cy="18" r="2" class="fill"/>',
  settings: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
  theme: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18Z" class="fill"/>',
  moon: '<path d="M21 12.8A8 8 0 0 1 11.2 3 7 7 0 1 0 21 12.8Z"/>',
  sun: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  more: '<circle cx="5" cy="12" r="1.5" class="fill"/><circle cx="12" cy="12" r="1.5" class="fill"/><circle cx="19" cy="12" r="1.5" class="fill"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 13h10l1-13"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
  x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  'arrow-down': '<line x1="12" y1="5" x2="12" y2="19"/><path d="M6 13l6 6 6-6"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  download: '<path d="M12 3v12"/><path d="M7 11l5 5 5-5"/><path d="M5 21h14"/>',
};
function ic(name, cls) {
  return '<svg class="icon-svg' + (cls ? ' ' + cls : '') + '" viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || '') + '</svg>';
}
function hydrateIcons(root) {
  (root || document).querySelectorAll('[data-icon]').forEach(el => {
    if (el.dataset.iconDone) return;
    el.insertAdjacentHTML('afterbegin', ic(el.dataset.icon));
    el.dataset.iconDone = '1';
  });
}

function msgMetaHtml(mts) {
  return '<div class="msg-meta"><button class="msg-copy" type="button" title="复制" aria-label="复制">⧉</button>' +
    '<span class="msg-time">' + fmtMsgTime(mts) + '</span></div>';
}

// 引用卡片：把消息 parts 里 type==='citation' 的条目渲染成卡片，插在 meta 之前
function renderCitations(bubbleEl, parts, beforeEl) {
  if (!Array.isArray(parts)) return;
  const cites = parts.filter(p => p && p.type === 'citation');
  if (!cites.length) return;
  const wrap = document.createElement('div');
  wrap.className = 'citations';
  cites.forEach(c => {
    const card = document.createElement('div');
    card.className = 'citation-card';
    const title = c.title || c.source || c.ref || '引用';
    const snippet = c.snippet || c.text || '';
    card.innerHTML = '<div class="cite-head">🔗 ' + esc(title) + '</div>' +
      (snippet ? '<div class="cite-snippet">' + esc(snippet) + '</div>' : '');
    if (c.url) {
      card.classList.add('clickable');
      card.addEventListener('click', () => window.open(c.url, '_blank', 'noopener'));
    }
    wrap.appendChild(card);
  });
  if (beforeEl) bubbleEl.insertBefore(wrap, beforeEl);
  else bubbleEl.appendChild(wrap);
}

// 从后端 message 表加载 DM 历史（P0 记忆地基为准），失败则保留本地离线缓存；最后合并后台私聊
async function loadDmHistory(id) {
  try {
    const r = await fetch(`/api/chat/${encodeURIComponent(id)}/messages`);
    if (r.ok) {
      const d = await r.json();
      if (S.currentAgentId === id && !S.isStreaming) {
        const mapped = (d.messages || []).map(m => ({
          role: m.role === 'user' ? 'user' : (m.role === 'agent' ? 'agent' : 'system'),
          content: m.text || '',
          parts: m.parts || null,
          ts: tsFromIso(m.created_at),
        }));
        if (mapped.length) {
          S.agentMessages[id] = mapped;
          DOM.messages.innerHTML = '';
          mapped.forEach(m => renderAgentMsg(m, DOM.messages, id));
          scrollBottom(DOM.messages, true);
        }
      }
    }
  } catch (e) { /* 离线：保留本地缓存渲染 */ }
  loadBackgroundChats(id);
}

function renderAgentMsg(msg, container, agentId) {
  const c = container || DOM.messages;
  const aid = agentId || S.currentAgentId;
  const mts = msg.ts || 0;
  const gkey = msg.role === 'agent' ? 'agent:' + aid : msg.role;

  if (msg.role !== 'system') _dateSep(c, mts);
  const grouped = _grouped(c, gkey, mts);

  const div = document.createElement('div');
  div.dataset.gkey = gkey;
  div.dataset.ts = String(mts);
  div.dataset.day = dayKeyOf(mts);

  if (msg.role === 'user') {
    div.className = 'message user' + (grouped ? ' grouped' : '');
    div.innerHTML = '<div class="bubble"><div class="msg-content">' + esc(msg.content) +
      '</div>' + msgMetaHtml(mts) + '</div>';
  } else if (msg.role === 'agent') {
    div.className = 'message agent' + (grouped ? ' grouped' : '');
    const a = S.agents.find(x => x.id === aid);
    const nm = a ? a.name : 'Agent';
    const hasThinking = msg.thinking && msg.thinking.length;

    div.innerHTML =
      '<div class="msg-avatar">' + getAvatar(aid) + '</div>' +
      '<div class="bubble">' +
        (grouped ? '' : '<div class="bubble-name">' + esc(nm) + '</div>') +
        '<div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">' + esc(thinkingSectionTitle(msg.thinking, !!(msg.ts && S.isStreaming))) + '</span></div><div class="thinking-body">' + buildThinkingBodyHtml(msg.thinking) + '</div></div>' +
        '<div class="msg-content"></div>' +
        '<div class="typing-dots" style="display:none"><span></span><span></span><span></span></div>' +
        msgMetaHtml(mts) +
      '</div>';

    const ce = div.querySelector('.msg-content');
    if (ce) renderBubbleMarkdown(ce, msg.content || '');

    // 引用卡片渲染管线（parts.citation → 卡片；无引用则 no-op）
    const bub = div.querySelector('.bubble');
    if (bub) renderCitations(bub, msg.parts, bub.querySelector('.msg-meta'));

    const tsEl = div.querySelector('.thinking-section');
    if (tsEl && !hasThinking && !(msg.ts && S.isStreaming)) tsEl.style.display = 'none';
    if (tsEl && msg.ts && S.isStreaming) tsEl.style.display = '';

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
    _boundProjectId = g.project_id || '';
    DOM['btn-open-project']?.classList.toggle('hidden', !_boundProjectId);

    // Render history
    (g.messages||[]).forEach(m => {
      renderGroupMsg(m);
    });
    scrollBottom(DOM['group-messages'], true);
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
    const c = DOM['group-messages'];
    const aId = data.agent_id;
    const mts = Date.now();
    const gkey = 'agent:' + aId;
    _dateSep(c, mts);
    const grouped = _grouped(c, gkey, mts);
    const div = document.createElement('div');
    div.className = 'message group-agent' + (grouped ? ' grouped' : '');
    div.id = `gt-${aId}`;
    div.dataset.gkey = gkey; div.dataset.ts = String(mts); div.dataset.day = dayKeyOf(mts);
    div.innerHTML =
      '<div class="msg-avatar">' + getAvatar(aId) + '</div>' +
      '<div class="bubble">' +
        (grouped ? '' : '<div class="bubble-name">@' + esc(aId) + '</div>') +
        '<div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">Agent 活动</span></div><div class="thinking-body"></div></div>' +
        '<div class="msg-content"></div>' +
        msgMetaHtml(mts) +
      '</div>';
    c.appendChild(div);
    block = div;
    scrollBottom(c);
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
  const mts = msg.timestamp ? Math.round(msg.timestamp * 1000) : (msg.ts || Date.now());
  const sender = msg.sender;
  const isUser = sender === 'user';
  const isSystem = sender === 'system';
  const gkey = isUser ? 'user' : (isSystem ? 'system' : 'agent:' + sender);

  if (!isSystem) _dateSep(c, mts);
  const grouped = _grouped(c, gkey, mts);

  const div = document.createElement('div');
  div.dataset.gkey = gkey; div.dataset.ts = String(mts); div.dataset.day = dayKeyOf(mts);

  if (isUser) {
    div.className = 'message group-user' + (grouped ? ' grouped' : '');
    div.innerHTML = '<div class="bubble"><div class="msg-content">' + esc(msg.text || '') +
      '</div>' + msgMetaHtml(mts) + '</div>';
  } else if (isSystem) {
    div.className = 'message system';
    div.innerHTML = esc(msg.text || '').replace(/\n/g, '<br>');
  } else {
    const aId = sender;
    div.className = 'message group-agent' + (grouped ? ' grouped' : '');
    div.innerHTML =
      '<div class="msg-avatar">' + getAvatar(aId) + '</div>' +
      '<div class="bubble">' +
        (grouped ? '' : '<div class="bubble-name">@' + esc(aId) + '</div>') +
        '<div class="msg-content"></div>' +
        msgMetaHtml(mts) +
      '</div>';
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
    `<span class="member-tag">${esc(m)} <button class="member-remove" data-agent="${m}">${ic('x')}</button></span>`
  ).join('') || '<span style="color:var(--text-tertiary);font-size:12px">暂无成员</span>';

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

async function populateCreateForm() {
  let defBackend = 'opencode';
  let defModel = '';
  try {
    const r = await fetch('/api/config');
    const cfg = (await r.json()).config || {};
    defBackend = cfg.system?.default_backend || defBackend;
    defModel = cfg.system?.default_model || '';
  } catch (_) { /* ignore */ }

  const bSel = DOM['cf-backend'];
  bSel.innerHTML = S.backends.map(b =>
    `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`
  ).join('');
  updateCreateModels(bSel.value, defModel);
  bSel.onchange = () => updateCreateModels(bSel.value);
  DOM['cf-description'].oninput = () => {
    const desc = DOM['cf-description'].value.trim();
    if (desc.length > 5) suggestId(desc);
  };
}

function updateCreateModels(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['cf-model'];
  mSel.innerHTML = models.map(m =>
    `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`
  ).join('');
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
      <td><div class="agent-cell"><span class="icon">${getAvatar(a.id)}</span><span><strong>${esc(a.name)}</strong><br><span style="color:var(--text-tertiary);font-size:11px">${esc(a.id)}</span></span></div></td>
      <td><span style="font-size:12px">${esc(a.backend)}</span></td>
      <td><span style="font-size:11px;color:var(--text-secondary)">${esc(a.model||'').slice(0,30)}</span></td>
      <td><span style="font-size:10px;color:var(--text-tertiary);word-break:break-all">${esc(a.workspace||'')}</span></td>
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
      if (!await showConfirm(`确认删除 Agent「${id}」？将删除工作目录和配置。`, {title:'删除 Agent', okText:'删除', danger:true})) return;
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
    const kindLabel = { artifact: '文档', action: '动作证据', code_project: '代码工程' };
    box.innerHTML = `<table class="manage-table tasktype-table">
      <thead><tr><th>类型</th><th>产出形态</th><th>交付指引</th><th>门禁（客观）</th></tr></thead>
      <tbody>${items.map(t => {
        const kind = kindLabel[t.outcome_kind] || t.outcome_kind;
        const guide = (t.sections || []).map(s =>
          `<span class="chip" title="${esc(s.description || '')}">${esc(s.name)}</span>`
        ).join(' ') || '—';
        const gate = (t.gate_checks || []).map(s => `<span class="chip chip-gate">${esc(s)}</span>`).join(' ') || '—';
        const structHint = (t.structure || []).length
          ? `<div class="hint tasktype-struct">${(t.structure || []).map(esc).join(' · ')}</div>` : '';
        return `<tr>
          <td><code>${esc(t.task_type)}</code></td>
          <td>${esc(kind)}</td>
          <td>${guide}${structHint}</td>
          <td>${gate}</td></tr>`;
      }).join('')}</tbody></table>`;
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
let _settingsCfg = {};

const CLI_PATH_LABELS = {
  opencode: 'OpenCode CLI 路径',
  claude: 'Claude CLI 路径',
};

function updateSettingsCliPath(backendId) {
  const label = DOM['set-cli-path-label'];
  const hint = DOM['set-cli-path-hint'];
  const input = DOM['set-cli-path'];
  if (label) label.textContent = CLI_PATH_LABELS[backendId] || `${backendId} CLI 路径`;
  if (input) {
    input.value = _settingsCfg.backends?.[backendId]?.cli_path || '';
    input.placeholder = backendId === 'claude' ? '留空则从 PATH 检测 claude' : '留空则自动检测';
  }
  if (hint) {
    hint.textContent = backendId === 'opencode'
      ? 'OpenCode 可执行文件；模型别名仅作用于 OpenCode'
      : 'Claude Code 可执行文件；留空则依次尝试配置路径、CLAUDE_CLI_PATH、PATH';
  }
}

async function loadSettings() {
  await loadBackends();
  try {
    const [rSys, rSkill] = await Promise.all([
      fetch('/api/config'),
      fetch('/api/skill-config'),
    ]);
    const cfg = (await rSys.json()).config || {};
    _settingsCfg = cfg;
    const skillCfg = (await rSkill.json()).config || {};

    const defBackend = cfg.system?.default_backend || 'opencode';
    const bSel = DOM['set-default-backend'];
    bSel.innerHTML = S.backends.map(b =>
      `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`
    ).join('');

    const defModel = cfg.system?.default_model || '';
    updateDefaultModelSelect(defBackend, defModel);
    bSel.onchange = () => {
      updateDefaultModelSelect(bSel.value);
      updateSettingsCliPath(bSel.value);
    };
    updateSettingsCliPath(defBackend);

    DOM['set-port'].value = cfg.system?.port || 8765;
    DOM['set-debug'].checked = !!cfg.system?.debug;
    DOM['set-price'].value = cfg.system?.price_per_mtok || '';
    DOM['set-default-review'].checked = !!cfg.system?.default_review;
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
  if (!await showConfirm(`把后端「${backend}」下的所有 agent 模型都改成：\n${model}\n（其它后端的 agent 不受影响）`, {title:'批量应用模型', okText:'应用'})) return;
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
    cfg.system.price_per_mtok = Number(DOM['set-price']?.value) || 0;
    cfg.system.default_review = !!DOM['set-default-review']?.checked;
    cfg.backends = cfg.backends || {};
    cfg.backends[backend] = cfg.backends[backend] || {};
    cfg.backends[backend].cli_path = cliPath;
    if (backend === 'opencode') {
      cfg.backends.opencode.model_aliases = aliases;
    }

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
    _sysCfg = null;
    _settingsCfg = cfg;
    showSetStatus('✓ 已保存（端口变更需重启 Hub）', 'success');
  } catch(e) {
    showSetStatus('保存失败: '+e.message, 'error');
  }
}

function showSetStatus(msg, type) {
  if (msg) showToast(msg, type || 'info');
  const s = DOM['set-status'];
  if (!s) return;
  s.textContent = msg;
  s.className = 'form-status';
  if (msg) { s.style.display = 'block'; if (type) s.classList.add(type); }
  else s.style.display = 'none';
}

// ============ Toast 通知 ============
function showToast(msg, type = 'info', ms = 3200) {
  const box = document.getElementById('toast-container');
  if (!box) { console.log('[toast]', type, msg); return; }
  const icon = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' }[type] || 'ℹ';
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg"></span>`;
  el.querySelector('.toast-msg').textContent = msg;
  box.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  const close = () => { el.classList.remove('show'); setTimeout(() => el.remove(), 220); };
  el.addEventListener('click', close);
  if (ms) setTimeout(close, ms);
}

// ============ 通用确认弹窗（替代原生 confirm）============
function showConfirm(body, opts = {}) {
  return new Promise(resolve => {
    const modal = document.getElementById('confirm-modal');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');
    if (!modal || !okBtn || !cancelBtn) { resolve(window.confirm(body)); return; }
    document.getElementById('confirm-title').textContent = opts.title || '确认操作';
    document.getElementById('confirm-body').textContent = body;
    okBtn.textContent = opts.okText || '确认';
    okBtn.className = opts.danger ? 'btn-primary btn-danger' : 'btn-primary';
    modal.classList.remove('hidden');
    const done = (val) => {
      modal.classList.add('hidden');
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      resolve(val);
    };
    const onOk = () => done(true);
    const onCancel = () => done(false);
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
  });
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

function isNearBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
}
function showNewMsgFloater() { DOM['new-msg-floater']?.classList.remove('hidden'); }
function hideNewMsgFloater() { DOM['new-msg-floater']?.classList.add('hidden'); }

// 贴底时跟随滚动；用户上滑查看历史时不猛拽，改为提示「↓ 新消息」
function scrollBottom(el, force) {
  if (force || isNearBottom(el)) {
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    if (el === DOM.messages) hideNewMsgFloater();
  } else if (el === DOM.messages) {
    showNewMsgFloater();
  }
}

function removeTyping(el) {
  const td = el?.querySelector('.typing-dots');
  if (td) td.style.display = 'none';
}

async function clearChat() {
  if (!S.currentAgentId) return;
  if (S.isStreaming) cancelActiveStream();
  const ok = await showConfirm(
    '清空后将删除：\n' +
    '· 本页所有对话记录（浏览器本地）\n' +
    '· Agent 多轮上下文（OpenCode Session）\n' +
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
  const ok = await showConfirm(
    '清空后将删除本群组的所有消息记录。\n' +
    '说明：各 Agent 的私聊上下文需在对应 Agent 对话里单独清空。',
    {title:'清空群消息', okText:'清空', danger:true}
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
  DOM['btn-clear-chat'].addEventListener('click', () => {
    DOM['chat-more-dropdown']?.classList.add('hidden'); clearChat();
  });
  DOM['btn-delete-chat']?.addEventListener('click', () => {
    DOM['chat-more-dropdown']?.classList.add('hidden'); deleteChatWindow();
  });
  DOM['btn-chat-more']?.addEventListener('click', e => {
    e.stopPropagation();
    DOM['chat-more-dropdown']?.classList.toggle('hidden');
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.more-menu')) DOM['chat-more-dropdown']?.classList.add('hidden');
  });
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
  DOM['btn-clear-group'].addEventListener('click', () => {
    DOM['group-more-dropdown']?.classList.add('hidden'); clearGroupChat();
  });
  DOM['btn-dissolve-group']?.addEventListener('click', () => {
    DOM['group-more-dropdown']?.classList.add('hidden'); dissolveGroupWindow();
  });
  DOM['btn-group-more']?.addEventListener('click', e => {
    e.stopPropagation();
    DOM['group-more-dropdown']?.classList.toggle('hidden');
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.more-menu')) DOM['group-more-dropdown']?.classList.add('hidden');
  });
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
  const openNewProject = async () => {
    DOM['new-project-modal'].classList.remove('hidden');
    DOM['np-goal']?.focus();
    if (DOM['np-review']) DOM['np-review'].checked = !!(await getSysConfig()).default_review;
  };
  const closeNewProject = () => DOM['new-project-modal'].classList.add('hidden');
  document.querySelectorAll('.project-subnav .ptab').forEach(b =>
    b.addEventListener('click', () => switchProjectTab(b.dataset.ptab)));
  DOM['btn-deliverable-copy']?.addEventListener('click', copyDeliverable);
  DOM['btn-deliverable-download']?.addEventListener('click', downloadDeliverable);
  DOM['btn-open-group']?.addEventListener('click', () => {
    if (_boundGroupId) { switchTab('groups'); selectGroup(_boundGroupId); }
  });
  DOM['btn-open-project']?.addEventListener('click', () => {
    if (_boundProjectId) { switchTab('projects'); selectProject(_boundProjectId); }
  });
  DOM['btn-sidebar-toggle']?.addEventListener('click', () => document.body.classList.toggle('sidebar-open'));
  DOM['sidebar-backdrop']?.addEventListener('click', () => document.body.classList.remove('sidebar-open'));
  // 窄屏抽屉：选中侧栏条目后自动收起
  DOM['sidebar']?.addEventListener('click', (e) => {
    if (e.target.closest('.sidebar-item, .search-item')) {
      document.body.classList.remove('sidebar-open');
    }
  });
  DOM['btn-new-project']?.addEventListener('click', openNewProject);
  DOM['btn-new-project-welcome']?.addEventListener('click', openNewProject);
  DOM['btn-home-new-project']?.addEventListener('click', openNewProject);
  DOM['np-cancel']?.addEventListener('click', closeNewProject);
  DOM['new-project-modal']?.querySelector('.modal-close')?.addEventListener('click', closeNewProject);
  DOM['btn-cancel-project']?.addEventListener('click', async () => {
    const id = S.currentProjectId;
    if (!id) return;
    if (!await showConfirm('取消该项目？当前正在执行的任务会跑完，之后不再派发新任务。', {title:'取消项目', okText:'取消项目', danger:true})) return;
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
    if (thHeader) { thHeader.closest('.thinking-section')?.classList.toggle('collapsed'); return; }
    const cp = e.target.closest('.msg-copy');
    if (cp) {
      const mc = cp.closest('.message')?.querySelector('.msg-content');
      const txt = mc ? (mc.innerText || mc.textContent || '') : '';
      if (txt && navigator.clipboard) {
        navigator.clipboard.writeText(txt).then(() => {
          cp.textContent = '✓';
          setTimeout(() => { cp.textContent = '⧉'; }, 1200);
        }).catch(() => {});
      }
    }
  });
  DOM.messages.addEventListener('scroll', () => {
    if (isNearBottom(DOM.messages)) hideNewMsgFloater();
  });
  DOM['new-msg-floater']?.addEventListener('click', () => scrollBottom(DOM.messages, true));
  DOM['group-messages'].addEventListener('click', e => {
    const thHeader = e.target.closest('.thinking-header');
    if (thHeader) { thHeader.closest('.thinking-section')?.classList.toggle('collapsed'); return; }
    const cp = e.target.closest('.msg-copy');
    if (cp) {
      const mc = cp.closest('.message')?.querySelector('.msg-content');
      const txt = mc ? (mc.innerText || mc.textContent || '') : '';
      if (txt && navigator.clipboard) {
        navigator.clipboard.writeText(txt).then(() => {
          cp.textContent = '✓';
          setTimeout(() => { cp.textContent = '⧉'; }, 1200);
        }).catch(() => {});
      }
    }
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