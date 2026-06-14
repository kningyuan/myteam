// ============ Workflow 管理 ============
let _wfList = [];
let _wfCurrentId = null;
let _wfAgentRecords = [];
let _wfTaskTypeRecords = [];
let _wfDeliveryTemplates = [];
let _wfDirty = false;

const WF_TEMPLATE = {
  id: 'GitHub项目调研',
  version: '1.0',
  description: '对任意 GitHub 开源项目做产品/架构/工程化三视角调研并汇总；具体仓库在发起项目时填写 goal',
  options: {
    review_enabled: false,
    split_enabled: false,
    parallel_enabled: false,
    max_parallel: 3,
  },
  tasks: [
    {
      id: 'task-1',
      name: '调研',
      agent: 'research',
      task_type: 'research',
      dependencies: [],
      description: '【对象】目标 GitHub 仓库（链接见【项目目标】）\n【视角】\n【范围】仅 README、docs/',
    },
    {
      id: 'task-2',
      name: '汇总',
      agent: 'main',
      task_type: 'strategy',
      dependencies: ['task-1'],
      description: '【输入】只读 task-1 交付物',
    },
  ],
};

/** 从 YAML 加载的任务/ body 描述缓存（UI 不展示，保存时写回）。 */
let _wfDescCache = {};
let _wfBodyDescCache = {};

function wfIdBadge(id, title) {
  const tip = title || '系统自动生成，不可修改';
  return `<code class="wf-id-badge" title="${wfEsc(tip)}">${wfEsc(id)}</code>`;
}

function wfEnsureTaskIds(tasks) {
  const used = [];
  return (tasks || []).map(t => {
    let id = String(t.id || '').trim();
    if (!id) id = wfNextSeqId('task', used);
    used.push(id);
    return { ...t, id };
  });
}

function wfEnsureBodyIds(bodyTasks) {
  const used = [];
  return (bodyTasks || []).map(t => {
    let id = String(t.id || '').trim();
    if (!id) id = wfNextSeqId('step', used);
    used.push(id);
    return { ...t, id };
  });
}

/** 按列表顺序自动链接上一任务（仅作新建默认值，保存以表单为准）。 */
function wfApplyLinearDeps(tasks) {
  return (tasks || []).map((t, i) => ({
    ...t,
    dependencies: i === 0 ? [] : [tasks[i - 1].id],
  }));
}

function wfApplyBodyLinearDeps(bodyTasks) {
  const rows = wfEnsureBodyIds(bodyTasks);
  return rows.map((t, i) => ({
    ...t,
    dependencies: i === 0 ? [] : [rows[i - 1].id],
  }));
}

function wfAutoTaskDescription({ name, agent, task_type, isLoop }) {
  const lines = [];
  if (name) lines.push(`【任务】${name}`);
  if (isLoop) {
    lines.push('【说明】多轮循环；每轮 body 与 until 见 loops 配置');
  } else {
    if (agent) lines.push(`【执行】${agentDisplayLabel(agent, _wfAgentRecords)}`);
    if (task_type) lines.push(`【类型】${taskTypeDisplayLabel(task_type, _wfTaskTypeRecords)}`);
  }
  lines.push('【详情】见 workflow 描述与发起项目时的【项目目标】');
  return lines.join('\n');
}

function wfAutoBodyDescription({ name, agent, task_type }) {
  const lines = [];
  if (name) lines.push(`【步骤】${name}`);
  if (agent) lines.push(`【执行】${agentDisplayLabel(agent, _wfAgentRecords)}`);
  if (task_type) lines.push(`【类型】${taskTypeDisplayLabel(task_type, _wfTaskTypeRecords)}`);
  lines.push('【详情】见【项目目标】');
  return lines.join('\n');
}

function wfCacheDescriptionsFromWorkflow(data) {
  _wfDescCache = {};
  _wfBodyDescCache = {};
  (data.tasks || []).forEach(t => {
    if (t.id && t.description?.trim()) _wfDescCache[t.id] = t.description;
  });
  (data.loops || []).forEach(lp => {
    (lp.body || []).forEach(b => {
      const key = `${lp.id}:${b.id}`;
      if (b.description?.trim()) _wfBodyDescCache[key] = b.description;
    });
  });
}

function wfResolveTaskDescription(id, fields) {
  const cached = _wfDescCache[id];
  if (cached?.trim()) return cached;
  return wfAutoTaskDescription(fields);
}

function wfResolveBodyDescription(loopId, stepId, fields) {
  const cached = _wfBodyDescCache[`${loopId}:${stepId}`];
  if (cached?.trim()) return cached;
  return wfAutoBodyDescription(fields);
}

function wfReadTaskId(tr) {
  return tr?.dataset?.taskId?.trim() || '';
}

function wfReadBodyId(tr) {
  return tr?.dataset?.bodyId?.trim() || '';
}

/** 加载时将 t-gap / work 等旧 ID 规范为 task-1、step-1… */
function wfStandardizeWorkflowIds(data) {
  const tasks = data.tasks || [];
  if (!tasks.length) return data;
  const needsTaskRenumber = tasks.some(t => !/^task-\d+$/.test(String(t.id || '')));
  const loops = data.loops || [];
  const needsStepRenumber = loops.some(lp =>
    (lp.body || []).some(b => !/^step-\d+$/.test(String(b.id || ''))),
  );
  if (!needsTaskRenumber && !needsStepRenumber) return data;

  const idMap = Object.fromEntries(tasks.map((t, i) => [t.id, `task-${i + 1}`]));
  const stdTasks = tasks.map((t, i) => {
    const id = `task-${i + 1}`;
    return {
      ...t,
      id,
      dependencies: (t.dependencies || []).map(d => idMap[d]).filter(Boolean),
      ...(t.loop ? { loop: id } : {}),
    };
  });

  const stdLoops = loops.map(lp => {
    const ti = tasks.findIndex(t => t.loop === lp.id || t.id === lp.id);
    const lid = ti >= 0 ? `task-${ti + 1}` : (idMap[lp.id] || lp.id);
    const body = lp.body || [];
    const stepMap = Object.fromEntries(body.map((b, j) => [b.id, `step-${j + 1}`]));
    const stdBody = body.map((b, j) => ({
      ...b,
      id: `step-${j + 1}`,
      dependencies: (b.dependencies || []).map(d => stepMap[d]).filter(Boolean),
    }));
    const untilRemapped = (lp.until || []).map(u => ({
      ...u,
      task: u.task && stepMap[u.task] ? stepMap[u.task] : u.task,
    }));
    const until = wfNormalizeLoopUntil({ body: stdBody, until: untilRemapped });
    return { ...lp, id: lid, body: stdBody, until };
  });

  return { ...data, tasks: stdTasks, loops: stdLoops };
}

/** 工业化默认：审计 step Gate 通过即停；旧 REVIEW:PASS 标记迁移为 gate_passed。 */
function wfLastBodyStepId(body) {
  const rows = body || [];
  return rows[rows.length - 1]?.id || 'step-2';
}

function wfDefaultUntilCond(body) {
  return { type: 'gate_passed', task: wfLastBodyStepId(body) };
}

function wfNormalizeLoopUntil(lp) {
  const body = lp.body || [];
  const last = wfLastBodyStepId(body);
  let until = (lp.until || []).map(u => {
    if (!u || typeof u !== 'object') return u;
    if (u.type === 'deliverable_marker') {
      const marker = String(u.marker || '');
      if (!marker || /REVIEW:\s*PASS/i.test(marker)) {
        return { type: 'gate_passed', task: u.task || last };
      }
    }
    return u;
  });
  if (!until.length) until = [wfDefaultUntilCond(body)];
  return until;
}

