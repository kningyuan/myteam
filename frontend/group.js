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
    const ts = groupLastActivityTs(g);
    const projTag = g.project_id ? '<span class="s-tag s-tag-project" title="属于一个项目（自动建群）">项目</span>' : '';
    const preview = msgPreviewText(g.last_message || g.last_message_text || g.description || '') || `${g.member_count || 0} 名成员`;
    return `<div class="sidebar-item ${S.currentGroupId === g.id ? 'active' : ''}" data-id="${g.id}">
      <span class="s-icon avatar-badge avatar-group">${esc(getAvatar(g.name || g.id))}</span>
      <span class="s-main">
        <span class="s-row1"><span class="s-name">${esc(g.name)}${projTag}</span><span class="s-time">${esc(fmtListTime(ts))}</span></span>
        <span class="s-row2"><span class="s-preview">${esc(truncateText(preview, 48))}</span></span>
      </span>
    </div>`;
  }).join('');
  DOM['group-list'].querySelectorAll('.sidebar-item').forEach(el => {
    el.addEventListener('click', () => selectGroup(el.dataset.id));
  });
}

// --- Members detail panel (Discord-style) ---
let _membersCollapsed = localStorage.getItem('agentHub_membersPanel') === '1';

function renderGroupMembersPanel(members) {
  const panel = DOM['group-members-panel'];
  const list = DOM['group-members-list'];
  if (!panel || !list) return;
  const ms = members || S.groupMembers || [];
  if (DOM['group-members-count']) DOM['group-members-count'].textContent = ms.length;
  list.innerHTML = ms.length ? ms.map(id => {
    const a = S.agents.find(x => x.id === id);
    return `<div class="member-row" title="@${esc(id)}">
      <span class="m-avatar avatar-badge">${esc(getAvatar(id))}</span>
      <span class="m-meta"><span class="m-name">${esc(a ? a.name : id)}</span><span class="m-sub">@${esc(id)}</span></span>
    </div>`;
  }).join('') : '<div class="empty no-icon">暂无成员</div>';
  updateMembersPanelVisibility();
}
function updateMembersPanelVisibility() {
  const panel = DOM['group-members-panel'];
  if (!panel) return;
  const show = !!S.currentGroupId && !_membersCollapsed;
  panel.classList.toggle('hidden', !show);
  panel.classList.toggle('force-open', show);
}
function toggleMembersPanel() {
  _membersCollapsed = !_membersCollapsed;
  try { localStorage.setItem('agentHub_membersPanel', _membersCollapsed ? '1' : '0'); } catch (_) {}
  updateMembersPanelVisibility();
}
async function refreshMembersPanel() {
  if (!S.currentGroupId) return;
  try {
    const r = await fetch(`/api/groups/${S.currentGroupId}`);
    const d = await r.json();
    S.groupMembers = d.group?.members || [];
    renderGroupMembersPanel(S.groupMembers);
  } catch (_) { /* ignore */ }
}

// --- Select Group ---
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
    renderGroupMembersPanel(g.members || []);
    (g.messages||[]).forEach(m => { renderGroupMsg(m); });
    scrollBottom(DOM['group-messages'], true);
  } catch(e) { console.error(e); }
  DOM['group-input'].disabled = false;
  DOM['group-input'].focus();
  refreshStatusBadge();
  updateGroupSendBtn();
  populateGroupMemberSelect();
  connectGroupEvents(id);
  if (!opts.restore) saveUiState();
}

