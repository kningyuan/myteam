// ============ State ============
const S = {
  agents: [], backends: [], groups: [], projects: [],
  currentAgentId: null, currentGroupId: null, currentProjectId: null,
  isStreaming: false, abortCtrl: null, currentReader: null,
  streamContext: null,
  streams: {},
  groupEventSource: null,
  agentEventSource: null,
  agentEventSources: {},
  agentTaskBlocks: {},
  sidebarPollTimer: null,
  groupActivityTs: {},
  agentMessages: {}, groupMessages: {},
  hiddenAgents: new Set(),
  backendsCache: {},
  mentionActive: false, mentionFilter: '',
  mentionIdx: -1, groupMembers: [],
  contextTokens: {},
};

const CONTEXT_TOKEN_BUDGET = 25000;

// 统一错误提取：兼容 {error:{message}}（APIError）与 {detail}（HTTPException）两种信封；
// detail 为数组（422 校验错误）时摊平为可读文案。契约见 docs/接口一致性整改方案.md §4.2
function apiErr(d, fallback) {
  if (!d) return fallback;
  const detail = Array.isArray(d.detail) ? d.detail.map(e => e?.msg || e).join('; ') : d.detail;
  return d.error?.message || detail || fallback;
}

S.api = {
  init: async () => {
    try {
      const r = await fetch('/api/init', {method:'POST'});
      const d = await r.json();
      if (!r.ok) throw new Error(apiErr(d, '初始化失败'));
      showToast(d.message || '初始化完成');
      if (typeof renderDashboard === 'function') renderDashboard();
    } catch (e) { showToast('初始化失败：' + e.message, 'error'); }
  },
  runDemo: async () => {
    try {
      const r = await fetch('/api/demo', {method:'POST'});
      const d = await r.json();
      if (!r.ok) throw new Error(apiErr(d, '启动失败'));
      showToast('Demo 已启动');
      if (typeof switchTab === 'function') switchTab('projects');
      if (typeof selectProject === 'function') selectProject(d.project_id);
    } catch (e) { showToast('Demo 启动失败：' + e.message, 'error'); }
  },
};

S.ui = {
  showNewProjectModal: () => {
    const m = document.getElementById('new-project-modal');
    if (m) m.style.display = 'flex';
  },
};

const CHAT_HISTORY_KEY = 'agentHub_chatHistory_v3';
const UI_STATE_KEY = 'agentHub_uiState_v2';
const THEME_KEY = 'agentHub_theme';
const CHAT_HISTORY_MAX = 300;

// ============ DOM Refs ============
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);
const DOM = {};