const WF_UNTIL_TYPES = [
  { id: 'gate_passed', label: 'Gate 通过', hint: '指定 step 经任务类型模板门禁且 status=completed', fields: ['task'] },
  { id: 'review_passed', label: 'Peer Review 通过', hint: '启用 review_enabled 时读 review_done.passed', fields: ['task'] },
  { id: 'task_status', label: '任务状态', hint: '指定 step 达到某终态', fields: ['task', 'status'] },
  { id: 'deliverable_marker', label: '交付物含文本（高级）', hint: '字符串匹配，非推荐', fields: ['task', 'marker'] },
];

const WF_LOOP_OUTCOMES = [
  { id: 'complete', label: 'completed' },
  { id: 'completed', label: 'completed（别名）' },
  { id: 'needs_review', label: 'needs_review' },
  { id: 'failed', label: 'failed' },
];

const WF_TASK_STATUSES = ['completed', 'needs_review', 'failed', 'blocked'];

const WF_LOOP_TEMPLATE = {
  id: 'task-1',
  max_rounds: 5,
  on_pass: 'complete',
  on_exhaust: 'needs_review',
  until: [{ type: 'gate_passed', task: 'step-2' }],
  body: [
    {
      id: 'step-1',
      name: '执行',
      agent: 'research',
      task_type: 'research',
      dependencies: [],
      description: '',
    },
    {
      id: 'step-2',
      name: '审计',
      agent: 'main',
      task_type: 'strategy',
      dependencies: ['step-1'],
      description: '',
    },
  ],
};

function wfEsc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
}

function wfMarkDirty() { _wfDirty = true; }

/** 在已有 id 集合上取下一个 ``prefix-N``（如 task-1、loop-2）。 */
function wfNextSeqId(prefix, used) {
  const set = new Set((used || []).map(s => String(s).trim()).filter(Boolean));
  let n = 1;
  while (set.has(`${prefix}-${n}`)) n += 1;
  return `${prefix}-${n}`;
}

function wfNextTaskId(tasks) {
  return wfNextSeqId('task', (tasks || []).map(t => t.id));
}

function wfNextBodyStepId(bodyTasks) {
  return wfNextSeqId('step', (bodyTasks || []).map(t => t.id));
}

async function wfLoadMeta() {
  try {
    const [ra, rt, rr, rdt] = await Promise.all([
      fetch('/api/agents'),
      fetch('/api/task-types'),
      fetch('/api/agents/registry'),
      fetch('/api/delivery-templates'),
    ]);
    const scanned = (await ra.json()).agents || [];
    const regMap = (await rr.json()).agents || {};
    _wfAgentRecords = scanned.map(a => ({
      ...a,
      name: (regMap[a.id] || {}).name || a.name || a.id,
      task_types: (regMap[a.id] || {}).task_types || [],
      role_hint: (regMap[a.id] || {}).description || '',
    }));
    _wfTaskTypeRecords = (await rt.json()).task_types || [];
    setTaskTypeRecords(_wfTaskTypeRecords);
    _wfDeliveryTemplates = (await rdt.json()).templates || [];
  } catch (_) {
    _wfAgentRecords = [
      { id: 'main', name: '项目经理' },
      { id: 'product', name: '产品专家' },
      { id: 'research', name: '研究员' },
      { id: 'content', name: '内容专家' },
    ];
    _wfTaskTypeRecords = [
      { task_type: 'research', display_name: '调研' },
      { task_type: 'strategy', display_name: '策略分析' },
      { task_type: 'requirements', display_name: '需求' },
      { task_type: 'content', display_name: '内容' },
    ];
    _wfDeliveryTemplates = [];
  }
}

function wfRenderList() {
  const ul = DOM['wf-list'];
  if (!ul) return;
  if (!_wfList.length) {
    ul.innerHTML = '<li class="wf-empty">暂无 workflow</li>';
    return;
  }
  ul.innerHTML = _wfList.map(w => {
    const active = w.id === _wfCurrentId ? ' active' : '';
    const err = w.error ? ` <span class="wf-err" title="${wfEsc(w.error)}">⚠</span>` : '';
    const loopMeta = w.loop_count ? ` · ${w.loop_count} 循环` : '';
    return `<li class="wf-item${active}" data-id="${wfEsc(w.id)}"><span class="wf-item-id">${wfEsc(w.id)}</span><span class="wf-item-meta">${w.task_count || 0} 步${loopMeta}</span>${err}</li>`;
  }).join('');
  ul.querySelectorAll('.wf-item').forEach(li => {
    li.addEventListener('click', () => wfSelect(li.dataset.id));
  });
}

let _wfLoopSpecs = {}; /** 循环任务 id → loop 配置（编辑态） */

function wfSyncLoopSpecsFromWorkflow(data) {
  _wfLoopSpecs = {};
  const loopsById = Object.fromEntries((data.loops || []).map(l => {
    const until = wfNormalizeLoopUntil(l);
    return [l.id, { ...l, until }];
  }));
  (data.tasks || []).forEach(t => {
    if (!t.loop) return;
    const spec = loopsById[t.loop];
    if (spec) _wfLoopSpecs[t.id] = { ...spec };
  });
}

function wfDefaultLoopSpec(taskId) {
  const spec = JSON.parse(JSON.stringify(WF_LOOP_TEMPLATE));
  spec.id = taskId;
  return spec;
}

function wfFillForm(data) {
  data = wfStandardizeWorkflowIds(data);
  if (data.loops) {
    data.loops = data.loops.map(lp => ({ ...lp, until: wfNormalizeLoopUntil(lp) }));
  }
  if (DOM['wf-id']) DOM['wf-id'].value = data.id || '';
  if (DOM['wf-version']) DOM['wf-version'].value = data.version || '1.0';
  if (DOM['wf-description']) DOM['wf-description'].value = data.description || '';
  const opt = data.options || {};
  if (DOM['wf-review']) DOM['wf-review'].checked = !!opt.review_enabled;
  if (DOM['wf-split']) DOM['wf-split'].checked = !!opt.split_enabled;
  if (DOM['wf-parallel']) DOM['wf-parallel'].checked = !!opt.parallel_enabled;
  if (DOM['wf-max-parallel']) DOM['wf-max-parallel'].value = opt.max_parallel ?? 3;
  wfCacheDescriptionsFromWorkflow(data);
  wfSyncLoopSpecsFromWorkflow(data);
  wfRenderTasks(wfEnsureTaskIds(data.tasks || []));
  _wfDirty = false;
}

function wfUntilTypeOptions(selected) {
  return WF_UNTIL_TYPES.map(t =>
    `<option value="${wfEsc(t.id)}" ${t.id === selected ? 'selected' : ''}>${wfEsc(t.label)}</option>`,
  ).join('');
}

function wfBodyIdOptions(bodyIds, selected) {
  const ids = [...new Set([...bodyIds, selected].filter(Boolean))];
  if (!ids.length) return '<option value="">—</option>';
  return ids.map(id =>
    `<option value="${wfEsc(id)}" ${id === selected ? 'selected' : ''}>${wfEsc(id)}</option>`,
  ).join('');
}

