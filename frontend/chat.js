// ============ Chat / DM ============

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
  const snapshot = { label: name, messages: msgs.map(m => ({ role: m.role, content: m.content, thinking: m.thinking })) };
  try {
    const r = await fetch(`/api/chat/${id}/archive`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ snapshot }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(apiErr(d, `HTTP ${r.status}`)); }
  } catch (e) { alert('删除失败: ' + e.message); return; }
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
    if (!r.ok) throw new Error(apiErr(d, '恢复失败'));
    S.hiddenAgents.delete(agentId);
    if (d.snapshot?.messages?.length) {
      S.agentMessages[agentId] = d.snapshot.messages;
      saveChatHistory();
    }
    hideSearchResults('agent');
    renderAgentList();
    selectAgent(agentId);
  } catch (e) { alert('恢复失败: ' + e.message); }
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
      : '<div class="search-item no-match"><span class="sub">无匹配归档</span></div>';
    box.querySelectorAll('[data-restore-agent]').forEach(el => {
      el.addEventListener('click', () => restoreChatWindow(el.dataset.restoreAgent));
    });
    box.classList.remove('hidden');
  } catch (e) { console.warn('searchChatArchives:', e); }
}

function hideSearchResults(kind) {
  const box = kind === 'group' ? DOM['group-search-results'] : DOM['agent-search-results'];
  if (box) box.classList.add('hidden');
}

// --- Agent Selection ---
function selectAgent(id, opts = {}) {
  S.currentAgentId = id;
  S.currentGroupId = null;
  S.currentProjectId = null;
  (S.agentMessages[id] || []).forEach(m => { m._new = false; });
  renderAgentList();
  DOM.welcome.classList.add('hidden');
  DOM['chat-view'].classList.remove('hidden');
  const a = S.agents.find(x => x.id === id);
  if (a) {
    DOM['chat-agent-name'].textContent = a.name || a.id;
    DOM['chat-agent-id'].textContent = [a.backend, a.model].filter(Boolean).join(' · ');
    applyAvatar(DOM['chat-agent-avatar'], id, 'agent');
    updateContextIndicator(S.contextTokens[id] || 0);
  }
  DOM.messages.innerHTML = '';
  if (S.agentMessages[id]) {
    S.agentMessages[id].forEach(m => renderAgentMsg(m, DOM.messages, id));
    scrollBottom(DOM.messages, true);
  }
  if (isStreamBusy(streamKeyAgent(id))) rebindAgentStreamDom(id);
  hideNewMsgFloater();
  void syncAgentChatFromServer(id);
  DOM['message-input'].disabled = false;
  DOM['message-input'].focus();
  refreshStatusBadge();
  updateSendBtn();
  connectAgentEvents(id);
  if (!opts.restore) saveUiState();
}

// --- DM History ---
async function loadDmHistory(id) {
  await syncAgentChatFromServer(id);
  loadBackgroundChats(id);
}

async function loadBackgroundChats(agentId) {
  try {
    const r = await fetch(`/api/agents/${encodeURIComponent(agentId)}/chats`);
    const d = await r.json();
    const msgs = d.messages || [];
    let existing = S.agentMessages[agentId] || [];
    let changed = false;
    for (const m of msgs) {
      if (!existing.some(x => x.ts === m.ts)) { existing.push(m); changed = true; }
    }
    if (changed) {
      S.agentMessages[agentId] = existing;
      if (agentId === S.currentAgentId) {
        if (isStreamBusy(streamKeyAgent(agentId))) rebindAgentStreamDom(agentId);
        else {
          DOM.messages.innerHTML = '';
          existing.forEach(m => renderAgentMsg(m, DOM.messages, agentId));
          scrollBottom(DOM.messages, true);
        }
      }
    }
  } catch (e) { /* ignore */ }
}