// --- Send ---
async function sendGroupMsg() {
  const text = DOM['group-input'].value.trim();
  const gid = S.currentGroupId;
  const skey = streamKeyGroup(gid);
  if (!text || !gid || isStreamBusy(skey)) return;
  const uMsg = { sender:'user', text, id:`m_${Date.now()}` };
  renderGroupMsg(uMsg);
  DOM['group-input'].value = ''; DOM['group-input'].style.height = 'auto';
  const st = ensureStream(skey);
  st.busy = true;
  S.isStreaming = true;
  setStatus('busy');
  updateGroupSendBtn();
  try {
    st.abortCtrl = new AbortController();
    S.abortCtrl = st.abortCtrl;
    st.ctx = { mode: 'group', userText: text, groupId: gid };
    S.streamContext = st.ctx;
    const resp = await fetch(`/api/groups/${gid}/chat?sender=user&text=${encodeURIComponent(text)}`, { signal: st.abortCtrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    st.reader = reader;
    S.currentReader = reader;
    const dec = new TextDecoder(); let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      const lines = buf.split('\n'); buf = lines.pop() || '';
      for (const line of lines) {
        const t = line.trim();
        if (!t || t === 'data: [DONE]') continue;
        if (!t.startsWith('data: ')) continue;
        try { const ev = JSON.parse(t.slice(6)); handleGroupStreamEvent(ev); } catch(e) {}
      }
    }
  } catch(e) {
    if (e.name === 'AbortError') { rollbackGroupTurn(text); }
    else { renderGroupMsg({ sender:'system', text:`错误: ${e.message}`, id:`e_${Date.now()}` }); }
  } finally {
    st.busy = false;
    st.abortCtrl = null;
    st.reader = null;
    st.ctx = null;
    if (S.currentGroupId === gid) {
      S.currentReader = null;
      S.streamContext = null;
      S.isStreaming = false;
    }
    refreshStatusBadge();
    updateGroupSendBtn();
  }
}

// --- Events ---
function disconnectGroupEvents() {
  if (S.groupEventSource) { S.groupEventSource.close(); S.groupEventSource = null; }
}
function handleGroupStreamEvent(ev) {
  if (!ev || !ev.event) return;
  const now = Date.now();
  if (S.currentGroupId) S.groupActivityTs[S.currentGroupId] = now;
  if (ev.data?.group_id && S.currentGroupId && ev.data.group_id === S.currentGroupId) {
    const g = S.groups.find(x => x.id === S.currentGroupId);
    if (g && g.status === 'dissolved') { fetch(`/api/groups/${S.currentGroupId}/restore`, { method: 'POST' }).catch(() => {}); g.status = 'active'; }
  }
  switch (ev.event) {
    case 'group_message': if (ev.data?.sender && ev.data.sender !== 'user') renderGroupMsg({ sender: ev.data.sender, text: ev.data.text, id: ev.data.msg_id || `m_${Date.now()}` }); break;
    case 'routing': renderGroupMsg({ sender: 'system', text: `🔄 路由到 @${ev.data.to}...`, id: `r_${Date.now()}` }); break;
    case 'agent_thinking': handleGroupThinking(ev.data); break;
    case 'agent_done': renderGroupMsg({ sender: 'system', text: `@${ev.data.agent_id} 已完成`, id: `d_${Date.now()}` }); break;
    case 'error': renderGroupMsg({ sender: 'system', text: `错误：${ev.data.message}`, id: `e_${Date.now()}` }); break;
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
    setTimeout(() => { if (S.currentGroupId === groupId) connectGroupEvents(groupId); }, 3000);
  };
}
function handleGroupThinking(data) {
  let block = document.getElementById(`gt-${data.agent_id}`);
  if (!block) {
    const c = DOM['group-messages']; const aId = data.agent_id; const mts = Date.now(); const gkey = 'agent:' + aId;
    _dateSep(c, mts);
    const grouped = _grouped(c, gkey, mts);
    const div = document.createElement('div');
    div.className = 'message group-agent' + (grouped ? ' grouped' : ''); div.id = `gt-${aId}`;
    div.dataset.gkey = gkey; div.dataset.ts = String(mts); div.dataset.day = dayKeyOf(mts);
    div.innerHTML = '<div class="msg-avatar avatar-badge" aria-label="' + esc(aId) + '">' + esc(getAvatar(aId)) + '</div>' +
      '<div class="bubble">' + (grouped ? '' : '<div class="bubble-name">@' + esc(aId) + '</div>') +
      '<div class="thinking-section collapsed" aria-expanded="false"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">Agent 活动</span></div><div class="thinking-body"></div></div>' +
      '<div class="msg-content"></div>' + msgMetaHtml(mts) + '</div>';
    c.appendChild(div); block = div; scrollBottom(c);
  }
  const tb = block.querySelector('.thinking-body'); const ce = block.querySelector('.msg-content'); const ts = block.querySelector('.thinking-section');
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
  if (S.currentGroupId) { S.groupActivityTs[S.currentGroupId] = Date.now(); if (document.querySelector('.nav-tab.active')?.dataset.tab === 'groups') renderGroupList(); }
  const c = container || DOM['group-messages'];
  const mts = msg.timestamp ? Math.round(msg.timestamp * 1000) : (msg.ts || Date.now());
  const sender = msg.sender; const isUser = sender === 'user'; const isSystem = sender === 'system';
  const gkey = isUser ? 'user' : (isSystem ? 'system' : 'agent:' + sender);
  if (!isSystem) _dateSep(c, mts);
  const grouped = _grouped(c, gkey, mts);
  const div = document.createElement('div');
  div.dataset.gkey = gkey; div.dataset.ts = String(mts); div.dataset.day = dayKeyOf(mts);
  if (isUser) {
    div.className = 'message group-user' + (grouped ? ' grouped' : '');
    div.innerHTML = '<div class="bubble"><div class="msg-content">' + esc(msg.text || '') + '</div>' + msgMetaHtml(mts) + '</div>';
  } else if (isSystem) {
    div.className = 'message system';
    div.innerHTML = esc(msg.text || '').replace(/\n/g, '<br>');
  } else {
    const aId = sender;
    div.className = 'message group-agent' + (grouped ? ' grouped' : '');
    div.innerHTML = '<div class="msg-avatar avatar-badge" aria-label="' + esc(aId) + '">' + esc(getAvatar(aId)) + '</div>' +
      '<div class="bubble">' + (grouped ? '' : '<div class="bubble-name">@' + esc(aId) + '</div>') +
      '<div class="msg-content"></div>' + msgMetaHtml(mts) + '</div>';
    const ce = div.querySelector('.msg-content');
    if ((msg.text || '').includes('📋')) { ce.innerHTML = esc(msg.text || '').replace(/\n/g, '<br>'); }
    else { renderBubbleMarkdown(ce, msg.text || ''); }
  }
  c.appendChild(div); scrollBottom(c); return div;
}

// --- Clear ---
async function clearGroupChat() {
  if (!S.currentGroupId) return;
  if (isStreamBusy(streamKeyGroup(S.currentGroupId))) cancelActiveStream();
  const ok = await showConfirm('清空后将删除本群组的所有消息记录。\n说明：各 Agent 的私聊上下文需在对应 Agent 对话里单独清空。', {title:'清空群消息', okText:'清空', danger:true});
  if (!ok) return;
  try {
    const r = await fetch(`/api/groups/${S.currentGroupId}/clear`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErr(d, d.message || `HTTP ${r.status}`));
  } catch (e) { alert('清空失败: ' + e.message); return; }
  DOM['group-messages'].innerHTML = '';
}

// --- Dissolve / Restore ---
async function dissolveGroupWindow() {
  if (!S.currentGroupId) return;
  const g = S.groups.find(x => x.id === S.currentGroupId);
  const name = g ? g.name : S.currentGroupId;
  if (!await showConfirm(`解散群组「${name}」？\n· 从列表隐藏，可搜索恢复\n· 不删除 tasks/ 项目数据\n· 消息记录将清空`, {title:'解散群组', okText:'解散', danger:true})) return;
  try {
    const r = await fetch(`/api/groups/${S.currentGroupId}/dissolve`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErr(d, `HTTP ${r.status}`));
  } catch (e) { alert('解散失败: ' + e.message); return; }
  S.currentGroupId = null;
  DOM['group-welcome'].classList.remove('hidden');
  DOM['group-chat-view'].classList.add('hidden');
  updateMembersPanelVisibility();
  await loadGroups(); renderGroupList();
}
async function restoreGroupWindow(groupId) {
  try {
    const r = await fetch(`/api/groups/${groupId}/restore`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErr(d, '恢复失败'));
    hideSearchResults('group');
    await loadGroups(); renderGroupList(); selectGroup(groupId);
  } catch (e) { alert('恢复失败: ' + e.message); }
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
      : '<div class="search-item no-match"><span class="sub">无匹配群组</span></div>';
    box.querySelectorAll('[data-restore-group]').forEach(el => {
      el.addEventListener('click', () => {
        const gid = el.dataset.restoreGroup;
        if (el.dataset.dissolved === '1') restoreGroupWindow(gid);
        else { hideSearchResults('group'); selectGroup(gid); }
      });
    });
    box.classList.remove('hidden');
  } catch (e) { console.warn('searchGroupsArchive:', e); }
}