/** 从内存数据收集节点（首屏渲染时尚未写入 DOM）。 */
function wfCollectAllWorkflowNodeIdsFromData(tasks, loopSpecs) {
  const nodes = [];
  const seen = new Set();
  (tasks || []).forEach(t => {
    const id = t.id;
    if (id && !seen.has(id)) {
      seen.add(id);
      const name = (t.name || '').trim();
      nodes.push({ id, label: name ? `${id} · ${name}` : id });
    }
    if (t.loop && loopSpecs?.[t.loop]?.body) {
      loopSpecs[t.loop].body.forEach(b => {
        const bid = b.id;
        if (bid && !seen.has(bid)) {
          seen.add(bid);
          const bname = (b.name || '').trim();
          nodes.push({ id: bid, label: bname ? `${bid} · ${bname}` : bid });
        }
      });
    }
  });
  Object.values(loopSpecs || {}).forEach(spec => {
    (spec.body || []).forEach(b => {
      const id = b.id;
      if (id && !seen.has(id)) {
        seen.add(id);
        const name = (b.name || '').trim();
        nodes.push({ id, label: name ? `${id} · ${name}` : id });
      }
    });
  });
  return nodes.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
}

/** 当前 workflow 全部节点 ID（顶层 task + 各循环 body step），统一供依赖多选。 */
function wfCollectAllWorkflowNodeIds() {
  const nodes = [];
  const seen = new Set();
  wfDom('wf-tasks-body')?.querySelectorAll('tr[data-task-row]').forEach(tr => {
    const id = wfReadTaskId(tr);
    const name = tr.querySelector('.wf-t-name')?.value.trim() || '';
    if (id && !seen.has(id)) {
      seen.add(id);
      nodes.push({ id, label: name ? `${id} · ${name}` : id });
    }
  });
  wfDom('wf-tasks-body')?.querySelectorAll('[data-loop-panel]').forEach(panel => {
    panel.querySelectorAll('tr[data-body-row]').forEach(tr => {
      const id = wfReadBodyId(tr);
      const name = tr.querySelector('.wf-b-name')?.value.trim() || '';
      if (id && !seen.has(id)) {
        seen.add(id);
        nodes.push({ id, label: name ? `${id} · ${name}` : id });
      }
    });
  });
  return nodes.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
}

function wfReadDepsSelect(el) {
  if (!el) return [];
  return Array.from(el.selectedOptions).map(o => o.value).filter(Boolean);
}

function wfDepOptionsHtml(nodes, excludeId, selected) {
  const sel = new Set((selected || []).map(String));
  const opts = (nodes || []).filter(n => n.id && n.id !== excludeId);
  if (!opts.length) {
    return '<option disabled value="">（暂无其它节点）</option>';
  }
  return opts.map(n =>
    `<option value="${wfEsc(n.id)}" ${sel.has(n.id) ? 'selected' : ''}>${wfEsc(n.label)}</option>`,
  ).join('');
}

function wfDepMultiSelectHtml(selected, excludeId, nodes) {
  const inner = wfDepOptionsHtml(nodes, excludeId, selected);
  return `<select multiple class="wf-deps-multi wf-input-sm" size="3" title="Ctrl/⌘ 点击多选前置节点">${inner}</select>`;
}

function wfRefreshAllDepSelects() {
  const nodes = wfCollectAllWorkflowNodeIds();
  wfDom('wf-tasks-body')?.querySelectorAll('tr[data-task-row]').forEach(tr => {
    const sel = tr.querySelector('.wf-deps-multi');
    if (!sel) return;
    const currentId = wfReadTaskId(tr);
    const selected = wfReadDepsSelect(sel);
    sel.innerHTML = wfDepOptionsHtml(nodes, currentId, selected);
  });
  wfDom('wf-tasks-body')?.querySelectorAll('tr[data-body-row]').forEach(tr => {
    const sel = tr.querySelector('.wf-deps-multi');
    if (!sel) return;
    const currentId = wfReadBodyId(tr);
    const selected = wfReadDepsSelect(sel);
    sel.innerHTML = wfDepOptionsHtml(nodes, currentId, selected);
  });
}

function wfBindDepSelects(root) {
  (root || wfDom('wf-tasks-body'))?.querySelectorAll('.wf-deps-multi').forEach(sel => {
    sel.addEventListener('change', wfMarkDirty);
  });
}

function wfReadBodyTasks(card, loopId) {
  const tasks = [];
  const assigned = [];
  card.querySelectorAll('tr[data-body-row]').forEach(tr => {
    let id = wfReadBodyId(tr);
    if (!id) id = wfNextSeqId('step', assigned);
    assigned.push(id);
    tr.dataset.bodyId = id;
    const name = tr.querySelector('.wf-b-name')?.value.trim() || '';
    const agent = tr.querySelector('.wf-b-agent')?.value.trim() || '';
    const task_type = tr.querySelector('.wf-b-type')?.value.trim() || 'research';
    const template_id = tr.querySelector('.wf-b-template')?.value.trim() || '';
    const row = {
      id,
      name,
      agent,
      task_type,
      dependencies: wfReadDepsSelect(tr.querySelector('.wf-deps-multi')),
      description: wfResolveBodyDescription(loopId || '', id, { name, agent, task_type }),
    };
    if (template_id) row.template_id = template_id;
    tasks.push(row);
  });
  return tasks;
}

function wfReadUntilRows(card) {
  const until = [];
  card.querySelectorAll('.wf-until-row').forEach(row => {
    const type = row.querySelector('.wf-u-type')?.value.trim() || '';
    if (!type) return;
    const item = { type };
    const task = row.querySelector('.wf-u-task')?.value.trim();
    if (task) item.task = task;
    const marker = row.querySelector('.wf-u-marker')?.value;
    if (marker != null && marker !== '') item.marker = marker;
    const status = row.querySelector('.wf-u-status')?.value.trim();
    if (status) item.status = status;
    until.push(item);
  });
  return until;
}

function wfReadLoopPanel(panel) {
  if (!panel) return null;
  const loopId = panel.dataset.taskId || '';
  const maxRounds = parseInt(panel.querySelector('.wf-l-max')?.value, 10) || 5;
  const body = wfReadBodyTasks(panel, loopId);
  return {
    max_rounds: Math.max(1, maxRounds),
    on_pass: panel.querySelector('.wf-l-on-pass')?.value.trim() || 'complete',
    on_exhaust: panel.querySelector('.wf-l-on-exhaust')?.value.trim() || 'needs_review',
    body,
    until: wfNormalizeLoopUntil({ body, until: wfReadUntilRows(panel) }),
  };
}

function wfReadForm() {
  const rawTasks = [];
  const loops = [];
  const assignedIds = [];
  wfDom('wf-tasks-body')?.querySelectorAll('tr[data-task-row]').forEach(tr => {
    const mode = tr.querySelector('.wf-t-mode')?.value || 'normal';
    let id = wfReadTaskId(tr);
    if (!id) id = wfNextSeqId('task', assignedIds);
    assignedIds.push(id);
    tr.dataset.taskId = id;
    const name = tr.querySelector('.wf-t-name')?.value.trim() || '';
    const agent = tr.querySelector('.wf-t-agent')?.value.trim() || '';
    const task_type = tr.querySelector('.wf-t-type')?.value.trim() || 'research';
    const isLoop = mode === 'loop_ref';
    const base = {
      id,
      name,
      dependencies: wfReadDepsSelect(tr.querySelector('.wf-deps-multi')),
      description: wfResolveTaskDescription(id, { name, agent, task_type, isLoop }),
    };
    if (isLoop) {
      const panel = tr.nextElementSibling?.matches('[data-loop-detail]')
        ? tr.nextElementSibling.querySelector('[data-loop-panel]')
        : null;
      const spec = wfReadLoopPanel(panel) || _wfLoopSpecs[id] || wfDefaultLoopSpec(id);
      spec.id = id;
      loops.push(spec);
      rawTasks.push({ ...base, loop: id });
    } else {
      const template_id = tr.querySelector('.wf-t-template')?.value.trim() || '';
      const item = { ...base, agent, task_type };
      if (template_id) item.template_id = template_id;
      rawTasks.push(item);
    }
  });
  const tasks = wfEnsureTaskIds(rawTasks);
  const data = {
    id: DOM['wf-id'].value.trim(),
    version: DOM['wf-version'].value.trim() || '1.0',
    description: DOM['wf-description'].value.trim(),
    options: {
      review_enabled: !!DOM['wf-review']?.checked,
      split_enabled: !!DOM['wf-split']?.checked,
      parallel_enabled: !!DOM['wf-parallel']?.checked,
      max_parallel: parseInt(DOM['wf-max-parallel']?.value, 10) || 3,
    },
    tasks,
  };
  if (loops.length) data.loops = loops;
  return data;
}

