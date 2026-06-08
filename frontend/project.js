// ============ Project Detail ============
const PROJECT_TERMINAL = new Set(['completed', 'failed', 'partially_failed', 'aborted', 'cancelled', 'paused', 'timed_out']);
const PROJ_STATUS_LABEL = { in_progress:'运行中', running:'运行中', pending:'排队', completed:'已完成', needs_review:'待确认', failed:'失败', cancelled:'已取消', blocked:'阻塞' };
const TASK_STATUS_LABEL = { pending:'等待', in_progress:'运行中', running:'运行中', completed:'已完成', needs_review:'待评审', failed:'失败', cancelled:'已取消', blocked:'阻塞', awaiting_gate:'等待门禁' };
const DELIV_KIND_LABELS = { script: '脚本', doc: '文档', output: '产出', test: '测试', data: '数据', file: '文件' };
const EVENT_LABELS = {
  gate_passed:'门禁通过', gate_failed:'门禁未过', review_done:'评审完成',
  review_unreachable:'评审不可达', plan_rejected:'计划被拒', blocked:'任务阻塞',
  budget_alert:'预算告警', budget_over:'预算超限', cycle_done:'周期完成',
  watchdog_soft_idle:'疑似卡住', watchdog_hard_kill:'看门狗中止',
  transport_error:'传输错误', reconcile_timed_out:'重启对账超时',
  reconcile_adopted:'对账回收',
  tool_use:'skill 调用', tool_result:'工具返回',
  prompt_sent:'发送 prompt', request_snapshot:'请求快照',
  response_snapshot:'响应快照', message:'消息',
};
const INTERACTION_STATUS_LABEL = {
  running:'运行中', completed:'已完成', failed:'失败', cancelled:'已取消',
  timed_out:'超时', blocked:'阻塞', pending:'等待',
};
const INTERACTION_LABELS = { team_config:'组队配置', task_plan:'任务拆分', execute:'执行', review:'评审', triage:'分诊' };
const EXEC_TIMELINE_KINDS = new Set([
  'tool_use', 'tool_result', 'text', 'gate_passed', 'gate_failed', 'review_done', 'review_unreachable',
  'error', 'transport_error', 'watchdog_soft_idle', 'watchdog_hard_kill',
  'step_finish', 'prompt_sent', 'request_snapshot', 'response_snapshot', 'plan_rejected',
]);
const EXEC_CHILD_LABELS = {
  tool_use: 'skill 调用', tool_result: '工具返回', text: '模型输出', step_finish: 'Token 计量',
  prompt_sent: '发送 prompt', request_snapshot: '请求快照', response_snapshot: '响应快照',
  error: '错误', transport_error: '传输错误',
};

let _sysCfg = null;
let _boundGroupId = '';
let _boundProjectId = '';
const _renderSig = {};
const _execStreams = {};
let _deliverable = { content: '', taskId: '', projectId: '', files: [], activePath: '' };
let _deliverableTasks = [];
let _selectedTaskId = '';

function highlightProjectTask(taskId) {
  _selectedTaskId = taskId || '';
  document.querySelectorAll('.task-row.clickable').forEach(row => {
    row.classList.toggle('task-selected', !!taskId && row.dataset.task === taskId);
  });
  document.querySelectorAll('.dag-node').forEach(node => {
    node.classList.toggle('dag-selected', !!taskId && node.dataset.id === taskId);
  });
}

// ============ Config ============
async function getSysConfig() {
  if (_sysCfg) return _sysCfg;
  try { _sysCfg = (await (await fetch('/api/config')).json()).config?.system || {}; } catch { _sysCfg = {}; }
  return _sysCfg;
}
async function getPriceRate() { return Number((await getSysConfig()).price_per_mtok) || 0; }
function fmtYuan(tokens, rate) { return rate ? ` · ¥${(tokens / 1e6 * rate).toFixed(2)}` : ''; }
function budgetBar(tokens, budget, ratio, state) {
  if (!budget) return `<div class="budget-none">${tokens} tok · 无预算上限</div>`;
  const pct = Math.min(100, Math.round((ratio || 0) * 100));
  return `<div class="budget-wrap budget-${esc(state || 'ok')}"><div class="budget-track"><div class="budget-fill" style="width:${pct}%"></div></div><div class="budget-label">${tokens} / ${budget} tok · ${pct}%${state === 'over' ? ' · 超限' : state === 'alert' ? ' · 接近上限' : ''}</div></div>`;
}