// --- Send ---
async function sendAgentMsg() {
  const text = DOM['message-input'].value.trim();
  const aid = S.currentAgentId;
  const skey = streamKeyAgent(aid);
  if (!text || !aid || isStreamBusy(skey)) return;
  const msg = { role:'user', content:text, ts: Date.now() };
  addAgentMsg(aid, msg);
  renderAgentMsg(msg, DOM.messages, aid);
  scrollBottom(DOM.messages, true);
  DOM['message-input'].value = ''; DOM['message-input'].style.height = 'auto';
  const st = ensureStream(skey);
  st.busy = true;
  S.isStreaming = true;
  setStatus('busy');
  updateSendBtn();
  const aMsg = { role:'agent', content:'', thinking:[], ts: Date.now() };
  addAgentMsg(aid, aMsg);
  const el = renderAgentMsg(aMsg, DOM.messages, aid);
  const tb = el?.querySelector('.thinking-body');
  const ts = el?.querySelector('.thinking-section');
  const ce = el?.querySelector('.msg-content');
  try {
    st.abortCtrl = new AbortController();
    S.abortCtrl = st.abortCtrl;
    const resp = await fetch(`/api/chat/${aid}?message=${encodeURIComponent(text)}`, { signal: st.abortCtrl.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    st.reader = reader;
    S.currentReader = reader;
    st.ctx = { mode: 'agent', userText: text, agentEl: el, agentId: aid, aMsg,
      contentEl: ce, tb, ts };
    st.userCancelled = false;
    S.streamContext = st.ctx;
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
          const ui = resolveAgentStreamUi(aid, aMsg);
          handleChatEvent(ev, aMsg, ui.ce, ui.tb, ui.ts, ui.el);
        } catch(e) {}
      }
    }
    if (ce && !aMsg.content && !aMsg.thinking.length) { renderBubbleMarkdown(ce, '(空响应)'); }
  } catch(e) {
    if (e.name === 'AbortError' && st.userCancelled) rollbackAgentTurn(text, el, aid);
    else if (e.name !== 'AbortError' && S.currentAgentId === aid) showAgentError(el, e.message);
    else if (e.name !== 'AbortError') aMsg.content = aMsg.content || `错误：${e.message}`;
  } finally {
    const wasCancelled = st.userCancelled;
    const onView = S.currentAgentId === aid;
    const liveEl = onView ? (st.ctx?.agentEl?.isConnected ? st.ctx.agentEl : el) : null;
    st.busy = false;
    st.userCancelled = false;
    st.abortCtrl = null;
    st.reader = null;
    st.ctx = null;
    if (onView) {
      S.currentReader = null;
      S.streamContext = null;
      S.isStreaming = false;
    }
    refreshStatusBadge();
    updateSendBtn();
    if (onView && liveEl) {
      scrollBottom(DOM.messages);
      removeTyping(liveEl);
      const tsEl = liveEl.querySelector('.thinking-section');
      const tbEl = liveEl.querySelector('.thinking-body');
      const ceFin = liveEl.querySelector('.msg-content');
      if (tsEl && tbEl && !tbEl.children.length) tsEl.style.display = 'none';
      if (tsEl) updateThinkingHeader(tsEl, aMsg, false);
      if (ceFin && !aMsg.content && !aMsg.thinking?.length) renderBubbleMarkdown(ceFin, '(空响应)');
    } else if (!onView) {
      renderAgentList();
    }
    if (!wasCancelled) {
      finalizeAgentMsgFromThinking(aMsg);
      void syncAgentChatFromServer(aid);
    } else {
      saveChatHistory();
    }
  }
}