function wfTaskTypesForAgent(agentId) {
  const rec = _wfAgentRecords.find(a => a.id === agentId) || {};
  return rec.task_types || [];
}

function wfAgentOptions(selected) {
  const ids = [...new Set([..._wfAgentRecords.map(a => a.id), selected].filter(Boolean))];
  return ids.map(id => {
    const rec = _wfAgentRecords.find(a => a.id === id) || {};
    const label = agentDisplayLabel(id, _wfAgentRecords);
    const hint = [rec.role_hint, !(rec.task_types || []).length ? '未配置可执行任务类型' : '']
      .filter(Boolean)
      .join('；');
    return `<option value="${wfEsc(id)}" ${id === selected ? 'selected' : ''} title="${wfEsc(hint)}">${wfEsc(label)}</option>`;
  }).join('');
}

function wfTypeOptions(selected, agentId) {
  if (!agentId) {
    return '<option value="">先选择 Agent</option>';
  }
  const allowed = wfTaskTypesForAgent(agentId);
  if (!allowed.length) {
    return '<option value="">该 Agent 未配置任务类型</option>';
  }
  const ids = [...new Set([...allowed, selected].filter(Boolean))].filter(
    id => allowed.includes(id),
  );
  return ids.map(id => {
    const label = taskTypeDisplayLabel(id, _wfTaskTypeRecords);
    return `<option value="${wfEsc(id)}" ${id === selected ? 'selected' : ''}>${wfEsc(label)}</option>`;
  }).join('');
}

function wfTemplateRecord(id) {
  return _wfDeliveryTemplates.find(t => t.id === id) || null;
}

function wfTemplatesForTaskType(taskType) {
  const tt = (taskType || '').trim();
  if (!tt) return _wfDeliveryTemplates;
  const bound = _wfDeliveryTemplates.filter(t => (t.task_types || []).includes(tt));
  const unbound = _wfDeliveryTemplates.filter(t => !(t.task_types || []).length);
  if (bound.length) return [...bound, ...unbound];
  return _wfDeliveryTemplates;
}

function wfTemplateOptions(selected, taskType) {
  const pool = wfTemplatesForTaskType(taskType);
  const opts = ['<option value="">（任务类型默认）</option>'];
  const ids = [...new Set([...pool.map(t => t.id), selected].filter(Boolean))];
  ids.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  for (const id of ids) {
    const rec = wfTemplateRecord(id) || { id, display_name: id };
    if (taskType && (rec.task_types || []).length && !(rec.task_types || []).includes(taskType) && id !== selected) {
      continue;
    }
    const label = rec.display_name || id;
    const hint = rec.description ? ` — ${rec.description.slice(0, 60)}` : '';
    opts.push(
      `<option value="${wfEsc(id)}" ${id === selected ? 'selected' : ''} title="${wfEsc(hint)}">${wfEsc(label)}</option>`,
    );
  }
  return opts.join('');
}

function wfRefreshTemplateCellHint(sel) {
  const cell = sel?.closest('.wf-template-cell');
  if (!cell) return;
  const rec = wfTemplateRecord(sel.value);
  const hintText = rec?.section_count != null ? `${rec.section_count} 章 Gate` : '';
  let hintEl = cell.querySelector('small.hint');
  if (hintText) {
    if (!hintEl) {
      hintEl = document.createElement('small');
      hintEl.className = 'hint';
      cell.appendChild(hintEl);
    }
    hintEl.textContent = hintText;
  } else if (hintEl) hintEl.remove();
}

function wfBindTemplateSelect(sel) {
  if (!sel || sel.dataset.wfTplBound) return;
  sel.dataset.wfTplBound = '1';
  sel.addEventListener('change', () => {
    wfRefreshTemplateCellHint(sel);
    wfMarkDirty();
  });
}

function wfTemplateSelectHtml(className, selected, taskType) {
  const rec = selected ? wfTemplateRecord(selected) : null;
  const hint = rec?.section_count != null
    ? `${rec.section_count} 章 Gate`
    : '';
  return `<div class="wf-template-cell"><select class="${className} wf-template-select wf-input-sm" title="交付模板：Gate/Review 章节结构">${wfTemplateOptions(selected, taskType)}</select>${hint ? `<small class="hint">${wfEsc(hint)}</small>` : ''}</div>`;
}

function wfRefreshTemplateSelectForRow(tr, isBody) {
  const typeSel = tr?.querySelector(isBody ? '.wf-b-type' : '.wf-t-type');
  const cell = tr?.querySelector('.wf-template-cell');
  if (!typeSel || !cell) return;
  const tt = typeSel.value || '';
  const prev = cell.querySelector('select')?.value || '';
  const pool = wfTemplatesForTaskType(tt);
  const ok = !prev || pool.some(t => t.id === prev) || !(wfTemplateRecord(prev)?.task_types || []).length;
  const next = ok ? prev : '';
  cell.innerHTML = wfTemplateSelectHtml(isBody ? 'wf-b-template' : 'wf-t-template', next, tt);
  wfBindTemplateSelect(cell.querySelector('select'));
}

function wfSyncTaskTypeSelect(tr) {
  if (tr.querySelector('.wf-t-mode')?.value === 'loop_ref') {
    tr.classList.remove('wf-cap-mismatch');
    const hint = tr.querySelector('.wf-cap-hint');
    if (hint) { hint.textContent = ''; hint.style.display = 'none'; }
    return;
  }
  const agentSel = tr.querySelector('.wf-t-agent');
  const typeSel = tr.querySelector('.wf-t-type');
  if (!agentSel || !typeSel) return;
  const agentId = agentSel.value;
  const current = typeSel.value;
  const allowed = wfTaskTypesForAgent(agentId);
  typeSel.innerHTML = wfTypeOptions(current, agentId);
  if (allowed.length && current && !allowed.includes(current)) {
    typeSel.value = allowed[0];
  }
  tr.classList.toggle('wf-cap-mismatch', !allowed.length);
  const hint = tr.querySelector('.wf-cap-hint');
  if (hint) {
    hint.textContent = allowed.length ? '' : '请在管理 Tab 为该 Agent 勾选可执行任务类型';
    hint.style.display = allowed.length ? 'none' : 'block';
  }
  wfRefreshTemplateSelectForRow(tr, false);
}

function wfMoveTask(idx, delta) {
  const data = wfReadForm();
  wfSyncLoopSpecsFromWorkflow(data);
  const tasks = data.tasks;
  const next = idx + delta;
  if (next < 0 || next >= tasks.length) return;
  [tasks[idx], tasks[next]] = [tasks[next], tasks[idx]];
  wfRenderTasks(tasks);
  wfMarkDirty();
}