// ============ Project CRUD ============
async function loadProjects() {
  try {
    const r = await fetch('/api/obs/projects');
    const d = await r.json();
    S.projects = d.projects || [];
    if (DOM['project-count']) DOM['project-count'].textContent = S.projects.length;
  } catch (e) { console.error('projects:', e); S.projects = []; }
}
function renderProjectList() {
  if (!DOM['project-list']) return;
  if (!S.projects.length) { DOM['project-list'].innerHTML = '<div class="empty">暂无项目<br><small>点击 + 发起一个项目</small></div>'; return; }
  DOM['project-list'].innerHTML = S.projects.map(p =>
    `<div class="sidebar-item ${S.currentProjectId === p.id ? 'active' : ''}" data-id="${p.id}">
      <span class="s-icon avatar-badge">${esc(getAvatar(p.id))}</span>
      <span class="s-name">${esc(p.title || p.id)}</span>
      <span class="s-sub">${Math.round((p.progress || 0) * 100)}% · ${p.task_count || 0}任务 · ${esc(p.status || '')}</span>
      <button class="s-del" data-del="${p.id}" title="删除项目" aria-label="删除项目">${ic('trash')}</button>
    </div>`
  ).join('');
  DOM['project-list'].querySelectorAll('.sidebar-item').forEach(el => { el.addEventListener('click', () => selectProject(el.dataset.id)); });
  DOM['project-list'].querySelectorAll('.s-del').forEach(btn => { btn.addEventListener('click', (e) => { e.stopPropagation(); deleteProject(btn.dataset.del); }); });
}
async function deleteProject(id) {
  if (!await showConfirm(`确认彻底删除项目「${id}」？将清除其数据库记录、交付物目录与 agent 临时文件，不可恢复。`, {title:'删除项目', okText:'彻底删除', danger:true})) return;
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '删除失败'));
    if (S.currentProjectId === id) { stopProjectPoll(); S.currentProjectId = null; DOM['project-detail-view']?.classList.add('hidden'); DOM['project-welcome']?.classList.remove('hidden'); }
    await loadProjects(); renderProjectList();
    showToast(`已删除项目「${id}」`, 'success');
  } catch (e) { showToast('删除项目失败：' + (e.message || e), 'error'); }
}

// ============ Select Project ============
function setHtmlIfChanged(el, key, html) {
  if (!el) return false;
  if (_renderSig[key] === html) return false;
  _renderSig[key] = html;
  el.innerHTML = html;
  return true;
}
function setTextIfChanged(el, val) { if (el && el.textContent !== val) el.textContent = val; }

async function selectProject(id, opts = {}) {
  S.currentProjectId = id; S.currentAgentId = null; S.currentGroupId = null;
  _selectedTaskId = '';
  const dagEl = document.getElementById('dag-container');
  if (dagEl) {
    delete dagEl.dataset.dagScale;
    delete dagEl.dataset.dagPanX;
    delete dagEl.dataset.dagPanY;
    delete dagEl._dagPanSetup;
  }
  stopProjectPoll();
  for (const k in _renderSig) delete _renderSig[k];
  renderProjectList();
  DOM['project-welcome'].classList.add('hidden');
  DOM['project-detail-view'].classList.remove('hidden');
  const initialPtab = opts.restore ? (opts.ptab || 'overview') : 'overview';
  switchProjectTab(initialPtab, { skipDeliverableLoad: initialPtab !== 'deliverable', skipSave: true });
  if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '选择任务或从「概览」点任务查看交付物。';
  if (DOM['deliverable-body']) DOM['deliverable-body'].innerHTML = '';
  if (DOM['deliverable-files']) { DOM['deliverable-files'].innerHTML = ''; DOM['deliverable-files'].classList.add('hidden'); }
  if (DOM['deliverable-task-nav']) { DOM['deliverable-task-nav'].innerHTML = ''; DOM['deliverable-task-nav'].classList.add('hidden'); }
  _deliverable = { content: '', taskId: '' };
  setDeliverableActions(false);
  await updateBoundGroupButton(id);
  const done = await refreshProjectDetail(id);
  if (!done) connectProjectStream(id);
  if (!opts.restore) saveUiState();
}

