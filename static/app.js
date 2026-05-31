// ============ State ============
const S = {
  agents: [], backends: [], groups: [],
  currentAgentId: null, currentGroupId: null,
  isStreaming: false, abortCtrl: null,
  agentMessages: {}, groupMessages: {},
  backendsCache: {},
  // @mention state
  mentionActive: false, mentionFilter: '',
  mentionIdx: -1, groupMembers: [],
};

// ============ DOM Refs ============
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);
const DOM = {};

function cacheDom() {
  ['agent-list','group-list','messages','group-messages','welcome','chat-view',
   'group-welcome','group-chat-view','message-input','group-input','btn-send','btn-group-send',
   'btn-clear-chat','btn-clear-group','chat-agent-name','chat-agent-id','chat-agent-avatar',
   'group-name','group-members','group-avatar',
   'cf-description','cf-agent-id','cf-name','cf-backend','cf-model','cf-submit','cf-status','cf-result',
   'tab-chat','tab-groups','tab-create','tab-agents','tab-settings',
   'modal-overlay','agent-config-modal','modal-backend','modal-model','modal-agent-info',
   'modal-save','modal-cancel','btn-agent-config',
   'group-config-modal','group-modal-name','group-modal-members','group-add-agent','btn-add-member','group-modal-close',
   'new-group-modal','ng-name','ng-desc','ng-submit','ng-cancel','btn-new-group',
   'status-badge','agent-count','btn-group-config','btn-send','btn-group-send',
   'manage-agent-table','manage-agent-count',
   'set-default-backend','set-default-model','set-port','set-model-aliases','btn-save-settings','set-status',
   'mention-dropdown',
   'manage-modal','mm-id','mm-name','mm-backend','mm-model','mm-workspace','mm-save','mm-cancel','mm-status',
  ].forEach(id => DOM[id] = $(id));
}

// ============ Init ============
async function init() {
  cacheDom();
  setupTabs();
  setupEventListeners();
  await Promise.all([loadAgents(), loadBackends(), loadGroups()]);
  renderAgentList();
  renderGroupList();
  setStatus('online');
}

// ============ Tab System ============
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
}

function switchTab(tab) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.toggle('active', t.id === `tab-${tab}`));

  // Sidebar: show only for chat and groups
  const showSidebar = (tab === 'chat' || tab === 'groups');
  document.getElementById('sidebar').style.display = showSidebar ? 'flex' : 'none';
  document.querySelectorAll('.sidebar-panel').forEach(p => p.classList.toggle('active',
    (tab === 'chat' && p.id === 'sidebar-agents') ||
    (tab === 'groups' && p.id === 'sidebar-groups')
  ));

  if (tab === 'chat') renderAgentList();
  if (tab === 'groups') { renderGroupList(); loadGroups(); }
  if (tab === 'create') populateCreateForm();
  if (tab === 'agents') renderManageAgents();
  if (tab === 'settings') loadSettings();
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

function renderAgentList() {
  if (!DOM['agent-list']) return;
  if (!S.agents.length) { DOM['agent-list'].innerHTML = '<div class="empty">无可用 Agent</div>'; return; }
  DOM['agent-list'].innerHTML = S.agents.map(a =>
    `<div class="sidebar-item ${S.currentAgentId === a.id ? 'active' : ''}" data-id="${a.id}">
      <span class="s-icon">${getAvatar(a.id)}</span>
      <span class="s-name">${esc(a.name)}</span>
      <span class="s-sub">${esc(a.model||'').slice(0,18)}</span>
    </div>`
  ).join('');
  DOM['agent-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', () => selectAgent(el.dataset.id));
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

// ============ Groups ============
async function loadGroups() {
  try {
    const r = await fetch('/api/groups');
    const d = await r.json();
    S.groups = d.groups || [];
  } catch(e) { console.error('groups:', e); }
}

function renderGroupList() {
  if (!DOM['group-list']) return;
  if (!S.groups.length) { DOM['group-list'].innerHTML = '<div class="empty">暂无群组，点击 + 创建</div>'; return; }
  DOM['group-list'].innerHTML = S.groups.map(g =>
    `<div class="sidebar-item ${S.currentGroupId === g.id ? 'active' : ''}" data-id="${g.id}">
      <span class="s-icon">👥</span>
      <span class="s-name">${esc(g.name)}</span>
      <span class="s-sub">${g.member_count}人</span>
    </div>`
  ).join('');
  DOM['group-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', () => selectGroup(el.dataset.id));
  });
}