function wfApplySuggestedOptions(opt) {
  if (!opt) return;
  if (DOM['wf-review']) DOM['wf-review'].checked = !!opt.review_enabled;
  if (DOM['wf-split']) DOM['wf-split'].checked = !!opt.split_enabled;
  if (DOM['wf-parallel']) DOM['wf-parallel'].checked = !!opt.parallel_enabled;
  if (DOM['wf-max-parallel'] && opt.max_parallel != null) {
    DOM['wf-max-parallel'].value = opt.max_parallel;
  }
}

const WF_PATTERN_LABEL = {
  'github-parallel-research': 'GitHub 三视角并行调研',
  'smoke-research': '最小调研+汇总',
  'content-pipeline': '内容生产流水线',
  'content-publish-pipeline': '内容生产+发布',
  'data-analysis-pipeline': '数据分析流水线',
  'geo-pipeline': 'GEO 优化流水线',
  'delivery-lite': '轻量软件交付',
  'linear-research': '调研+汇总',
};

function wfSyncBodyTaskTypeSelect(tr) {
  const agentSel = tr.querySelector('.wf-b-agent');
  const typeSel = tr.querySelector('.wf-b-type');
  if (!agentSel || !typeSel) return;
  const agentId = agentSel.value;
  const current = typeSel.value;
  typeSel.innerHTML = wfTypeOptions(current, agentId);
  const allowed = wfTaskTypesForAgent(agentId);
  if (allowed.length && current && !allowed.includes(current)) {
    typeSel.value = allowed[0];
  }
  wfRefreshTemplateSelectForRow(tr, true);
}

function wfSyncUntilRowFields(row) {
  const type = row.querySelector('.wf-u-type')?.value || '';
  const spec = WF_UNTIL_TYPES.find(t => t.id === type) || WF_UNTIL_TYPES[0];
  const panel = row.closest('[data-loop-panel]');
  const loopId = panel?.dataset?.taskId || '';
  const bodyIds = wfReadBodyTasks(panel, loopId).map(t => t.id).filter(Boolean);
  row.querySelectorAll('.wf-until-field[data-field]').forEach(el => {
    const field = el.dataset.field;
    el.style.display = spec.fields.includes(field) ? '' : 'none';
    if (field === 'task') {
      const sel = el.querySelector('.wf-u-task');
      const cur = sel?.value || '';
      if (sel) sel.innerHTML = wfBodyIdOptions(bodyIds, cur);
    }
  });
}

function wfUntilRowHtml(cond, bodyIds) {
  const type = cond?.type || 'gate_passed';
  const spec = WF_UNTIL_TYPES.find(t => t.id === type) || WF_UNTIL_TYPES[0];
  const fields = spec.fields.map(field => {
    if (field === 'task') {
      return `<div class="wf-until-field" data-field="task"><label>step</label><select class="wf-u-task">${wfBodyIdOptions(bodyIds, cond?.task || bodyIds[bodyIds.length - 1] || '')}</select></div>`;
    }
    if (field === 'marker') {
      return `<div class="wf-until-field" data-field="marker"><label>标记文本</label><input class="wf-u-marker wf-input-sm" value="${wfEsc(cond?.marker || '')}" placeholder="可选"></div>`;
    }
    if (field === 'status') {
      const opts = WF_TASK_STATUSES.map(s =>
        `<option value="${wfEsc(s)}" ${s === (cond?.status || 'completed') ? 'selected' : ''}>${wfEsc(s)}</option>`,
      ).join('');
      return `<div class="wf-until-field" data-field="status"><label>目标状态</label><select class="wf-u-status">${opts}</select></div>`;
    }
    return '';
  }).join('');
  return `
    <div class="wf-until-row" title="${wfEsc(spec.hint || '')}">
      <div class="wf-until-field"><label>退出条件</label><select class="wf-u-type">${wfUntilTypeOptions(type)}</select></div>
      ${fields}
      <button type="button" class="btn-icon wf-u-del" title="删除条件" data-icon="trash"></button>
    </div>`;
}

function wfBodyTaskRowHtml(t, i, rowCount, nodes) {
  const id = t.id || wfNextSeqId('step', []);
  return `
    <tr data-body-row data-body-idx="${i}" data-body-id="${wfEsc(id)}">
      <td class="wf-col-order">
        <div class="wf-order-btns">
          <button type="button" class="btn-xs primary wf-b-up" ${i === 0 ? 'disabled' : ''} title="上移">↑</button>
          <button type="button" class="btn-xs primary wf-b-down" ${i === rowCount - 1 ? 'disabled' : ''} title="下移">↓</button>
        </div>
      </td>
      <td>${wfIdBadge(id)}</td>
      <td><input class="wf-b-name wf-input-sm" value="${wfEsc(t.name)}" placeholder="步骤名"></td>
      <td><select class="wf-b-agent wf-input-sm">${wfAgentOptions(t.agent)}</select></td>
      <td><div class="wf-type-cell"><select class="wf-b-type wf-input-sm">${wfTypeOptions(t.task_type, t.agent)}</select></div></td>
      <td>${wfTemplateSelectHtml('wf-b-template', t.template_id || '', t.task_type || '')}</td>
      <td>${wfDepMultiSelectHtml(t.dependencies || [], id, nodes)}</td>
      <td><button type="button" class="btn-icon wf-b-del" title="删除" data-icon="trash"></button></td>
    </tr>`;
}

function wfRenderBodyTable(card, bodyTasks) {
  const tbody = card.querySelector('.wf-loop-body-body');
  if (!tbody) return;
  const loopId = card.dataset.taskId || '';
  const rows = bodyTasks.length
    ? wfEnsureBodyIds(bodyTasks)
    : wfEnsureBodyIds(JSON.parse(JSON.stringify(WF_LOOP_TEMPLATE.body)));
  const nodes = wfCollectAllWorkflowNodeIds();
  tbody.innerHTML = rows.map((t, i) => wfBodyTaskRowHtml(t, i, rows.length, nodes)).join('');
  wfRefreshAllDepSelects();
  wfBindDepSelects(tbody);
  tbody.querySelectorAll('.wf-b-name').forEach(el => {
    el.addEventListener('input', () => { wfRefreshAllDepSelects(); wfMarkDirty(); });
  });
  tbody.querySelectorAll('.wf-b-agent').forEach(sel => {
    sel.addEventListener('change', () => {
      const tr = sel.closest('tr');
      if (tr) wfSyncBodyTaskTypeSelect(tr);
      wfMarkDirty();
    });
  });
  tbody.querySelectorAll('.wf-b-template').forEach(wfBindTemplateSelect);
  tbody.querySelectorAll('input,select,textarea').forEach(el => {
    if (el.classList.contains('wf-b-template')) return;
    el.addEventListener('input', wfMarkDirty);
  });
  tbody.querySelectorAll('tr[data-body-row]').forEach(tr => wfSyncBodyTaskTypeSelect(tr));
  tbody.querySelectorAll('.wf-b-up').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.closest('tr')?.dataset.bodyIdx, 10);
      const tasks = wfReadBodyTasks(card, loopId);
      if (Number.isNaN(idx) || idx <= 0) return;
      [tasks[idx - 1], tasks[idx]] = [tasks[idx], tasks[idx - 1]];
      wfRenderBodyTable(card, tasks);
      wfRefreshUntilTasksInPanel(card);
      wfMarkDirty();
    });
  });
  tbody.querySelectorAll('.wf-b-down').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.closest('tr')?.dataset.bodyIdx, 10);
      const tasks = wfReadBodyTasks(card, loopId);
      if (Number.isNaN(idx) || idx >= tasks.length - 1) return;
      [tasks[idx], tasks[idx + 1]] = [tasks[idx + 1], tasks[idx]];
      wfRenderBodyTable(card, tasks);
      wfRefreshUntilTasksInPanel(card);
      wfMarkDirty();
    });
  });
  tbody.querySelectorAll('.wf-b-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.closest('tr')?.dataset.bodyIdx, 10);
      const tasks = wfReadBodyTasks(card, loopId);
      if (!Number.isNaN(idx)) tasks.splice(idx, 1);
      wfRenderBodyTable(card, tasks.length ? tasks : []);
      wfRefreshUntilTasksInPanel(card);
      wfMarkDirty();
    });
  });
  hydrateIcons(tbody);
}