// ============ Refresh ============
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
    const resumable = !rs.running && (status === 'in_progress' || status === 'paused');
    DOM['btn-resume-project']?.classList.toggle('hidden', !resumable);
    DOM['btn-cancel-project']?.classList.toggle('hidden', !active);
    setTextIfChanged(DOM['project-title'], ov.title || id);
    const launchErr = rs && rs.error ? ` · 异常: ${rs.error}` : '';
    const totalTok = (cost && cost.project) || ov.tokens || 0;
    const rateEarly = await getPriceRate();
    const tokHint = totalTok ? ` · ${totalTok.toLocaleString()} tok${fmtYuan(totalTok, rateEarly)}` : '';
    setTextIfChanged(DOM['project-meta'], `${id} · ${status}${rs.running ? ' · 运行中' : ''}${tokHint}${launchErr}`);
    const pct = Math.round((ov.progress || 0) * 100);
    setTextIfChanged(DOM['project-progress-text'], `${pct}%`);
    if (DOM['project-progress-fill'].style.width !== `${pct}%`) DOM['project-progress-fill'].style.width = `${pct}%`;

    const tasks = ov.tasks || [];
    const byTask = (cost && cost.by_task) || {};
    const tasksHtml = tasks.length
      ? `<div class="task-list-header"><span>任务 ID</span><span>名称</span><span>Agent</span><span>Token</span><span>状态</span></div>` + tasks.map(t => {
          const st = t.status || 'pending';
          const deps = (t.dependencies || []).join(', ');
          const tok = byTask[t.id] ? `${Number(byTask[t.id]).toLocaleString()} tok` : '';
          const sub = t.summary ? `<small class="hint">${esc(t.summary)}</small>` : (deps ? `<small class="hint">依赖: ${esc(deps)}</small>` : '');
          const stLabel = TASK_STATUS_LABEL[st] || st;
          return `<div class="task-row status-${st} clickable" data-task="${esc(t.id)}">
            <span class="task-id" data-label="任务 ID">${esc(t.id)}</span>
            <span class="task-name" data-label="名称">${esc(t.name || '')}${sub ? '<br>' + sub : ''}</span>
            <span class="task-agent" data-label="Agent">${esc(t.agent || '-')}</span>
            <span class="task-tokens" data-label="Token">${tok || '—'}</span>
            <span class="task-status" data-label="状态"><span class="status-chip s-${esc(st)}">${esc(stLabel)}</span></span>
          </div>`;
        }).join('')
      : (rs.running ? '<div class="empty">内核启动中（team_config / task_plan 决策中）…</div>' : '<div class="empty">暂无任务</div>');
    if (setHtmlIfChanged(DOM['project-tasks'], 'tasks', tasksHtml)) {
      DOM['project-tasks'].querySelectorAll('.task-row.clickable').forEach(el => {
        el.addEventListener('click', () => { highlightProjectTask(el.dataset.task); openDeliverable(id, el.dataset.task); });
      });
      if (_selectedTaskId) highlightProjectTask(_selectedTaskId);
    }
    _deliverableTasks = tasks.map(t => ({ id: t.id, name: t.name || t.id }));
    if (document.querySelector('.ptab-panel[data-ptab="deliverable"]')?.classList.contains('active')) { void ensureDeliverablePanel(); }

    const fl = (fleet && fleet.fleet) || {};
    const flEntries = Object.entries(fl);
    const fleetHtml = flEntries.length ? flEntries.map(([a, s]) => `<span class="fleet-chip live-${esc(s)}">${esc(a)} · ${esc(s)}</span>`).join('') : '<span class="hint">暂无</span>';
    setHtmlIfChanged(DOM['project-fleet'], 'fleet', fleetHtml);

    const total = (cost && cost.project) || 0;
    const byAgent = (cost && cost.by_agent) || {};
    const rate = await getPriceRate();
    const agentRows = Object.entries(byAgent).map(([a, n]) => `<div class="cost-row"><span>${esc(a)}</span><span>${n} tok${fmtYuan(n, rate)}</span></div>`).join('');
    const maxTok = Math.max(...Object.values(byAgent), 1);
    const barChart = Object.entries(byAgent).length ? `<div class="cost-bar-chart">${
      Object.entries(byAgent).map(([a, n]) => {
        const pct = (n / maxTok * 100).toFixed(0);
        const colors = ['#4f46e5','#0891b2','#059669','#d97706','#dc2626','#7c3aed','#db2777','#2563eb'];
        const ci = Object.keys(byAgent).indexOf(a) % colors.length;
        return `<div class="cost-bar-item"><div class="cost-bar-label">${esc(a)}</div><div class="cost-bar-track"><div class="cost-bar-fill" style="width:${pct}%;background:${colors[ci]}"></div></div><div class="cost-bar-val">${n.toLocaleString()}</div></div>`;
      }).join('')
    }</div>` : '';
    const costHtml = budgetBar(total, ov.budget, ov.budget_ratio, ov.budget_state) + barChart +
      `<div class="cost-row cost-total"><span>合计</span><span>${total} tok${fmtYuan(total, rate)}</span></div>${agentRows || ''}` +
      (total === 0 ? '<div class="hint cost-zero-hint">暂无 Token 计量：交互进行中会逐步累加；若 CLI 无 step_finish 输出则保持为 0。</div>' : '') +
      (!rate && total > 0 ? '<div class="hint cost-zero-hint">未配置单价，仅显示 Token。请到「设置」填写每百万 Token 单价以估算人民币。</div>' : '');
    setHtmlIfChanged(DOM['project-cost'], 'cost', costHtml);
    setHtmlIfChanged(DOM['project-cost-overview'], 'costOverview', costHtml);
    renderEventFeed((ev && ev.events) || []);

    // 给 DAG 注入 token 计量（cost.by_task 来自 /cost API）
    const dagTasks = tasks.map(t => ({ ...t, token: byTask[t.id] || null }));
    if (tasks.length && typeof renderDAG === 'function') {
      try {
        window._onDagNodeClick = (taskId) => { highlightProjectTask(taskId); openDeliverable(id, taskId); };
        const dagContainer = document.getElementById('dag-container');
        if (dagContainer) renderDAG(dagContainer, dagTasks, _selectedTaskId);
      } catch (dagErr) {
        console.warn('DAG render failed:', dagErr);
      }
    }
    if (typeof renderTimeline === 'function') {
      try {
        const tlContainer = document.getElementById('timeline-container');
        const rawEvents = (ev && ev.events) || [];
        // 适配：interaction events（kind/ts）→ timeline（type/timestamp）
        const mappedEvents = rawEvents.map(e => ({
          type: (
            e.kind === 'gate_passed' ? 'project.gate.completed' :
            e.kind === 'gate_failed' ? 'project.gate.rejected' :
            e.kind === 'cycle_done' ? 'project.cycle.completed' :
            e.kind === 'message' ? 'chat.message.posted' :
            e.kind === 'budget_alert' ? 'budget.threshold.reached' :
            e.kind === 'budget_over' ? 'budget.threshold.exceeded' :
            e.kind === 'watchdog_hard_kill' ? 'agent.error' :
            e.kind === 'plan_rejected' ? 'project.plan.rejected' :
            e.kind === 'blocked' ? 'project.task.blocked' :
            e.kind === 'review_done' ? 'project.gate.completed' :
            'project.event'
          ),
          timestamp: e.ts || '',
          payload: e.payload || {},
          metadata: { task_id: e.task_id, agent_id: e.agent_id, interaction_id: e.interaction_id },
        }));
        if (tlContainer && mappedEvents.length) renderTimeline(tlContainer, mappedEvents);
      } catch (tlErr) {
        console.warn('Timeline render failed:', tlErr);
      }
    }
    return PROJECT_TERMINAL.has(status) && !rs.running;
  } catch (e) { DOM['project-meta'].textContent = `${id} · 加载失败：${String(e.message || e)}`; return false; }
}