// ============ Select Agent (1-on-1 chat) ============
function selectAgent(id) {
  if (S.isStreaming) { stopStream(); }
  S.currentAgentId = id;
  renderAgentList();
  DOM.welcome.classList.add('hidden');
  DOM['chat-view'].classList.remove('hidden');
  const a = S.agents.find(x => x.id === id);
  if (a) {
    DOM['chat-agent-name'].textContent = a.name;
    DOM['chat-agent-id'].textContent = `${a.id} · ${a.backend}`;
    DOM['chat-agent-avatar'].textContent = getAvatar(id);
  }
  DOM.messages.innerHTML = '';
  if (S.agentMessages[id]) {
    S.agentMessages[id].forEach(m => renderAgentMsg(m));
  }
  DOM['message-input'].disabled = false;
  DOM['message-input'].focus();
  updateSendBtn();
}

// ============ Agent Chat Sending ============
async function sendAgentMsg() {
  const text = DOM['message-input'].value.trim();
  if (!text || S.isStreaming || !S.currentAgentId) return;

  const msg = { role:'user', content:text };
  addAgentMsg(S.currentAgentId, msg);
  renderAgentMsg(msg);
  DOM['message-input'].value = ''; DOM['message-input'].style.height = 'auto';
  DOM['btn-send'].disabled = true;
  S.isStreaming = true; setStatus('busy');

  const aMsg = { role:'agent', content:'', thinking:[], ts:Date.now() };
  addAgentMsg(S.currentAgentId, aMsg);
  const el = renderAgentMsg(aMsg);
  const tb = el?.querySelector('.thinking-body');
  const ts = el?.querySelector('.thinking-section');
  const ce = el?.querySelector('.msg-content');

  DOM['btn-send'].textContent = '...';

  try {
    S.abortCtrl = new AbortController();
    const resp = await fetch(`/api/chat/${S.currentAgentId}?message=${encodeURIComponent(text)}`, { signal: S.abortCtrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
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
          handleThinking(ev, aMsg, ce, tb, ts, el);
        } catch(e) {}
      }
    }
    if (ce) ce.textContent = aMsg.content || '(空响应)';
  } catch(e) {
    if (e.name !== 'AbortError') {
      aMsg.content += `\n[错误: ${e.message}]`;
      if (ce) ce.textContent = aMsg.content;
    }
  } finally {
    S.isStreaming = false; setStatus('online');
    DOM['btn-send'].textContent = '发送';
    updateSendBtn();
    scrollBottom(DOM.messages);
    removeTyping(el);
  }
}

function handleThinking(ev, msg, contentEl, tb, ts, rootEl) {
  if (!ev || ev.event !== 'thinking') return;
  const d = ev.data;
  if (!d) return;
  if (ts) ts.classList.remove('collapsed');

  switch(d.type) {
    case 'text':
      msg.content += d.content;
      if (contentEl) contentEl.textContent = msg.content;
      // 同时将文本添加到思考过程区域
      if (tb && d.content) {
        const textDiv = document.createElement('div');
        textDiv.className = 'thinking-text';
        textDiv.textContent = d.content;
        tb.appendChild(textDiv);
      }
      break;
    case 'tool_use':
      msg.thinking.push(d);
      if (tb) tb.innerHTML += `<div class="tool-call"><span class="tool-name">🔧 ${esc(d.name)}</span> <span class="tool-input">${esc(d.input||'')}</span></div>`;
      break;
    case 'tool_result':
      msg.thinking.push(d);
      if (tb) tb.innerHTML += `<div class="tool-result-block"><details><summary>📎 工具返回</summary><pre class="tool-result-content">${esc(d.content||'')}</pre></details></div>`;
      break;
    case 'step_finish':
      if (d.tokens && tb) tb.innerHTML += `<div class="step-finish">Token: i=${d.tokens.input||0} o=${d.tokens.output||0} t=${d.tokens.total||0}</div>`;
      break;
  }
  scrollBottom(DOM.messages);
}