function wfRefreshUntilTasksInPanel(panel) {
  if (!panel) return;
  const loopId = panel.dataset.taskId || '';
  const bodyIds = wfReadBodyTasks(panel, loopId).map(t => t.id).filter(Boolean);
  panel.querySelectorAll('.wf-until-row').forEach(row => {
    const sel = row.querySelector('.wf-u-task');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = wfBodyIdOptions(bodyIds, cur);
  });
}

function wfDom(id) {
  return DOM[id] || document.getElementById(id);
}

function wfBindLoopPanel(panel) {
  panel.querySelectorAll('.wf-l-max, .wf-l-on-pass, .wf-l-on-exhaust').forEach(el => {
    el.addEventListener('input', wfMarkDirty);
    el.addEventListener('change', wfMarkDirty);
  });
  panel.querySelector('.wf-add-body')?.addEventListener('click', () => {
    const loopId = panel.dataset.taskId || '';
    const tasks = wfReadBodyTasks(panel, loopId);
    tasks.push({
      id: wfNextBodyStepId(tasks), name: '', agent: 'research',
      task_type: 'research',
      dependencies: tasks.length ? [tasks[tasks.length - 1].id] : [],
      description: '',
    });
    wfRenderBodyTable(panel, tasks);
    wfRefreshUntilTasksInPanel(panel);
    wfMarkDirty();
  });
  panel.querySelector('.wf-add-until')?.addEventListener('click', () => {
    const list = panel.querySelector('.wf-until-list');
    const loopId = panel.dataset.taskId || '';
    const bodyIds = wfReadBodyTasks(panel, loopId).map(t => t.id).filter(Boolean);
    list.insertAdjacentHTML('beforeend', wfUntilRowHtml(
      wfDefaultUntilCond(bodyIds.map(id => ({ id }))), bodyIds,
    ));
    const row = list.lastElementChild;
    wfBindUntilRow(row);
    wfMarkDirty();
    hydrateIcons(row);
  });
  panel.querySelectorAll('.wf-until-row').forEach(row => wfBindUntilRow(row));
  const loopId = panel.dataset.taskId || '';
  let body = wfReadBodyTasks(panel, loopId);
  if (!body.length) {
    body = wfEnsureBodyIds(JSON.parse(JSON.stringify(WF_LOOP_TEMPLATE.body)));
  }
  wfRenderBodyTable(panel, body);
}

function wfBindUntilRow(row) {
  row.querySelector('.wf-u-type')?.addEventListener('change', () => {
    const panel = row.closest('[data-loop-panel]');
    if (!panel) return;
    const loopId = panel.dataset.taskId || '';
    const bodyIds = wfReadBodyTasks(panel, loopId).map(t => t.id).filter(Boolean);
    const cond = {
      type: row.querySelector('.wf-u-type')?.value,
      task: row.querySelector('.wf-u-task')?.value,
      marker: row.querySelector('.wf-u-marker')?.value,
      status: row.querySelector('.wf-u-status')?.value,
    };
    const wrap = document.createElement('div');
    wrap.innerHTML = wfUntilRowHtml(cond, bodyIds);
    const newRow = wrap.firstElementChild;
    row.replaceWith(newRow);
    wfBindUntilRow(newRow);
    wfMarkDirty();
    hydrateIcons(newRow);
  });
  row.querySelectorAll('input,select').forEach(el => el.addEventListener('input', wfMarkDirty));
  row.querySelector('.wf-u-del')?.addEventListener('click', () => {
    row.remove();
    wfMarkDirty();
  });
  wfSyncUntilRowFields(row);
}

function wfLoopInlineHtml(spec, taskId) {
  const body = spec.body?.length ? wfEnsureBodyIds(spec.body) : wfEnsureBodyIds(WF_LOOP_TEMPLATE.body);
  const untilRaw = spec.until?.length ? spec.until : WF_LOOP_TEMPLATE.until;
  const until = wfNormalizeLoopUntil({ body, until: untilRaw });
  const bodyIds = body.map(t => t.id).filter(Boolean);
  const untilHtml = until.map(u => wfUntilRowHtml(u, bodyIds)).join('');
  const bodyRows = body.map((t, i) => wfBodyTaskRowHtml(t, i, body.length)).join('');
  return `
    <div class="wf-loop-inline" data-loop-panel data-task-id="${wfEsc(taskId)}">
      <div class="wf-loop-inline-head">Work → 审计 多轮循环；退出由 <strong>Gate</strong>（交付模板 + 任务类型 + Agent 交付）判定</div>
      <div class="wf-loop-inline-meta">
        <div><label>最大轮次</label><input class="wf-l-max wf-input-sm" type="number" min="1" max="20" value="${spec.max_rounds ?? 5}"></div>
        <div><label>通过时</label><select class="wf-l-on-pass">${WF_LOOP_OUTCOMES.map(o => `<option value="${wfEsc(o.id)}" ${o.id === (spec.on_pass || 'complete') ? 'selected' : ''}>${wfEsc(o.label)}</option>`).join('')}</select></div>
        <div><label>轮次用尽</label><select class="wf-l-on-exhaust">${WF_LOOP_OUTCOMES.map(o => `<option value="${wfEsc(o.id)}" ${o.id === (spec.on_exhaust || 'needs_review') ? 'selected' : ''}>${wfEsc(o.label)}</option>`).join('')}</select></div>
      </div>
      <div class="wf-loop-section-title">每轮 body（执行 → 审计）</div>
      <div class="wf-loop-body-scroll">
        <table class="wf-tasks-table wf-body-table">
          <thead><tr><th class="wf-col-order">顺序</th><th>ID</th><th>名称</th><th>Agent</th><th>类型</th><th>交付模板</th><th>依赖</th><th></th></tr></thead>
          <tbody class="wf-loop-body-body">${bodyRows}</tbody>
        </table>
      </div>
      <button type="button" class="btn-secondary btn-sm wf-add-body">添加步骤</button>
      <div class="wf-loop-section-title">何时停止循环（满足任一）</div>
      <p class="hint wf-until-hint">推荐「Gate 通过」：内核按该 step 的<strong>交付模板</strong>与<strong>任务类型</strong>验收交付物。</p>
      <div class="wf-until-list">${untilHtml}</div>
      <button type="button" class="btn-secondary btn-sm wf-add-until">添加退出条件</button>
    </div>`;
}

function wfLoopDetailRowHtml(spec, taskId, taskIdx) {
  return `
    <tr data-loop-detail data-task-idx="${taskIdx}" class="wf-loop-detail-row">
      <td colspan="9">${wfLoopInlineHtml(spec, taskId)}</td>
    </tr>`;
}