// ============ Tab Switching ============
function switchProjectTab(ptab, opts = {}) {
  document.querySelectorAll('.project-subnav .ptab').forEach(b => b.classList.toggle('active', b.dataset.ptab === ptab));
  document.querySelectorAll('.ptab-panel').forEach(p => p.classList.toggle('active', p.dataset.ptab === ptab));
  if (ptab === 'deliverable' && !opts.skipDeliverableLoad) { void ensureDeliverablePanel(); }
  if (!opts.skipSave && S.currentProjectId) saveUiState();
}

async function updateBoundGroupButton(projectId) {
  const btn = DOM['btn-open-group'];
  if (!btn) return;
  if (!S.groups || !S.groups.length) { try { await loadGroups(); } catch (e) {} }
  const grp = (S.groups || []).find(g => g.project_id === projectId && g.status !== 'dissolved');
  _boundGroupId = grp ? grp.id : '';
  btn.classList.toggle('hidden', !grp);
}

// ============ Polling / SSE ============
function stopProjectPoll() {
  if (S._projectPoll) { clearInterval(S._projectPoll); S._projectPoll = null; }
  if (S._projectStream) { try { S._projectStream.close(); } catch (e) {} S._projectStream = null; }
  stopExecStreams();
}
function stopExecStreams() { for (const iid of Object.keys(_execStreams)) stopExecStream(iid); }
function stopExecStream(iid) {
  const es = _execStreams[iid];
  if (!es) return;
  try { es.close(); } catch (e) {} delete _execStreams[iid];
}
function startExecStream(iid, bodyEl) {
  if (!iid || !bodyEl || typeof EventSource === 'undefined') return;
  stopExecStream(iid);
  let es;
  try { es = new EventSource(`/api/obs/interactions/${encodeURIComponent(iid)}/events`); } catch (e) { return; }
  _execStreams[iid] = es;
  es.onmessage = (ev) => {
    if (S.currentProjectId == null) { stopExecStream(iid); return; }
    if (ev.data === '[DONE]') { stopExecStream(iid); void loadExecNodeBody(iid, bodyEl, { force: true }); return; }
    void loadExecNodeBody(iid, bodyEl, { force: true });
  };
  es.onerror = () => stopExecStream(iid);
}
function startProjectPoll(id) {
  S._projectPoll = setInterval(async () => {
    if (S.currentProjectId !== id) { stopProjectPoll(); return; }
    const done = await refreshProjectDetail(id);
    if (done) { stopProjectPoll(); loadProjects().then(renderProjectList); }
  }, 2500);
}
function connectProjectStream(id) {
  if (typeof EventSource === 'undefined') { startProjectPoll(id); return; }
  let es;
  try { es = new EventSource(`/api/obs/projects/${encodeURIComponent(id)}/stream`); } catch (e) { startProjectPoll(id); return; }
  S._projectStream = es;
  es.onmessage = async (ev) => {
    if (S.currentProjectId !== id) { stopProjectPoll(); return; }
    if (ev.data === '[DONE]') { await refreshProjectDetail(id); stopProjectPoll(); loadProjects().then(renderProjectList); return; }
    const done = await refreshProjectDetail(id);
    if (done) { stopProjectPoll(); loadProjects().then(renderProjectList); }
  };
  es.onerror = () => {
    try { es.close(); } catch (e) {}
    if (S._projectStream === es) S._projectStream = null;
    if (S.currentProjectId === id && !S._projectPoll) startProjectPoll(id);
  };
}