// --- @mention ---
function showMentionDropdown(filter) {
  const dd = DOM['mention-dropdown'];
  if (!dd || !S.groupMembers.length) return;
  const matched = S.groupMembers.filter(m => m.includes(filter));
  if (!matched.length) { dd.classList.add('hidden'); return; }
  dd.innerHTML = matched.map((m, i) => {
    const agent = S.agents.find(a => a.id === m);
    return `<div class="mention-item ${i === 0 ? 'active' : ''}" data-id="${m}">
      <span class="m-icon avatar-badge">${esc(agent ? getAvatar(m) : '?')}</span>
      <span class="m-name">${agent ? esc(agent.name) : esc(m)}</span>
      <span class="m-id">@${esc(m)}</span>
    </div>`;
  }).join('');
  dd.classList.remove('hidden');
  S.mentionActive = true; S.mentionFilter = filter; S.mentionIdx = 0;
  dd.querySelectorAll('.mention-item').forEach(el => { el.addEventListener('click', () => insertMention(el.dataset.id)); });
}
function hideMentionDropdown() {
  const dd = DOM['mention-dropdown'];
  if (dd) dd.classList.add('hidden');
  S.mentionActive = false; S.mentionFilter = ''; S.mentionIdx = -1;
}
function insertMention(agentId) {
  const input = DOM['group-input']; const val = input.value; const pos = input.selectionStart;
  let atPos = pos - 1;
  while (atPos >= 0 && val[atPos] !== '@') atPos--;
  if (atPos < 0) { hideMentionDropdown(); return; }
  input.value = val.slice(0, atPos) + `@${agentId} ` + val.slice(pos);
  input.focus();
  const newPos = atPos + agentId.length + 2;
  input.setSelectionRange(newPos, newPos);
  hideMentionDropdown(); updateGroupSendBtn();
}

// --- Group Config ---
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
      openGroupConfig(); loadGroups(); renderGroupList(); refreshMembersPanel();
    });
  });
  populateGroupMemberSelect();
  DOM['group-config-modal'].classList.remove('hidden');
}
async function populateGroupMemberSelect() {
  const sel = DOM['group-add-agent']; if (!sel) return;
  await loadAgents();
  const groupId = S.currentGroupId; let members = [];
  try { const r = await fetch(`/api/groups/${groupId}`); const d = await r.json(); members = d.group?.members || []; } catch(e) {}
  const available = S.agents.filter(a => !members.includes(a.id));
  sel.innerHTML = available.map(a => `<option value="${a.id}">${esc(a.name || a.id)}</option>`).join('');
  sel.size = Math.min(available.length || 1, 8);
}