function wfTaskRowHtml(t, i, rowCount, nodes) {
  const isLoop = !!(t.loop && String(t.loop).trim());
  const mode = isLoop ? 'loop_ref' : 'normal';
  const spec = isLoop ? (_wfLoopSpecs[t.id] || wfDefaultLoopSpec(t.id)) : null;
  const id = t.id || wfNextTaskId([]);
  let html = `
    <tr data-task-row data-task-idx="${i}" data-task-id="${wfEsc(id)}"${t.template_id ? ` data-template-id="${wfEsc(t.template_id)}"` : ''}>
      <td class="wf-col-order">
        <div class="wf-order-btns">
          <button type="button" class="btn-xs primary wf-t-up" ${i === 0 ? 'disabled' : ''} title="上移">↑</button>
          <button type="button" class="btn-xs primary wf-t-down" ${i === rowCount - 1 ? 'disabled' : ''} title="下移">↓</button>
        </div>
      </td>
      <td>${wfIdBadge(id)}</td>
      <td><input class="wf-t-name wf-input-sm" value="${wfEsc(t.name)}" placeholder="任务名"></td>
      <td>
        <select class="wf-t-mode wf-input-sm">
          <option value="normal" ${mode === 'normal' ? 'selected' : ''}>普通</option>
          <option value="loop_ref" ${mode === 'loop_ref' ? 'selected' : ''}>循环</option>
        </select>
      </td>
      <td><div class="wf-t-agent-cell"><select class="wf-t-agent wf-input-sm">${wfAgentOptions(t.agent)}</select></div></td>
      <td><div class="wf-type-cell${isLoop ? ' wf-t-type-disabled' : ''}"><select class="wf-t-type wf-input-sm">${wfTypeOptions(t.task_type, t.agent)}</select><small class="wf-cap-hint hint"></small></div></td>
      <td class="wf-t-template-cell">${isLoop ? '<span class="hint">—</span>' : wfTemplateSelectHtml('wf-t-template', t.template_id || '', t.task_type || '')}</td>
      <td>${wfDepMultiSelectHtml(t.dependencies || [], id, nodes)}</td>
      <td><button type="button" class="btn-icon wf-t-del" title="删除" data-icon="trash"></button></td>
    </tr>`;
  if (isLoop && spec) {
    html += wfLoopDetailRowHtml(spec, id, i);
  }
  return html;
}

function wfSyncTaskRowMode(tr) {
  const mode = tr.querySelector('.wf-t-mode')?.value || 'normal';
  const agentCell = tr.querySelector('.wf-t-agent-cell');
  const typeCell = tr.querySelector('.wf-type-cell');
  const isLoop = mode === 'loop_ref';
  if (agentCell) agentCell.style.display = isLoop ? 'none' : '';
  if (typeCell) typeCell.classList.toggle('wf-t-type-disabled', isLoop);
  const tplCell = tr.querySelector('.wf-t-template-cell');
  if (tplCell) {
    if (isLoop) {
      const sel = tplCell.querySelector('.wf-t-template');
      if (sel?.value) tr.dataset.templateId = sel.value;
      tplCell.style.display = 'none';
    } else {
      tplCell.style.display = '';
      if (!tplCell.querySelector('.wf-t-template')) {
        const saved = tr.dataset.templateId || tr.getAttribute('data-template-id') || '';
        const tt = tr.querySelector('.wf-t-type')?.value || '';
        tplCell.innerHTML = wfTemplateSelectHtml('wf-t-template', saved, tt);
        wfBindTemplateSelect(tplCell.querySelector('.wf-t-template'));
      }
    }
  }
  const detail = tr.nextElementSibling;
  const hasDetail = detail?.matches('[data-loop-detail]');
  if (isLoop) {
    let tid = wfReadTaskId(tr);
    if (!tid) {
      tid = wfNextTaskId([]);
      tr.dataset.taskId = tid;
    }
    if (!_wfLoopSpecs[tid]) _wfLoopSpecs[tid] = wfDefaultLoopSpec(tid);
    if (!hasDetail) {
      const idx = tr.dataset.taskIdx || '0';
      tr.insertAdjacentHTML('afterend', wfLoopDetailRowHtml(_wfLoopSpecs[tid], tid, idx));
      const panel = tr.nextElementSibling?.querySelector('[data-loop-panel]');
      if (panel) wfBindLoopPanel(panel);
      hydrateIcons(tr.nextElementSibling);
      wfRefreshAllDepSelects();
    } else {
      detail.style.display = '';
      wfRefreshAllDepSelects();
    }
  } else if (hasDetail) {
    detail.remove();
    const tid = wfReadTaskId(tr);
    if (tid) delete _wfLoopSpecs[tid];
  }
}

function wfRenderTasks(tasks) {
  const body = wfDom('wf-tasks-body');
  if (!body) {
    console.error('workflow: #wf-tasks-body 未找到，请硬刷新页面');
    return;
  }
  const rows = wfEnsureTaskIds(tasks.length
    ? tasks
    : [{
      id: wfNextTaskId([]), name: '', agent: 'research', task_type: 'research',
      dependencies: [], description: '',
    }]);
  const nodes = wfCollectAllWorkflowNodeIdsFromData(rows, _wfLoopSpecs);
  body.innerHTML = rows.map((t, i) => wfTaskRowHtml(t, i, rows.length, nodes)).join('');
  body.querySelectorAll('tr[data-loop-detail] [data-loop-panel]').forEach(panel => wfBindLoopPanel(panel));
  wfRefreshAllDepSelects();
  wfBindDepSelects(body);
  body.querySelectorAll('.wf-t-name').forEach(el => {
    el.addEventListener('input', () => { wfRefreshAllDepSelects(); wfMarkDirty(); });
  });
  body.querySelectorAll('.wf-t-template').forEach(wfBindTemplateSelect);
  body.querySelectorAll('input,select,textarea').forEach(el => {
    if (el.classList.contains('wf-deps-multi') || el.classList.contains('wf-t-template')) return;
    el.addEventListener('input', wfMarkDirty);
  });
  body.querySelectorAll('tr[data-task-row]').forEach(tr => {
    wfSyncTaskTypeSelect(tr);
    wfSyncTaskRowMode(tr);
  });
  body.querySelectorAll('.wf-t-mode').forEach(sel => {
    sel.addEventListener('change', () => {
      const tr = sel.closest('tr');
      if (!tr) return;
      wfSyncTaskRowMode(tr);
      wfMarkDirty();
    });
  });
  body.querySelectorAll('.wf-t-agent').forEach(sel => {
    sel.addEventListener('change', () => {
      const tr = sel.closest('tr');
      if (tr) wfSyncTaskTypeSelect(tr);
      wfMarkDirty();
    });
  });
  body.querySelectorAll('.wf-t-type').forEach(sel => {
    sel.addEventListener('change', () => {
      const tr = sel.closest('tr');
      if (tr) wfSyncTaskTypeSelect(tr);
      wfMarkDirty();
    });
  });
  body.querySelectorAll('.wf-t-up').forEach(btn => {
    btn.addEventListener('click', () => {
      const tr = btn.closest('tr[data-task-row]');
      const idx = parseInt(tr?.dataset.taskIdx, 10);
      if (!Number.isNaN(idx)) wfMoveTask(idx, -1);
    });
  });
  body.querySelectorAll('.wf-t-down').forEach(btn => {
    btn.addEventListener('click', () => {
      const tr = btn.closest('tr[data-task-row]');
      const idx = parseInt(tr?.dataset.taskIdx, 10);
      if (!Number.isNaN(idx)) wfMoveTask(idx, 1);
    });
  });
  body.querySelectorAll('.wf-t-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const data = wfReadForm();
      wfSyncLoopSpecsFromWorkflow(data);
      const tasksNow = data.tasks;
      const tr = btn.closest('tr[data-task-row]');
      const idx = parseInt(tr?.dataset.taskIdx, 10);
      if (!Number.isNaN(idx)) tasksNow.splice(idx, 1);
      wfRenderTasks(tasksNow.length ? tasksNow : []);
      wfMarkDirty();
    });
  });
  hydrateIcons(body);
}