// ============ Event Feed ============
function eventDetail(e) {
  const p = e.payload || {};
  if (e.kind === 'gate_failed' && Array.isArray(p.failures)) return p.failures.join('；');
  if (e.kind === 'review_done') return (p.passed ? '通过' : '打回') + (p.feedback ? ' · ' + p.feedback : '');
  if (e.kind === 'message') return (p.sender ? p.sender + '：' : '') + (p.text || '');
  if (e.kind === 'tool_use') return toolUseSummary(p);
  if (e.kind === 'blocked' || e.kind === 'plan_rejected') return p.reason || (p.invalid_agents || []).join(', ');
  if (e.kind === 'budget_alert' || e.kind === 'budget_over') return JSON.stringify(p);
  if (e.kind === 'text') return String(p.content || '').slice(0, 160);
  if (e.kind === 'step_finish') { const t = p.tokens; if (t && typeof t === 'object') return `${t.total || t.input + t.output || 0} tok`; return t ? `${t} tok` : ''; }
  if (e.kind === 'prompt_sent') return `${p.prompt_len || 0} 字 · ${p.model || p.agent_id || ''}`;
  if (e.kind === 'request_snapshot') return p.request_path || 'InteractionRequest';
  if (e.kind === 'response_snapshot') return p.response_path || 'response';
  if (e.kind === 'tool_result') return String(p.content || '').slice(0, 160);
  return p && Object.keys(p).length ? JSON.stringify(p).slice(0, 160) : '';
}
function toolUseSummary(p) {
  const name = p.name || p.tool || 'tool';
  const act = describeToolAction(name, p.input);
  return `${name} · ${act.verb} ${act.target}`.trim().slice(0, 120);
}