function cacheDom() {
  ['agent-list','group-list','messages','group-messages','welcome','chat-view',
   'group-welcome','group-chat-view','message-input','group-input','btn-send','btn-group-send','context-indicator',
   'btn-clear-chat','btn-delete-chat','btn-clear-group','btn-dissolve-group',
   'btn-chat-more','chat-more-dropdown','new-msg-floater',
   'btn-group-more','group-more-dropdown',
   'agent-search','agent-search-results','group-search','group-search-results',
   'chat-agent-name','chat-agent-id','chat-agent-avatar',
   'group-name','group-members','group-avatar',
   'cf-description','cf-agent-id','cf-name','cf-backend','cf-model','cf-submit','cf-cancel','cf-status','cf-result',
   'tab-chat','tab-groups','tab-projects','tab-manage','tab-workflows','tab-settings',
   'project-list','project-count','project-welcome','project-detail-view',
   'project-title','project-meta','project-progress-text','project-progress-fill',
   'project-tasks','project-fleet','project-cost','project-cost-overview','project-events','project-launch-config',
   'project-trace','trace-title','trace-body','trace-close',
   'home-stats','home-projects','btn-home-new-project',
   'project-deliverable','deliverable-title','deliverable-task-nav','deliverable-meta','deliverable-files','deliverable-body',
   'btn-deliverable-copy','btn-deliverable-download',
   'btn-sidebar-toggle','sidebar-backdrop','sidebar','btn-open-group','btn-open-project',
   'btn-new-project','btn-new-project-welcome','new-project-modal','btn-resume-project','btn-cancel-project',
   'np-goal','np-title','np-mode','np-budget','np-review','np-split','np-workflow','np-workflow-hint','np-submit','np-cancel',
   'set-default-budget','set-max-gate-retries','set-soft-idle','set-hard-idle','set-max-cycles',
   'set-split-default','set-parallel-default','set-max-parallel','set-max-concurrent-projects',
   'wf-list','wf-new','wf-welcome','wf-editor','wf-id','wf-version','wf-description','wf-suggest',
   'wf-review','wf-split','wf-parallel','wf-max-parallel',
   'wf-tasks-body','wf-add-task','wf-save','wf-delete','wf-status',
   'set-budget-degrade-threshold','set-budget-degrade-backend','set-budget-degrade-model',
   'btn-theme','theme-dropdown',
   'modal-overlay','agent-config-modal','modal-backend','modal-model','modal-agent-info',
   'modal-save','modal-cancel','btn-agent-config',
   'group-config-modal','group-modal-name','group-modal-members','group-add-agent','btn-add-member','group-modal-close',
   'group-members-panel','group-members-list','group-members-count','btn-toggle-members',
   'new-group-modal','ng-name','ng-desc','ng-submit','ng-cancel','btn-new-group',
   'status-badge','agent-count','btn-group-config','btn-send','btn-group-send',
   'manage-agent-table','manage-agent-count','manage-agent-search','btn-create-agent','btn-sync-task-types',
   'manage-tasktype-table','manage-tasktype-count','manage-tasktype-search',
   'manage-dt-table','manage-dt-count','manage-dt-search','btn-new-dt','dt-upload',
   'dt-modal','dt-modal-title','dt-id','dt-display-name','dt-description','dt-task-types','dt-default-for','dt-sections','dt-yaml','dt-save','dt-cancel','dt-status',
   'kb-table','kb-count','kb-search',
   'create-agent-modal',
    'set-default-backend','set-default-model','set-port','set-cli-path','set-debug','set-audit-log','set-audit-log-max-bytes','set-price',
    'set-model-aliases','btn-save-settings','set-status','btn-apply-model-all',
    'set-use-project-group','set-enable-telegram','set-auto-group','set-auto-group-include-main','set-auto-group-name-prefix','set-hub-url','set-default-review',
   'set-poll-interval','set-ack-timeout','set-task-timeout',
   'set-agent-msg-timeout','set-team-config-timeout','set-task-plan-timeout','set-max-retries',
   'mention-dropdown',
   'manage-modal','mm-id','mm-name','mm-backend','mm-model','mm-workspace','mm-task-types','mm-suggest-task-types','mm-save','mm-cancel','mm-status',
   'tasktype-modal','tt-modal-title','tt-description','tt-suggest','tt-id','tt-display-name','tt-outcome','tt-outcome-hint','tt-sections','tt-save','tt-cancel','tt-status','btn-new-tasktype',
  ].forEach(id => DOM[id] = $(id));
}

// ============ Icons ============
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
  play: '<polygon points="8,5 19,12 8,19" class="fill"/>',
  flow: '<circle cx="6" cy="5" r="2.5"/><circle cx="18" cy="5" r="2.5"/><circle cx="12" cy="19" r="2.5"/><path d="M6 7.5v3a3 3 0 0 0 3 3h3M18 7.5v3a3 3 0 0 1-3 3h-3"/><line x1="12" y1="13.5" x2="12" y2="16.5"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="15" y1="4" x2="15" y2="20"/>',
  book: '<path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4Z"/><path d="M8 4h9a3 3 0 0 1 3 3v13H8V4Z"/>',
  tag: '<path d="M4 10.5V4a2 2 0 0 1 2-2h6.5L20 9.5V20a2 2 0 0 1-2 2h-5.5"/><circle cx="8" cy="8" r="1.5" class="fill"/>',
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