function renderAgentMsg(msg, container) {
  const c = container || DOM.messages;
  const div = document.createElement('div');
  if (msg.role === 'user') {
    div.className = 'message user';
    div.innerHTML = `<div class="msg-content">${esc(msg.content)}</div>`;
  } else if (msg.role === 'agent') {
    const a = S.agents.find(x => x.id === S.currentAgentId);
    const nm = a ? a.name : 'Agent';
    const th = (msg.thinking||[]).map(t => {
      if (t.type === 'tool_use') return `<div class="tool-call"><span class="tool-name">🔧 ${esc(t.name)}</span> <span class="tool-input">${esc(t.input||'')}</span></div>`;
      if (t.type === 'tool_result') return `<div class="tool-result-block"><details><summary>📎 工具返回</summary><pre class="tool-result-content">${esc(t.content||'')}</pre></details></div>`;
      return '';
    }).join('');
    div.innerHTML = `<div class="msg-header"><span class="msg-agent-icon">${getAvatar(S.currentAgentId)}</span>${esc(nm)}</div><div class="msg-content"></div>
      <div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">思考过程</span></div><div class="thinking-body">${th}</div></div>
      <div class="typing-dots" style="display:none"><span></span><span></span><span></span></div>`;
    const ce = div.querySelector('.msg-content');
    if (ce) ce.textContent = msg.content || '';
    if (msg.ts && S.isStreaming) {
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
async function selectGroup(id) {
  S.currentGroupId = id;
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

// ============ Group Chat ============
async function sendGroupMsg() {
  const text = DOM['group-input'].value.trim();
  if (!text || !S.currentGroupId) return;

  // Show user message
  const uMsg = { sender:'user', text, id:`m_${Date.now()}` };
  renderGroupMsg(uMsg);
  DOM['group-input'].value = ''; DOM['group-input'].style.height = 'auto';
  DOM['btn-group-send'].disabled = true;
  S.isStreaming = true; setStatus('busy');
  DOM['btn-group-send'].textContent = '...';

  try {
    const resp = await fetch(`/api/groups/${S.currentGroupId}/chat?sender=user&text=${encodeURIComponent(text)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let agentThinkingEls = {}; // agent_id -> DOM element

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
          switch (ev.event) {
            case 'group_message':
              // Already shown user message
              break;
            case 'routing':
              // Show system message
              renderGroupMsg({ sender:'system', text:`🔄 路由到 @${ev.data.to}...`, id:`r_${Date.now()}` });
              break;
            case 'agent_thinking':
              handleGroupThinking(ev.data);
              break;
            case 'agent_done':
              renderGroupMsg({ sender:'system', text:`✅ @${ev.data.agent_id} 已完成（回复 ${ev.data.reply_to}）`, id:`d_${Date.now()}` });
              break;
            case 'error':
              renderGroupMsg({ sender:'system', text:`❌ ${ev.data.message}`, id:`e_${Date.now()}` });
              break;
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    if (e.name !== 'AbortError') renderGroupMsg({ sender:'system', text:`错误: ${e.message}`, id:`e_${Date.now()}` });
  } finally {
    S.isStreaming = false; setStatus('online');
    DOM['btn-group-send'].textContent = '发送';
    updateGroupSendBtn();
  }
}

function handleGroupThinking(data) {
  // Find or create agent thinking block
  let block = document.getElementById(`gt-${data.agent_id}`);
  if (!block) {
    const div = document.createElement('div');
    div.className = 'message agent';
    div.id = `gt-${data.agent_id}`;
    div.innerHTML = `<div class="msg-header"><span class="msg-agent-icon">${getAvatar(data.agent_id)}</span>${esc(data.agent_id)} 思考中...</div>
      <div class="msg-content"></div>
      <div class="thinking-section"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">思考过程</span></div><div class="thinking-body"></div></div>`;
    DOM['group-messages'].appendChild(div);
    block = div;
    scrollBottom(DOM['group-messages']);
  }

  const tb = block.querySelector('.thinking-body');
  const ce = block.querySelector('.msg-content');
  if (!tb || !ce) return;

  switch(data.type) {
    case 'text':
      ce.textContent = (ce.textContent || '') + data.content;
      break;
    case 'tool_use':
      if (tb) tb.innerHTML += `<div class="tool-call"><span class="tool-name">🔧 ${esc(data.name)}</span></div>`;
      break;
    case 'step_finish':
      if (data.tokens && tb) tb.innerHTML += `<div class="step-finish">Token: ${data.tokens.total||0}</div>`;
      break;
  }
  scrollBottom(DOM['group-messages']);
}

function renderGroupMsg(msg, container) {
  const c = container || DOM['group-messages'];
  const div = document.createElement('div');

  if (msg.sender === 'user') {
    div.className = 'message group-user';
    div.innerHTML = `<div class="msg-header">你</div><div class="msg-content">${esc(msg.text)}</div>`;
  } else if (msg.sender === 'system') {
    div.className = 'message system';
    div.textContent = msg.text;
  } else {
    // Agent message
    const aId = msg.sender;
    div.className = 'message group-agent';
    div.innerHTML = `<div class="msg-header"><span class="msg-agent-icon">${getAvatar(aId)}</span>@${esc(aId)}</div><div class="msg-content">${esc(msg.text||'')}</div>`;
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
    DOM['manage-agent-table'].innerHTML = '<div class="empty">暂无 Agent，前往「创建」页面创建</div>';
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
    const r = await fetch('/api/config');
    const d = await r.json();
    const cfg = d.config || {};

    // Default backend
    const defBackend = cfg.system?.default_backend || 'opencode';
    const bSel = DOM['set-default-backend'];
    bSel.innerHTML = S.backends.map(b =>
      `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`
    ).join('');

    // Default model
    const defModel = cfg.system?.default_model || '';
    updateDefaultModelSelect(defBackend, defModel);

    bSel.onchange = () => updateDefaultModelSelect(bSel.value);

    // Port
    DOM['set-port'].value = cfg.system?.port || 8765;

    // Model aliases
    const aliases = cfg.backends?.opencode?.model_aliases || {};
    DOM['set-model-aliases'].value = JSON.stringify(aliases, null, 2);

  } catch(e) { showSetStatus('加载配置失败: '+e.message, 'error'); }
}

function updateDefaultModelSelect(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['set-default-model'];
  mSel.innerHTML = models.map(m =>
    `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`
  ).join('');
}

async function saveSettings() {
  const backend = DOM['set-default-backend'].value;
  const model = DOM['set-default-model'].value;
  const port = parseInt(DOM['set-port'].value) || 8765;
  let aliases = {};
  try {
    aliases = JSON.parse(DOM['set-model-aliases'].value || '{}');
  } catch(e) {
    showSetStatus('模型别名 JSON 格式错误', 'error');
    return;
  }

  try {
    // Load current config first to preserve unknown fields
    const r0 = await fetch('/api/config');
    const d0 = await r0.json();
    const cfg = d0.config || {};

    cfg.system = cfg.system || {};
    cfg.system.default_backend = backend;
    cfg.system.default_model = model;
    cfg.system.port = port;
    cfg.backends = cfg.backends || {};
    cfg.backends.opencode = cfg.backends.opencode || {};
    cfg.backends.opencode.model_aliases = aliases;

    // Also write models list from backend data
    const allModels = getBackendModels(backend);
    cfg.models = cfg.models || {};
    cfg.models[backend] = allModels.map(m => ({
      id: m.id, name: m.name, provider: m.provider, default: m.id === model,
    }));

    const r = await fetch('/api/config', {
      method: 'PUT', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ config: cfg }),
    });
    if (!r.ok) throw new Error('保存失败');
    showSetStatus('✓ 已保存，部分配置（端口）需重启生效', 'success');
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
function addAgentMsg(id, msg) {
  if (!S.agentMessages[id]) S.agentMessages[id] = [];
  S.agentMessages[id].push(msg);
}

function stopStream() {
  if (S.abortCtrl) S.abortCtrl.abort();
}

function setStatus(s) {
  const badge = DOM['status-badge'];
  badge.className = `status ${s}`;
  badge.textContent = s === 'online' ? '就绪' : s === 'busy' ? '处理中' : '离线';
}

function updateSendBtn() {
  DOM['btn-send'].disabled = S.isStreaming || !DOM['message-input'].value.trim() || !S.currentAgentId;
}

function updateGroupSendBtn() {
  DOM['btn-group-send'].disabled = S.isStreaming || !DOM['group-input'].value.trim() || !S.currentGroupId;
}

function scrollBottom(el) {
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

function removeTyping(el) {
  const td = el?.querySelector('.typing-dots');
  if (td) td.style.display = 'none';
}

function clearChat() {
  if (!S.currentAgentId) return;
  S.agentMessages[S.currentAgentId] = [];
  DOM.messages.innerHTML = '';
  DOM['message-input'].focus();
}

function clearGroupChat() {
  DOM['group-messages'].innerHTML = '';
}

// ============ Event Listeners ============
function setupEventListeners() {
  // Agent chat
  DOM['btn-send'].addEventListener('click', sendAgentMsg);
  DOM['message-input'].addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAgentMsg(); }
  });
  DOM['message-input'].addEventListener('input', () => {
    DOM['message-input'].style.height = 'auto';
    DOM['message-input'].style.height = Math.min(DOM['message-input'].scrollHeight, 120) + 'px';
    updateSendBtn();
  });
  DOM['btn-clear-chat'].addEventListener('click', clearChat);
  DOM['btn-agent-config'].addEventListener('click', openAgentConfig);

  // Group chat
  DOM['btn-group-send'].addEventListener('click', sendGroupMsg);
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
  DOM['btn-group-config'].addEventListener('click', openGroupConfig);

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

  // Settings save
  DOM['btn-save-settings']?.addEventListener('click', saveSettings);

  // Manage modal
  DOM['mm-save']?.addEventListener('click', saveManageModal);
  DOM['mm-cancel']?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));
  DOM['manage-modal']?.querySelector('.modal-close')?.addEventListener('click', () => DOM['manage-modal'].classList.add('hidden'));

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
      DOM['cf-status'].style.display = 'none';
      await loadAgents();
      switchTab('chat');
    } catch(e) {
      showFormStatus(e.message, 'error');
    } finally {
      DOM['cf-submit'].disabled = false;
      DOM['cf-submit'].textContent = '🚀 创建 Agent';
    }
  });

  // Thinking section toggle (delegated)
  DOM.messages.addEventListener('click', e => {
    const header = e.target.closest('.thinking-header');
    if (!header) return;
    const section = header.closest('.thinking-section');
    if (section) section.classList.toggle('collapsed');
  });

  // Close mention dropdown on outside click
  document.addEventListener('click', e => {
    if (S.mentionActive && !e.target.closest('#group-input') && !e.target.closest('.mention-dropdown')) {
      hideMentionDropdown();
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
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