function _execOpenState(box) {
  const nodes = new Set(); const children = new Set();
  box.querySelectorAll('.exec-node.open').forEach(n => nodes.add(n.dataset.iid));
  box.querySelectorAll('.exec-child.open').forEach(c => children.add(c.dataset.childId));
  return { nodes, children };
}
function _interactionIds(events) {
  const s = new Set();
  for (const e of events) { if (e.category === 'interaction' && e.interaction_id) s.add(e.interaction_id); }
  return s;
}
function cssEsc(s) { return (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); }
function renderInteractionNode(e) {
  const label = INTERACTION_LABELS[e.kind] || e.kind || '交互';
  const att = e.attempt > 1 ? ` ×${e.attempt}` : '';
  const who = [e.task_id, e.agent_id].filter(Boolean).map(esc).join(' · ');
  const tok = e.tokens ? `${Number(e.tokens).toLocaleString()} tok` : '';
  const stLabel = INTERACTION_STATUS_LABEL[e.status] || e.status || '';
  const ts = (e.ts || '').replace('T', ' ').slice(5, 16);
  const iid = e.interaction_id || '';
  return `<div class="exec-node status-${esc(e.status || '')}" data-iid="${esc(iid)}" data-status="${esc(e.status || '')}">
    <div class="exec-node-head" role="button" tabindex="0" aria-expanded="false">
      <span class="exec-chevron">▸</span>
      <span class="exec-node-title">${esc(label)}${att}</span>
      <span class="exec-node-meta">${who ? esc(who) : ''}</span>
      <span class="exec-node-status">${esc(stLabel)}${tok ? ' · ' + esc(tok) : ''}</span>
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
  const sig = JSON.stringify(events.map(e => [e.category, e.kind, e.interaction_id, e.status, e.attempt, e.ts]));
  const prev = _execOpenState(box);
  if (_renderSig.execTree === sig) { refreshOpenExecTimelines(); return; }
  _renderSig.execTree = sig;
  const iids = _interactionIds(events);
  const runningIids = new Set(events.filter(e => e.category === 'interaction' && e.status === 'running').map(e => e.interaction_id).filter(Boolean));
  let html = '';
  if (!events.length) { html = '<span class="hint">暂无执行事件</span>'; }
  else {
    for (const e of events) {
      if (e.category === 'interaction') html += renderInteractionNode(e);
      else if (e.category === 'event') { const iid = e.interaction_id || ''; if (!iid || !iids.has(iid)) html += renderStandaloneEvent(e); }
    }
  }
  box.innerHTML = html;
  bindExecTree(box);
  for (const iid of prev.nodes) {
    const node = box.querySelector(`.exec-node[data-iid="${cssEsc(iid)}"]`);
    if (!node) continue;
    setExecNodeOpen(node, true);
    const body = node.querySelector('.exec-node-body');
    if (body) {
      void loadExecNodeBody(iid, body, { force: true }).then(() => {
        for (const cid of prev.children) { const ch = body.querySelector(`.exec-child[data-child-id="${cssEsc(cid)}"]`); if (ch) setExecChildOpen(ch, true); }
        if (runningIids.has(iid)) startExecStream(iid, body);
      });
    }
  }
  for (const cid of prev.children) { const el = box.querySelector(`[data-child-id="${cssEsc(cid)}"]`); if (el && el.classList.contains('exec-standalone')) setExecChildOpen(el, true); }
}
function refreshOpenExecTimelines() {
  const box = DOM['project-events'];
  if (!box) return;
  for (const node of box.querySelectorAll('.exec-node.open')) {
    const iid = node.dataset.iid; const body = node.querySelector('.exec-node-body');
    if (!iid || !body) continue;
    void loadExecNodeBody(iid, body, { force: true }).then(() => { if (node.dataset.status === 'running') startExecStream(iid, body); });
  }
}
function bindExecTree(box) {
  if (box.dataset.execBound) return;
  box.dataset.execBound = '1';
  box.addEventListener('click', ev => {
    const nodeHead = ev.target.closest('.exec-node-head');
    if (nodeHead) { ev.preventDefault(); toggleExecNode(nodeHead.closest('.exec-node')); return; }
    const childHead = ev.target.closest('.exec-child-head');
    if (childHead) { ev.preventDefault(); toggleExecChild(childHead.closest('.exec-child, .exec-standalone')); }
  });
}
function setExecNodeOpen(node, open) {
  if (!node) return;
  const body = node.querySelector('.exec-node-body'); const head = node.querySelector('.exec-node-head'); const chev = node.querySelector('.exec-chevron');
  node.classList.toggle('open', open); body?.classList.toggle('hidden', !open);
  if (head) head.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (chev) chev.textContent = open ? '▾' : '▸';
}
async function toggleExecNode(node) {
  if (!node) return;
  const iid = node.dataset.iid; const body = node.querySelector('.exec-node-body');
  const open = !node.classList.contains('open');
  if (!open) { stopExecStream(iid); setExecNodeOpen(node, false); return; }
  setExecNodeOpen(node, open);
  await loadExecNodeBody(iid, body);
  if (node.dataset.status === 'running') startExecStream(iid, body);
}
function setExecChildOpen(el, open) {
  if (!el) return;
  const body = el.querySelector('.exec-child-body'); const chev = el.querySelector('.exec-chevron');
  el.classList.toggle('open', open); body?.classList.toggle('hidden', !open);
  if (chev) chev.textContent = open ? '▾' : '▸';
}
function toggleExecChild(el) { if (!el) return; setExecChildOpen(el, !el.classList.contains('open')); }
function bindExecChildToggles(container) {}
async function loadExecNodeBody(iid, bodyEl, { force = false } = {}) {
  if (!iid || !bodyEl || (!force && bodyEl.dataset.loaded)) return;
  const openChildren = new Set([...bodyEl.querySelectorAll('.exec-child.open')].map(c => c.dataset.childId).filter(Boolean));
  const silent = force && bodyEl.dataset.loaded;
  if (!silent) bodyEl.innerHTML = '<div class="exec-loading hint">加载明细…</div>';
  try {
    const r = await fetch(`/api/obs/interactions/${encodeURIComponent(iid)}/timeline`);
    const d = await r.json();
    const tl = (d.timeline || []).filter(e => EXEC_TIMELINE_KINDS.has(e.kind));
    if (!tl.length) { bodyEl.innerHTML = '<div class="exec-empty hint">该步骤暂无 skill 调用或其它明细</div>'; }
    else { bodyEl.innerHTML = tl.map((ev, idx) => renderExecChild(ev, iid, idx)).join(''); }
    bodyEl.dataset.loaded = '1';
    for (const cid of openChildren) { const ch = bodyEl.querySelector(`.exec-child[data-child-id="${cssEsc(cid)}"]`); if (ch) setExecChildOpen(ch, true); }
  } catch (e) { bodyEl.innerHTML = `<div class="exec-empty">加载失败：${esc(e.message || String(e))}</div>`; }
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
        <span class="exec-child-label"><span class="activity-icon" title="${esc(name)}">${esc(toolIconAbbr(name))}</span> ${esc(name)}</span>
        <span class="exec-child-summary">${esc(summary)}</span>
      </div>
      <div class="exec-child-body hidden">${renderToolDetailBody(p)}</div>
    </div>`;
  }
  const label = EVENT_LABELS[ev.kind] || EXEC_CHILD_LABELS[ev.kind] || ev.kind;
  const cls = ev.kind === 'text' ? 'exec-child-text' : (['error', 'transport_error', 'watchdog_hard_kill'].includes(ev.kind) ? 'exec-child-error' : 'exec-child-mile');
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
  const targetHtml = act.mono ? `<code class="activity-target">${esc(act.target)}</code>` : `<span class="activity-target-text">${esc(act.target)}</span>`;
  const summary = `<div class="exec-tool-summary"><span class="activity-icon" title="${esc(name)}">${esc(toolIconAbbr(name))}</span><span class="activity-verb">${esc(act.verb)}</span>${targetHtml}</div>`;
  const args = `<div class="trace-section"><span class="trace-tag">参数</span>${renderPayloadPre(p.input)}</div>`;
  const out = p.output ? `<div class="trace-out"><span class="trace-tag">CLI 返回</span>${renderPayloadPre(p.output)}</div>` : '<div class="trace-out trace-noout">（无返回 / 未完成）</div>';
  return summary + args + out;
}
function renderTimelineDetailBody(ev) {
  const p = ev.payload || {};
  if (ev.kind === 'text') return `<div class="trace-section"><span class="trace-tag">输出</span><div class="trace-msg">${esc(String(p.content || '').slice(0, 8000))}</div></div>`;
  if (ev.kind === 'gate_failed' && Array.isArray(p.failures)) return `<ul class="exec-fail-list">${p.failures.map(f => `<li>${esc(f)}</li>`).join('')}</ul>`;
  if (ev.kind === 'step_finish') return `<div class="trace-section"><span class="trace-tag">Token 计量</span>${renderPayloadPre(p)}</div>`;
  if (ev.kind === 'prompt_sent') return `<div class="trace-section"><span class="trace-tag">Prompt</span><div class="trace-msg">${esc(String(p.prompt || '').slice(0, 8000))}</div></div>`;
  if (ev.kind === 'request_snapshot' || ev.kind === 'response_snapshot') { const body = p.request || p.response || p; return `<div class="trace-section"><span class="trace-tag">快照</span>${renderPayloadPre(body)}</div>`; }
  if (ev.kind === 'tool_result') return `<div class="trace-section"><span class="trace-tag">返回</span><div class="trace-msg">${esc(String(p.content || '').slice(0, 8000))}</div></div>`;
  if (ev.kind === 'tool_use') return renderToolDetailBody(p);
  if (typeof p.text === 'string' && p.text) return `<div class="trace-msg">${esc(p.text)}</div>`;
  return `<div class="trace-section"><span class="trace-tag">详情</span>${renderPayloadPre(p)}</div>`;
}
function renderEventDetailBody(e) { return renderTimelineDetailBody({ kind: e.kind, payload: e.payload || {} }); }