// --- Agent Events ---
function disconnectAgentEvents(agentId) {
  const id = agentId || S.currentAgentId;
  if (!id) return;
  const es = S.agentEventSources[id];
  if (es) { es.close(); delete S.agentEventSources[id]; }
  if (S.agentEventSource === es) S.agentEventSource = null;
}
function ensureAgentTaskBlock(agentId) {
  const live = S.agentTaskBlocks[agentId];
  if (live?.el?.isConnected) return live;
  const msg = { role: 'agent', content: '', thinking: [], ts: Date.now(), background: true };
  if (!S.agentMessages[agentId]) S.agentMessages[agentId] = [];
  S.agentMessages[agentId].push(msg);
  let el = null;
  if (S.currentAgentId === agentId) { el = renderAgentMsg(msg, DOM.messages, agentId); scrollBottom(DOM.messages); }
  S.agentTaskBlocks[agentId] = { msg, el };
  return S.agentTaskBlocks[agentId];
}
function handleAgentBackgroundEvent(ev) {
  if (!ev || !ev.event) return;
  const agentId = ev.data?.agent_id || S.currentAgentId;
  if (!agentId) return;
  if (S.hiddenAgents.has(agentId)) {
    fetch(`/api/chat/${encodeURIComponent(agentId)}/restore`, { method: 'POST' }).catch(() => {});
    S.hiddenAgents.delete(agentId); renderAgentList();
  }
  if (S.currentAgentId !== agentId) return;
  switch (ev.event) {
    case 'agent_thinking': {
      const block = ensureAgentTaskBlock(agentId);
      if (!block.el && S.currentAgentId === agentId) block.el = renderAgentMsg(block.msg, DOM.messages, agentId);
      const el = block.el; if (!el) return;
      const tb = el.querySelector('.thinking-body'), ts = el.querySelector('.thinking-section'), ce = el.querySelector('.msg-content');
      handleThinking(ev.data, block.msg, ce, tb, ts, el);
      if (document.querySelector('.nav-tab.active')?.dataset.tab === 'chat') renderAgentList();
      break;
    }
    case 'agent_done': delete S.agentTaskBlocks[agentId]; break;
    case 'error':
      if (S.currentAgentId === agentId) renderAgentMsg({ role: 'agent', content: `错误：${ev.data?.message || '未知错误'}`, ts: Date.now() }, DOM.messages, agentId);
      break;
  }
}
function connectAgentEvents(agentId) {
  if (!agentId || S.agentEventSources[agentId]) return;
  const es = new EventSource(`/api/agents/${encodeURIComponent(agentId)}/events`);
  S.agentEventSources[agentId] = es;
  S.agentEventSource = es;
  es.onmessage = (e) => {
    if (!e.data || e.data === '[DONE]') return;
    try { handleAgentBackgroundEvent(JSON.parse(e.data)); } catch (err) { console.warn('agent event parse:', err); }
  };
  es.onerror = () => {
    disconnectAgentEvents(agentId);
    setTimeout(() => { connectAgentEvents(agentId); }, 3000);
  };
}

// --- Clear ---
async function clearChat() {
  if (!S.currentAgentId) return;
  if (isStreamBusy(streamKeyAgent(S.currentAgentId))) cancelActiveStream();
  const ok = await showConfirm('清空后将删除：\n· 本页所有对话记录（浏览器本地）\n· Agent 多轮上下文（OpenCode Session）\n下次对话 Agent 不会记得之前聊过什么。');
  if (!ok) return;
  try {
    const r = await fetch(`/api/chat/${S.currentAgentId}/clear`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(apiErr(d, d.message || `HTTP ${r.status}`));
  } catch (e) { alert('清空失败: ' + e.message); return; }
  S.agentMessages[S.currentAgentId] = [];
  resetContextTokens(S.currentAgentId);
  DOM.messages.innerHTML = '';
  saveChatHistory();
  DOM['message-input'].focus();
}

// --- Agent Config ---
async function openAgentConfig() {
  if (!S.currentAgentId) return;
  const a = S.agents.find(x => x.id === S.currentAgentId);
  if (!a) return;
  DOM['modal-agent-info'].textContent = `${a.name} (${a.id})`;
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
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ backend, model }),
    });
    await loadAgents(); renderAgentList(); selectAgent(S.currentAgentId);
    DOM['modal-overlay'].classList.add('hidden');
  } catch(e) { alert('保存失败: '+e.message); }
}