// ============ Utilities ============
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

/** Agent UI 标签：中文显示名优先，无中文名时回退 id */
function agentDisplayLabel(agentOrId, agents) {
  const list = agents || (typeof S !== 'undefined' ? S.agents : []) || [];
  const id = typeof agentOrId === 'string' ? agentOrId : agentOrId?.id;
  if (!id) return '';
  const a = typeof agentOrId === 'object' && agentOrId != null && 'name' in agentOrId
    ? agentOrId
    : list.find(x => x.id === id);
  const name = (a?.name || '').trim();
  if (name && name !== id) return name;
  return id;
}

function agentDisplayName(id) {
  return agentDisplayLabel(id);
}

/** task_type 注册表缓存（UI 中文名解析） */
let _taskTypeRecords = null;

async function ensureTaskTypeRecords() {
  if (_taskTypeRecords) return _taskTypeRecords;
  try {
    const r = await fetch('/api/task-types');
    const d = await r.json();
    _taskTypeRecords = d.task_types || [];
  } catch (_) {
    _taskTypeRecords = [];
  }
  return _taskTypeRecords;
}

function setTaskTypeRecords(list) {
  _taskTypeRecords = Array.isArray(list) ? list : null;
}

function invalidateTaskTypeRecords() {
  _taskTypeRecords = null;
}