async function wfSuggestTasks() {
  const desc = DOM['wf-description']?.value?.trim();
  if (!desc) { wfShowStatus('请先填写描述', 'error'); return; }
  const existing = wfReadForm().tasks;
  const hasContent = existing.some(t => t.id || t.name || (t.description || '').trim());
  if (hasContent && !await showConfirm('将用推导结果替换当前任务列表，继续？', { title: '自动推导', okText: '替换' })) return;
  const btn = DOM['wf-suggest'];
  if (btn) btn.disabled = true;
  try {
    const r = await fetch('/api/workflows/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '推导失败'));
    await wfLoadMeta();
    const w = d.workflow || {};
    wfApplySuggestedOptions(w.options);
    wfRenderTasks(w.tasks || []);
    wfMarkDirty();
    const label = d.pattern_label || WF_PATTERN_LABEL[d.pattern] || d.pattern || '已推导';
    const warn = (d.warnings || []).length ? `；注意：${d.warnings.join('；')}` : '';
    wfShowStatus(`✓ ${label}（${(w.tasks || []).length} 步）${warn}`, warn ? 'info' : 'success');
  } catch (e) {
    wfShowStatus('推导失败: ' + e.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function wfLoadList() {
  try {
    const r = await fetch('/api/workflows');
    const d = await r.json();
    _wfList = d.workflows || [];
  } catch (e) {
    _wfList = [];
    wfShowStatus('加载列表失败: ' + e.message, 'error');
  }
  wfRenderList();
}

async function wfSelect(id) {
  if (!id) return;
  if (_wfDirty && !await showConfirm('有未保存的修改，放弃？', { title: '未保存', okText: '放弃' })) return;
  try {
    const r = await fetch(`/api/workflows/${encodeURIComponent(id)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '加载失败'));
    _wfCurrentId = id;
    wfFillForm(d.workflow || {});
    wfRenderList();
    wfShowStatus('', '');
    DOM['wf-editor']?.classList.remove('hidden');
    DOM['wf-welcome']?.classList.add('hidden');
  } catch (e) {
    wfShowStatus('加载失败: ' + e.message, 'error');
  }
}

function wfNew() {
  _wfCurrentId = null;
  wfFillForm(JSON.parse(JSON.stringify(WF_TEMPLATE)));
  wfRenderList();
  DOM['wf-editor']?.classList.remove('hidden');
  DOM['wf-welcome']?.classList.add('hidden');
  wfShowStatus('新建 workflow — 修改 id 后保存', 'info');
}

async function wfSave() {
  const data = wfReadForm();
  if (!data.id) { wfShowStatus('请填写 workflow ID', 'error'); return; }
  if (!data.tasks.length) { wfShowStatus('至少一个任务', 'error'); return; }
  for (const lp of data.loops || []) {
    if (!lp.body.length) {
      wfShowStatus(`循环「${lp.id}」至少需要一个 body 任务`, 'error');
      return;
    }
    if (!lp.until.length) {
      wfShowStatus(`循环「${lp.id}」至少需要一个 until 条件`, 'error');
      return;
    }
  }
  for (const t of data.tasks) {
    if (t.loop && t.loop !== t.id) {
      wfShowStatus(`循环任务「${t.id}」的 loop 引用应与任务 ID 一致`, 'error');
      return;
    }
  }
  const method = _wfCurrentId ? 'PUT' : 'POST';
  const url = _wfCurrentId
    ? `/api/workflows/${encodeURIComponent(_wfCurrentId)}`
    : '/api/workflows';
  try {
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow: data }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '保存失败'));
    _wfCurrentId = d.id || data.id;
    _wfDirty = false;
    await wfLoadList();
    wfShowStatus('✓ 已保存', 'success');
    if (typeof window.refreshWorkflowSelect === 'function') window.refreshWorkflowSelect();
  } catch (e) {
    wfShowStatus('保存失败: ' + e.message, 'error');
  }
}

async function wfDelete() {
  const id = _wfCurrentId || DOM['wf-id']?.value?.trim();
  if (!id) return;
  if (!await showConfirm(`删除 workflow「${id}」？此操作不可恢复。`, { title: '删除', okText: '删除', danger: true })) return;
  try {
    const r = await fetch(`/api/workflows/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '删除失败'));
    _wfCurrentId = null;
    _wfDirty = false;
    DOM['wf-editor']?.classList.add('hidden');
    DOM['wf-welcome']?.classList.remove('hidden');
    await wfLoadList();
    wfShowStatus('✓ 已删除', 'success');
    if (typeof window.refreshWorkflowSelect === 'function') window.refreshWorkflowSelect();
  } catch (e) {
    wfShowStatus('删除失败: ' + e.message, 'error');
  }
}

function wfShowStatus(msg, type) {
  if (msg) showToast(msg, type || 'info');
  const s = DOM['wf-status'];
  if (!s) return;
  s.textContent = msg;
  s.className = 'form-status' + (type ? ' ' + type : '');
  s.style.display = msg ? 'block' : 'none';
}

async function loadWorkflowTab() {
  const hadEditor = !DOM['wf-editor']?.classList.contains('hidden');
  const formSnapshot = hadEditor ? wfReadForm() : null;
  await wfLoadMeta();
  await wfLoadList();
  if (formSnapshot && formSnapshot.tasks.length) {
    wfCacheDescriptionsFromWorkflow(formSnapshot);
    wfSyncLoopSpecsFromWorkflow(formSnapshot);
    wfRenderTasks(formSnapshot.tasks);
  } else if (_wfCurrentId && _wfList.some(w => w.id === _wfCurrentId)) {
    await wfSelect(_wfCurrentId);
  }
}

window.refreshWorkflowSelect = wfLoadMeta;

function setupWorkflowTab() {
  if (!wfDom('wf-list')) {
    console.error('workflow tab DOM 未就绪');
    return;
  }
  const tab = wfDom('tab-workflows');
  if (tab && !tab.dataset.wfBound) {
    tab.dataset.wfBound = '1';
    tab.addEventListener('click', (e) => {
      if (e.target.closest('#wf-add-task')) {
        e.preventDefault();
        const tasks = wfReadForm().tasks;
        const prev = tasks.length ? tasks[tasks.length - 1].id : null;
        tasks.push({
          id: wfNextTaskId(tasks), name: '', agent: 'research',
          task_type: 'research',
          dependencies: prev ? [prev] : [],
          description: '',
        });
        wfRenderTasks(tasks);
        wfMarkDirty();
      }
    });
  }
  wfDom('wf-new')?.addEventListener('click', wfNew);
  wfDom('wf-save')?.addEventListener('click', wfSave);
  wfDom('wf-delete')?.addEventListener('click', wfDelete);
  wfDom('wf-suggest')?.addEventListener('click', wfSuggestTasks);
  ['wf-id', 'wf-version', 'wf-description', 'wf-max-parallel'].forEach(id => {
    wfDom(id)?.addEventListener('input', wfMarkDirty);
  });
  ['wf-review', 'wf-split', 'wf-parallel'].forEach(id => {
    wfDom(id)?.addEventListener('change', wfMarkDirty);
  });
}