// ============ Deliverable ============
function _deliverableTasksFromDom() {
  const rows = DOM['project-tasks']?.querySelectorAll('.task-row.clickable') || [];
  return [...rows].map(el => ({ id: el.dataset.task, name: el.querySelector('.task-name')?.textContent?.split('\n')[0]?.trim() || el.dataset.task })).filter(t => t.id);
}
async function _fetchProjectTasks(projectId) {
  try { const ov = await fetch(`/api/obs/projects/${encodeURIComponent(projectId)}/overview`).then(r => r.json()); return (ov.tasks || []).map(t => ({ id: t.id, name: t.name || t.id })); } catch (_) { return []; }
}
function renderDeliverableTaskNav(projectId, activeTaskId, tasks) {
  const nav = DOM['deliverable-task-nav'];
  if (!nav) return;
  if (!tasks || !tasks.length) { nav.innerHTML = ''; nav.classList.add('hidden'); return; }
  nav.classList.remove('hidden');
  nav.innerHTML = tasks.map(t => {
    const active = t.id === activeTaskId ? ' active' : '';
    const name = t.name && t.name !== t.id ? `<span class="task-chip-name" title="${esc(t.name)}">${esc(t.name)}</span>` : '';
    return `<button type="button" class="task-chip${active}" data-task="${esc(t.id)}"><span class="task-chip-id">${esc(t.id)}</span>${name}</button>`;
  }).join('');
  nav.querySelectorAll('.task-chip').forEach(btn => { btn.addEventListener('click', () => { if (btn.dataset.task && btn.dataset.task !== _deliverable.taskId) void openDeliverable(projectId, btn.dataset.task); }); });
}
async function ensureDeliverablePanel() {
  const pid = S.currentProjectId; if (!pid) return;
  const bodyReady = !!(DOM['deliverable-body']?.innerHTML || '').trim();
  const filesReady = _deliverable.projectId === pid && !!_deliverable.files.length;
  if (_deliverable.projectId === pid && _deliverable.taskId && bodyReady && filesReady) { renderDeliverableTaskNav(pid, _deliverable.taskId, _deliverableTasks); renderDeliverableFileList(_deliverable.files, _deliverable.activePath); return; }
  if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '加载中…';
  let tasks = _deliverableTasks.length ? _deliverableTasks : _deliverableTasksFromDom();
  if (!tasks.length) tasks = await _fetchProjectTasks(pid);
  _deliverableTasks = tasks;
  const taskId = (_deliverable.projectId === pid && _deliverable.taskId) ? _deliverable.taskId : (tasks[0]?.id || '');
  if (!taskId) { if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '暂无任务，交付物将在任务完成后出现。'; return; }
  try { await openDeliverable(pid, taskId, { fromTabSwitch: true }); } catch (e) { if (DOM['deliverable-meta']) DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e); }
}
function setDeliverableActions(visible) { DOM['btn-deliverable-copy']?.classList.toggle('hidden', !visible); DOM['btn-deliverable-download']?.classList.toggle('hidden', !visible); }
function renderDeliverablePreview(content, path) {
  const body = DOM['deliverable-body']; if (!body) return;
  const low = (path || '').toLowerCase();
  if (low.endsWith('.md') && typeof renderAgentMarkdown === 'function') { body.innerHTML = renderAgentMarkdown(content); }
  else if (low.endsWith('.sh') || low.endsWith('.py') || low.endsWith('.js')) { body.innerHTML = `<pre class="trace-pre code-preview">${esc(content)}</pre>`; }
  else { body.innerHTML = `<pre class="trace-pre">${esc(content)}</pre>`; }
}
function sortDeliverableFiles(files) {
  const kindOrder = { doc: 0, script: 1, test: 2, data: 3, output: 4, file: 5 };
  return [...files].sort((a, b) => {
    const ad = (a.path || '').includes('/') ? (a.path || '').split('/').slice(0, -1).join('/') : '';
    const bd = (b.path || '').includes('/') ? (b.path || '').split('/').slice(0, -1).join('/') : '';
    if (ad !== bd) return ad.localeCompare(bd);
    if (a.path === 'README.md') return -1; if (b.path === 'README.md') return 1;
    const ka = kindOrder[a.kind] ?? 9; const kb = kindOrder[b.kind] ?? 9;
    return ka - kb || (a.path || '').localeCompare(b.path || '');
  });
}
function renderDeliverableFileList(files, activePath) {
  const box = DOM['deliverable-files']; if (!box) return;
  if (!files || !files.length) { box.classList.add('hidden'); box.innerHTML = ''; return; }
  box.classList.remove('hidden');
  const sorted = sortDeliverableFiles(files);
  const groups = new Map();
  for (const f of sorted) { const parts = (f.path || '').split('/'); const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : ''; if (!groups.has(dir)) groups.set(dir, []); groups.get(dir).push(f); }
  let html = '';
  for (const [dir, items] of groups) {
    html += `<div class="deliverable-dir">${dir ? `<div class="deliverable-dir-label">${esc(dir)}/</div>` : ''}`;
    html += items.map(f => {
      const kind = DELIV_KIND_LABELS[f.kind] || f.kind || '文件';
      const loc = f.location === 'legacy' ? '旧' : (f.location === 'workspace' ? 'ws' : '');
      const active = f.path === activePath ? ' active' : '';
      return `<button type="button" class="deliverable-file${active}" data-path="${esc(f.path)}"><span class="deliverable-file-kind">${esc(kind)}</span><span class="deliverable-file-name">${esc(f.name || f.path)}</span>${loc ? `<span class="deliverable-file-badge">${esc(loc)}</span>` : ''}</button>`;
    }).join('');
    html += '</div>';
  }
  box.setAttribute('role', 'tree');
  box.setAttribute('aria-label', '交付物文件');
  box.tabIndex = 0;
  box.innerHTML = html;
  box.querySelectorAll('.deliverable-file').forEach(btn => { btn.addEventListener('click', () => loadDeliverableFile(_deliverable.projectId, _deliverable.taskId, btn.dataset.path)); });
  bindDeliverableFileKeys(box);
}
function bindDeliverableFileKeys(box) {
  if (!box || box.dataset.keysBound) return;
  box.dataset.keysBound = '1';
  box.addEventListener('keydown', e => {
    const items = [...box.querySelectorAll('.deliverable-file')];
    if (!items.length) return;
    const idx = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); (items[idx + 1] || items[0])?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); (items[idx - 1] || items[items.length - 1])?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); items[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); items[items.length - 1]?.focus(); }
    else if (e.key === 'Enter' && document.activeElement?.classList.contains('deliverable-file')) {
      e.preventDefault();
      document.activeElement.click();
    }
  });
}
async function loadDeliverableFile(projectId, taskId, path) {
  if (!path) return;
  DOM['deliverable-meta'].textContent = `加载 ${path}…`;
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}/file?path=${encodeURIComponent(path)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '加载失败'));
    if (!d.exists) { DOM['deliverable-meta'].textContent = `文件不存在：${path}`; DOM['deliverable-body'].innerHTML = ''; setDeliverableActions(false); return; }
    _deliverable.content = d.content || ''; _deliverable.activePath = path;
    setDeliverableActions(!!_deliverable.content);
    DOM['deliverable-title'].textContent = `交付物 · ${taskId} · ${path}`;
    DOM['deliverable-meta'].textContent = `${DELIV_KIND_LABELS[d.kind] || '文件'} · ${(d.content || '').length} 字符 · ${path}`;
    renderDeliverablePreview(d.content || '', path);
    renderDeliverableFileList(_deliverable.files, path);
  } catch (e) { DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e); }
}
async function openDeliverable(projectId, taskId, opts = {}) {
  const panel = DOM['project-deliverable']; if (!panel) return;
  highlightProjectTask(taskId);
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
    if (!r.ok) throw new Error(apiErr(d, '加载失败'));
    const files = d.files || []; const primary = d.primary || {};
    _deliverable.files = files;
    if (!files.length && !primary.exists && !d.exists) { DOM['deliverable-meta'].textContent = '该任务暂无交付物'; return; }
    const taskName = (S.projects || []).find(p => p.id === projectId)?.title || '';
    const baseHint = d.base === 'code_project' ? `deliverables/${d.project_dir || taskId + '/'}` : 'deliverables/*.md';
    DOM['deliverable-title'].textContent = `交付物 · ${taskId}${taskName ? ' · ' + taskName : ''}`;
    DOM['deliverable-meta'].textContent = `${d.task_type || '任务'} · ${baseHint} · ${files.length} 个文件 · 左侧选文件预览`;
    renderDeliverableFileList(files, '');
    const defaultPath = primary.path || (files[0] && files[0].path) || '';
    if (defaultPath) { await loadDeliverableFile(projectId, taskId, defaultPath); }
    else if (d.content) { _deliverable.content = d.content; setDeliverableActions(true); renderDeliverablePreview(d.content, `${taskId}_deliverable.md`); }
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) { DOM['deliverable-meta'].textContent = '加载失败：' + (e.message || e); }
}
async function copyDeliverable() {
  if (!_deliverable.content) return;
  try { await navigator.clipboard.writeText(_deliverable.content); showToast('已复制交付物正文', 'success'); } catch (e) { showToast('复制失败：' + (e.message || e), 'error'); }
}
function downloadDeliverable() {
  if (!_deliverable.content) return;
  const blob = new Blob([_deliverable.content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url;
  const ext = (_deliverable.activePath || '').includes('.') ? _deliverable.activePath.split('.').pop() : 'md';
  a.download = `${(_deliverable.taskId || 'deliverable').replace(/[^\w.\-]/g, '_')}.${ext}`;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}