/** task_type UI 标签：优先 display_name（中文），注册键仍为 value / API id */
function taskTypeDisplayLabel(taskTypeOrRow, metaList) {
  const id = typeof taskTypeOrRow === 'string' ? taskTypeOrRow : taskTypeOrRow?.task_type;
  if (!id) return '';
  const row = typeof taskTypeOrRow === 'object' && taskTypeOrRow?.display_name
    ? taskTypeOrRow
    : (metaList || _taskTypeRecords || []).find(x => x.task_type === id);
  return (row?.display_name || id).trim() || id;
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
function _grouped(c, gkey, mts) {
  const prev = c.lastElementChild;
  if (prev && prev.classList && prev.classList.contains('message') && prev.dataset.gkey === gkey) {
    const lt = parseInt(prev.dataset.ts || '0', 10);
    return (mts && lt) ? Math.abs(mts - lt) < 300000 : (!mts && !lt);
  }
  return false;
}
function getAvatarInitials(id) {
  if (!id) return '?';
  const label = agentDisplayName(id);
  const han = label.replace(/[^\u4e00-\u9fff]/g, '');
  if (han.length >= 2) return han.slice(-2);
  if (han.length === 1) return han;
  const parts = String(id).split(/[-_]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  const s = String(id);
  return (s.length >= 2 ? s.slice(0, 2) : s).toUpperCase();
}
function getAvatar(id) { return getAvatarInitials(id); }
function applyAvatar(el, id, kind) {
  if (!el) return;
  el.classList.add('avatar-badge');
  if (kind) el.classList.add(`avatar-${kind}`);
  el.textContent = getAvatarInitials(id);
  const label = agentDisplayName(id);
  el.setAttribute('aria-label', label !== id ? `${label}（${id}）` : id);
}
function updateContextIndicator(used, budget = CONTEXT_TOKEN_BUDGET) {
  const el = DOM['context-indicator'];
  if (!el) return;
  const n = Number(used) || 0;
  if (!S.currentAgentId || n <= 0) {
    el.classList.add('hidden');
    return;
  }
  el.classList.remove('hidden');
  const pct = Math.min(100, (n / budget) * 100);
  const fill = el.querySelector('.ctx-fill');
  const label = el.querySelector('.ctx-label');
  if (fill) fill.style.width = `${pct}%`;
  if (label) label.textContent = `${n.toLocaleString()} / ${Math.round(budget / 1000)}k tokens`;
  el.classList.toggle('ctx-warn', pct >= 75 && pct < 90);
  el.classList.toggle('ctx-over', pct >= 90);
}
function accumulateContextTokens(agentId, tokenData) {
  if (!agentId || !tokenData) return;
  const add = tokenData.total || (Number(tokenData.input) || 0) + (Number(tokenData.output) || 0);
  if (!add) return;
  S.contextTokens[agentId] = (S.contextTokens[agentId] || 0) + add;
  if (agentId === S.currentAgentId) updateContextIndicator(S.contextTokens[agentId]);
}
function resetContextTokens(agentId) {
  if (agentId) S.contextTokens[agentId] = 0;
  if (agentId === S.currentAgentId) updateContextIndicator(0);
}
function toolIconAbbr(name) {
  const n = String(name || 'tool');
  if (n.length <= 2) return n.toUpperCase();
  return n.replace(/[^A-Z]/g, '').slice(0, 2) || n.slice(0, 2).toUpperCase();
}
function formatRelativeTime(ts) {
  if (!ts) return '';
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return '刚刚';
  if (sec < 3600) return `${Math.floor(sec / 60)}分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}小时前`;
  return `${Math.floor(sec / 86400)}天前`;
}
function agentLastActivityTs(agentId) {
  const msgs = S.agentMessages[agentId] || [];
  if (!msgs.length) return 0;
  return Math.max(...msgs.map(m => m.ts || 0));
}
/** 列表项预览文案：取最后一条非 system 消息，压平为单行纯文本 */
function msgPreviewText(content) {
  return String(content || '')
    .replace(/```[\s\S]*?```/g, '[代码]')
    .replace(/[#>*`_|-]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}
function agentLastPreview(agentId) {
  const msgs = (S.agentMessages[agentId] || []).filter(m => m.role !== 'system');
  const last = msgs[msgs.length - 1];
  if (!last) return '';
  const text = msgPreviewText(last.content) || (last.role === 'agent' ? '[Agent 活动]' : '');
  if (!text) return '';
  return (last.role === 'user' ? '你: ' : '') + text;
}
/** 列表时间戳：今天显示 HH:MM，昨天显示「昨天」，更早显示 M/D */
function fmtListTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d)) return '';
  const now = new Date();
  if (dayKeyOf(ts) === dayKeyOf(now.getTime())) return fmtMsgTime(ts);
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (dayKeyOf(ts) === dayKeyOf(y.getTime())) return '昨天';
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// ============ Theme ============
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
      // 按钮在左侧 Rail 底部：菜单向右上方展开
      const rect = e.currentTarget.getBoundingClientRect();
      dd.style.right = 'auto';
      dd.style.top = 'auto';
      dd.style.left = (rect.right + 10) + 'px';
      dd.style.bottom = (window.innerHeight - rect.bottom) + 'px';
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

// ============ Toast ============
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

// ============ Confirm ============
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

// ============ Chat History ============
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
function mapServerChatMessages(rows) {
  return (rows || []).map(m => ({
    role: m.role === 'user' ? 'user' : (m.role === 'agent' ? 'agent' : 'system'),
    content: m.text || '',
    parts: m.parts || null,
    ts: tsFromIso(m.created_at) || 0,
    seq: m.seq,
  })).filter(m => m.ts);
}
function finalizeAgentMsgFromThinking(msg) {
  if (!msg || String(msg.content || '').trim()) return;
  const chunks = (msg.thinking || []).filter(t => t && t.type === 'text' && t.content).map(t => t.content);
  if (!chunks.length) return;
  msg.content = normalizeBubbleText(chunks.join(''));
}
function attachInflightAgent(serverMsgs, localMsgs) {
  if (!serverMsgs?.length) return localMsgs || [];
  const local = localMsgs || [];
  const out = serverMsgs.slice();
  const lastLocal = local[local.length - 1];
  const prevLocal = local[local.length - 2];
  if (lastLocal?.role === 'agent' && prevLocal?.role === 'user') {
    const lastSrv = out[out.length - 1];
    if (lastSrv?.role === 'user') {
      finalizeAgentMsgFromThinking(lastLocal);
      out.push({
        ...lastLocal,
        thinking: Array.isArray(lastLocal.thinking) ? [...lastLocal.thinking] : [],
      });
    }
  }
  return out;
}
/** 以 Store 为准同步 DM；进行中回合保留本地 agent 气泡。 */
async function syncAgentChatFromServer(agentId) {
  if (!agentId) return;
  const skey = streamKeyAgent(agentId);
  const busy = isStreamBusy(skey);
  try {
    const r = await fetch(`/api/chat/${encodeURIComponent(agentId)}/messages`);
    if (!r.ok) return;
    const d = await r.json();
    const mapped = mapServerChatMessages(d.messages);
    const local = S.agentMessages[agentId] || [];
    let next;
    if (busy) {
      next = attachInflightAgent(mapped, local);
    } else {
      next = mapped.length ? mapped : local;
      const last = next[next.length - 1];
      if (last?.role === 'agent') finalizeAgentMsgFromThinking(last);
    }
    if (!next.length) return;
    S.agentMessages[agentId] = next;
    saveChatHistory();
    if (S.currentAgentId === agentId) {
      if (busy) rebindAgentStreamDom(agentId);
      else rerenderAgentChat(agentId);
    } else if (!busy) {
      next.slice(-2).forEach(m => { m._new = true; });
      renderAgentList();
    }
  } catch (e) {
    console.warn('syncAgentChatFromServer:', e);
  }
}
function rerenderAgentChat(agentId) {
  if (S.currentAgentId !== agentId || !DOM.messages) return;
  DOM.messages.innerHTML = '';
  (S.agentMessages[agentId] || []).forEach(m => renderAgentMsg(m, DOM.messages, agentId));
  scrollBottom(DOM.messages, true);
}
function rebindAgentStreamDom(agentId) {
  const skey = streamKeyAgent(agentId);
  const st = S.streams[skey];
  if (!st?.busy || !st.ctx || st.ctx.agentId !== agentId || S.currentAgentId !== agentId) return;
  rerenderAgentChat(agentId);
  const msgs = S.agentMessages[agentId] || [];
  const aMsg = st.ctx.aMsg || msgs[msgs.length - 1];
  const agentNodes = DOM.messages.querySelectorAll('.message.agent');
  const el = agentNodes[agentNodes.length - 1];
  if (!el || !aMsg) return;
  const ce = el.querySelector('.msg-content');
  const tb = el.querySelector('.thinking-body');
  const ts = el.querySelector('.thinking-section');
  st.ctx.agentEl = el;
  st.ctx.contentEl = ce;
  st.ctx.tb = tb;
  st.ctx.ts = ts;
  st.ctx.aMsg = aMsg;
  if (ce && aMsg.content) renderBubbleMarkdown(ce, aMsg.content);
  if (tb && aMsg.thinking?.length) {
    tb.innerHTML = buildThinkingBodyHtml(aMsg.thinking);
    if (ts) { ts.style.display = ''; updateThinkingHeader(ts, aMsg, true); }
  }
  const td = el.querySelector('.typing-dots');
  if (td && !aMsg.content && !(aMsg.thinking?.length)) td.style.display = 'flex';
}
function resolveAgentStreamUi(agentId, aMsg) {
  const skey = streamKeyAgent(agentId);
  const st = S.streams[skey];
  if (!st?.ctx) return { el: null, ce: null, tb: null, ts: null };
  if (S.currentAgentId === agentId && (!st.ctx.agentEl || !st.ctx.agentEl.isConnected)) {
    rebindAgentStreamDom(agentId);
  }
  const ctx = st.ctx;
  return { el: ctx.agentEl || null, ce: ctx.contentEl || null, tb: ctx.tb || null, ts: ctx.ts || null };
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

// ============ Scroll & Stream ============
function isNearBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
}
function showNewMsgFloater() { DOM['new-msg-floater']?.classList.remove('hidden'); }
function hideNewMsgFloater() { DOM['new-msg-floater']?.classList.add('hidden'); }
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
function streamKeyAgent(agentId) { return agentId ? `agent:${agentId}` : null; }
function streamKeyGroup(groupId) { return groupId ? `group:${groupId}` : null; }
function ensureStream(key) {
  if (!key) return null;
  if (!S.streams[key]) S.streams[key] = { abortCtrl: null, reader: null, ctx: null, busy: false };
  return S.streams[key];
}
function isStreamBusy(key) { return !!(key && S.streams[key]?.busy); }
function currentViewStreamKey() {
  if (S.currentAgentId) return streamKeyAgent(S.currentAgentId);
  if (S.currentGroupId) return streamKeyGroup(S.currentGroupId);
  return null;
}
function refreshStatusBadge() {
  const key = currentViewStreamKey();
  setStatus(key && isStreamBusy(key) ? 'busy' : 'online');
}
function setStatus(s) {
  const badge = DOM['status-badge'];
  badge.className = `status ${s}`;
  badge.textContent = s === 'online' ? '就绪' : s === 'busy' ? '处理中' : '离线';
}
function setSendBtnMode(btn, streaming, hasText, enabled) {
  if (!btn) return;
  if (streaming) { btn.disabled = false; btn.textContent = '停止'; btn.classList.add('stop-mode'); return; }
  btn.classList.remove('stop-mode');
  btn.textContent = '发送';
  btn.disabled = !hasText || !enabled;
}
function updateSendBtn() {
  const busy = isStreamBusy(streamKeyAgent(S.currentAgentId));
  setSendBtnMode(DOM['btn-send'], busy, !!DOM['message-input'].value.trim(), !!S.currentAgentId);
}
function updateGroupSendBtn() {
  const busy = isStreamBusy(streamKeyGroup(S.currentGroupId));
  setSendBtnMode(DOM['btn-group-send'], busy, !!DOM['group-input'].value.trim(), !!S.currentGroupId);
}
function stopStreamKey(key, opts = {}) {
  const st = key ? S.streams[key] : null;
  if (!st) return;
  if (opts.userInitiated) st.userCancelled = true;
  if (st.abortCtrl) { st.abortCtrl.abort(); st.abortCtrl = null; }
  if (st.reader) { st.reader.cancel().catch(() => {}); st.reader = null; }
}
function stopStream() {
  stopStreamKey(currentViewStreamKey());
  S.abortCtrl = null;
  S.currentReader = null;
}
function cancelActiveStream() {
  const key = currentViewStreamKey();
  if (!key || !isStreamBusy(key)) return;
  stopStreamKey(key, { userInitiated: true });
  refreshStatusBadge();
  updateSendBtn();
  updateGroupSendBtn();
}
function rollbackAgentTurn(userText, agentEl, agentId) {
  const aid = agentId || S.currentAgentId;
  const msgs = S.agentMessages[aid];
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
  renderGroupMsg({ sender:'system', text:'已中断', id:`x_${Date.now()}` });
  DOM['group-input'].value = userText;
  DOM['group-input'].style.height = 'auto';
}

// ============ Tool Parsing ============
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
function describeToolAction(name, input) {
  const inp = parseToolInputObj(input);
  const n = name || 'tool';
  switch (n) {
    case 'Read': return { verb: '读取', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Write': return { verb: '写入', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Edit': return { verb: '编辑', target: inp.file_path || inp.path || inp.file || '…', mono: true };
    case 'Bash': case 'Run': return { verb: '运行命令', target: truncateText(inp.command || inp.cmd || inp.script || inp.raw || '', 80), mono: true };
    case 'Grep': return { verb: '搜索', target: `"${truncateText(inp.pattern || inp.query || '', 36)}" · ${shortPath(inp.path || inp.glob || '.')}`, mono: false };
    case 'Glob': return { verb: '匹配文件', target: inp.pattern || inp.glob || '…', mono: true };
    case 'WebSearch': return { verb: 'Web 搜索', target: truncateText(inp.query || inp.q || '', 60), mono: false };
    case 'WebFetch': return { verb: '抓取 URL', target: truncateText(inp.url || '', 72), mono: true };
    case 'Task': return { verb: '子任务', target: truncateText(inp.description || inp.prompt || '', 60), mono: false };
    case 'Think': return { verb: '推理', target: truncateText(inp.thought || inp.content || inp.text || formatToolInputJson(input), 120), mono: false };
    default: return { verb: n, target: truncateText(formatToolInputJson(input).replace(/\s+/g, ' '), 60), mono: true };
  }
}

// ============ Activity Timeline Builders ============
function buildActivityStep(stepNum) {
  return `<div class="activity-step"><span class="activity-step-label">步骤 ${stepNum}</span></div>`;
}
function buildActivityRow(toolUse, toolResult) {
  const act = describeToolAction(toolUse.name, toolUse.input);
  const abbr = toolIconAbbr(toolUse.name);
  const pending = !toolResult;
  const args = formatToolInputJson(toolUse.input);
  const targetHtml = act.mono ? `<code class="activity-target">${esc(act.target)}</code>` : `<span class="activity-target-text">${esc(act.target)}</span>`;
  let html = `<div class="activity-row${pending ? ' pending' : ' done'}"><div class="activity-main"><span class="activity-icon" title="${esc(toolUse.name || '')}">${esc(abbr)}</span><span class="activity-verb">${esc(act.verb)}</span>${targetHtml}<span class="activity-status">${pending ? '…' : '✓'}</span></div><details class="activity-detail"><summary>参数</summary><pre class="activity-pre">${esc(args)}</pre></details>`;
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
  let html = ''; let step = 0;
  const items = thinking || [];
  for (let i = 0; i < items.length; i++) {
    const t = items[i];
    if (t.type === 'step_start') { step += 1; html += buildActivityStep(step); }
    else if (t.type === 'tool_use') {
      const next = items[i + 1];
      const paired = next?.type === 'tool_result' ? next : null;
      html += buildActivityRow(t, paired);
      if (paired) i += 1;
    } else if (t.type === 'tool_result') { html += `<div class="activity-row done">${buildActivityResultInner(t)}</div>`; }
    else if (t.type === 'step_finish' && t.tokens) html += buildThinkingStepFinish(t);
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
      pending.classList.remove('pending'); pending.classList.add('done');
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

// ============ Bubble / Markdown Rendering ============
function normalizeBubbleText(text) {
  if (!text) return '';
  let s = String(text);
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
  if (!ev || !msg) return;
  const live = rootEl && rootEl.isConnected;
  if (ev.event === 'thinking') { handleThinking(ev.data, msg, contentEl, tb, ts, rootEl); }
  else if (ev.event === 'citations') {
    const cites = Array.isArray(ev.data) ? ev.data : [];
    if (cites.length) {
      msg.parts = cites;
      if (live) {
        const bubble = rootEl.querySelector('.bubble');
        if (bubble) {
          bubble.querySelector('.citations')?.remove();
          renderCitations(bubble, cites, bubble.querySelector('.msg-meta'));
        }
        scrollBottom(DOM.messages);
      }
      saveChatHistory();
    }
  } else if (ev.event === 'error') {
    if (live) showAgentError(rootEl, ev.data?.message || '未知错误');
    else msg.content = msg.content || `错误：${ev.data?.message || '未知错误'}`;
    saveChatHistory();
  } else if (ev.event === 'done') {
    msg.sessionId = ev.data?.session_id || '';
    saveChatHistory();
  }
}
function handleThinking(d, msg, contentEl, tb, ts, rootEl) {
  if (!d || !msg) return;
  const liveEl = rootEl && rootEl.isConnected;
  let ce = contentEl;
  let thinkingBody = tb;
  let thinkingSec = ts;
  if (liveEl && !thinkingSec) {
    thinkingSec = rootEl.querySelector('.thinking-section');
    thinkingBody = rootEl.querySelector('.thinking-body');
    ce = ce || rootEl.querySelector('.msg-content');
  }
  if (d.type === 'text') {
    msg.content = normalizeBubbleText((msg.content || '') + (d.content || ''));
    if (ce?.isConnected) renderBubbleMarkdown(ce, msg.content);
    if (ce?.isConnected) scrollBottom(DOM.messages);
    saveChatHistory();
    return;
  }
  if (thinkingSec?.isConnected) thinkingSec.style.display = '';
  if (d.type === 'step_start' || d.type === 'tool_use' || d.type === 'tool_result' || d.type === 'step_finish') {
    appendThinkingEvent(msg, thinkingBody?.isConnected ? thinkingBody : null, d);
    if (d.type === 'step_finish' && d.tokens && S.currentAgentId) accumulateContextTokens(S.currentAgentId, d.tokens);
    if (thinkingSec?.isConnected) updateThinkingHeader(thinkingSec, msg, true);
    saveChatHistory();
  }
  if (thinkingBody?.isConnected || ce?.isConnected) scrollBottom(DOM.messages);
}
function showAgentError(rootEl, message) {
  const ce = rootEl?.querySelector('.msg-content');
  if (ce) { ce.classList.remove('markdown-body'); ce.textContent = message; ce.classList.add('error'); }
}
function msgMetaHtml(mts) {
  return '<div class="msg-meta"><button class="msg-copy" type="button" title="复制" aria-label="复制">' + ic('copy') + '</button><span class="msg-time">' + fmtMsgTime(mts) + '</span></div>';
}
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
    card.innerHTML = '<div class="cite-head"><span class="cite-label">引用</span> ' + esc(title) + '</div>' + (snippet ? '<div class="cite-snippet">' + esc(snippet) + '</div>' : '');
    if (c.url) { card.classList.add('clickable'); card.addEventListener('click', () => window.open(c.url, '_blank', 'noopener')); }
    wrap.appendChild(card);
  });
  if (beforeEl) bubbleEl.insertBefore(wrap, beforeEl);
  else bubbleEl.appendChild(wrap);
}

// ============ Message Renderer ============
function renderAgentMsg(msg, container, agentId) {
  const c = container || DOM.messages;
  const aid = agentId || S.currentAgentId;
  const mts = msg.ts || 0;
  const gkey = msg.role === 'agent' ? 'agent:' + aid : msg.role;
  if (msg.role !== 'system') _dateSep(c, mts);
  const grouped = _grouped(c, gkey, mts);
  const div = document.createElement('div');
  div.dataset.gkey = gkey; div.dataset.ts = String(mts); div.dataset.day = dayKeyOf(mts);

  if (msg.role === 'user') {
    div.className = 'message user' + (grouped ? ' grouped' : '');
    div.innerHTML = '<div class="bubble"><div class="msg-content">' + esc(msg.content) + '</div>' + msgMetaHtml(mts) + '</div>';
  } else if (msg.role === 'agent') {
    div.className = 'message agent' + (grouped ? ' grouped' : '');
    const a = S.agents.find(x => x.id === aid);
    const nm = a ? (a.name || aid) : 'Agent';
    const hasThinking = msg.thinking && msg.thinking.length;
    div.innerHTML =
      '<div class="msg-avatar avatar-badge" aria-label="' + esc(aid) + '">' + esc(getAvatar(aid)) + '</div>' +
      '<div class="bubble">' +
      (grouped ? '' : '<div class="bubble-name">' + esc(nm) + '</div>') +
      '<div class="thinking-section collapsed"><div class="thinking-header"><span class="thinking-toggle">▼</span><span class="thinking-title">' + esc(thinkingSectionTitle(msg.thinking, !!(msg.ts && S.isStreaming))) + '</span></div><div class="thinking-body">' + buildThinkingBodyHtml(msg.thinking) + '</div></div>' +
      '<div class="msg-content"></div>' +
      '<div class="typing-dots" style="display:none"><span></span><span></span><span></span></div>' +
      msgMetaHtml(mts) +
      '</div>';
    const ce = div.querySelector('.msg-content');
    if (ce) renderBubbleMarkdown(ce, msg.content || '');
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