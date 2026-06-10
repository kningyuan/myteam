// ============ Workflow 管理 ============
let _wfList = [];
let _wfCurrentId = null;
let _wfAgentRecords = [];
let _wfTaskTypeRecords = [];
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
      id: 't1',
      name: '调研',
      agent: 'research',
      task_type: 'research',
      dependencies: [],
      description: '【对象】目标 GitHub 仓库（链接见【项目目标】）\n【视角】\n【范围】仅 README、docs/',
    },
    {
      id: 't2',
      name: '汇总',
      agent: 'main',
      task_type: 'strategy',
      dependencies: ['t1'],
      description: '【输入】只读 t1 交付物',
    },
  ],
};

function wfEsc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
}

function wfMarkDirty() { _wfDirty = true; }

async function wfLoadMeta() {
  try {
    const [ra, rt, rr] = await Promise.all([
      fetch('/api/agents'),
      fetch('/api/task-types'),
      fetch('/api/agents/registry'),
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
  } catch (_) {
    _wfAgentRecords = [
      { id: 'main', name: '项目经理' },
      { id: 'product', name: '产品专家' },
      { id: 'research', name: '研究员' },
      { id: 'content', name: '内容专家' },
    ];
    _wfTaskTypeRecords = [
      { task_type: 'research', display_name: '调研 research' },
      { task_type: 'strategy', display_name: '策略分析 strategy' },
      { task_type: 'requirements', display_name: '需求 requirements' },
      { task_type: 'content', display_name: '内容 content' },
    ];
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
    return `<li class="wf-item${active}" data-id="${wfEsc(w.id)}"><span class="wf-item-id">${wfEsc(w.id)}</span><span class="wf-item-meta">${w.task_count || 0} 步</span>${err}</li>`;
  }).join('');
  ul.querySelectorAll('.wf-item').forEach(li => {
    li.addEventListener('click', () => wfSelect(li.dataset.id));
  });
}

function wfFillForm(data) {
  if (DOM['wf-id']) DOM['wf-id'].value = data.id || '';
  if (DOM['wf-version']) DOM['wf-version'].value = data.version || '1.0';
  if (DOM['wf-description']) DOM['wf-description'].value = data.description || '';
  const opt = data.options || {};
  if (DOM['wf-review']) DOM['wf-review'].checked = !!opt.review_enabled;
  if (DOM['wf-split']) DOM['wf-split'].checked = !!opt.split_enabled;
  if (DOM['wf-parallel']) DOM['wf-parallel'].checked = !!opt.parallel_enabled;
  if (DOM['wf-max-parallel']) DOM['wf-max-parallel'].value = opt.max_parallel ?? 3;
  wfRenderTasks(data.tasks || []);
  _wfDirty = false;
}

function wfReadForm() {
  const tasks = [];
  DOM['wf-tasks-body']?.querySelectorAll('tr[data-task-row]').forEach(tr => {
    const deps = (tr.querySelector('.wf-t-deps')?.value || '').split(/[,，\s]+/).map(s => s.trim()).filter(Boolean);
    tasks.push({
      id: tr.querySelector('.wf-t-id')?.value.trim() || '',
      name: tr.querySelector('.wf-t-name')?.value.trim() || '',
      agent: tr.querySelector('.wf-t-agent')?.value.trim() || '',
      task_type: tr.querySelector('.wf-t-type')?.value.trim() || 'research',
      dependencies: deps,
      description: tr.querySelector('.wf-t-desc')?.value || '',
    });
  });
  return {
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

function wfSyncTaskTypeSelect(tr) {
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
}

function wfMoveTask(idx, delta) {
  const tasks = wfReadForm().tasks;
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

function wfRenderTasks(tasks) {
  const body = DOM['wf-tasks-body'];
  if (!body) {
    console.error('workflow: #wf-tasks-body 未找到，请硬刷新页面');
    return;
  }
  const rows = tasks.length ? tasks : [{ id: '', name: '', agent: 'research', task_type: 'research', dependencies: [], description: '' }];
  body.innerHTML = rows
    .map((t, i) => `
    <tr data-task-row data-task-idx="${i}">
      <td class="wf-col-order">
        <div class="wf-order-btns">
          <button type="button" class="btn-xs primary wf-t-up" ${i === 0 ? 'disabled' : ''} title="上移" aria-label="上移">↑</button>
          <button type="button" class="btn-xs primary wf-t-down" ${i === rows.length - 1 ? 'disabled' : ''} title="下移" aria-label="下移">↓</button>
        </div>
      </td>
      <td><input class="wf-t-id wf-input-sm" value="${wfEsc(t.id)}" placeholder="t1"></td>
      <td><input class="wf-t-name wf-input-sm" value="${wfEsc(t.name)}" placeholder="任务名"></td>
      <td><select class="wf-t-agent wf-input-sm">${wfAgentOptions(t.agent)}</select></td>
      <td><div class="wf-type-cell"><select class="wf-t-type wf-input-sm">${wfTypeOptions(t.task_type, t.agent)}</select><small class="wf-cap-hint hint"></small></div></td>
      <td><input class="wf-t-deps wf-input-sm" value="${wfEsc((t.dependencies || []).join(', '))}" placeholder="t1, t2"></td>
      <td><textarea class="wf-t-desc" rows="2" placeholder="【对象】…">${wfEsc(t.description || '')}</textarea></td>
      <td><button type="button" class="btn-icon wf-t-del" title="删除" data-icon="trash"></button></td>
    </tr>`).join('');
  body.querySelectorAll('input,select,textarea').forEach(el => el.addEventListener('input', wfMarkDirty));
  body.querySelectorAll('tr[data-task-row]').forEach(tr => wfSyncTaskTypeSelect(tr));
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
      const tr = btn.closest('tr');
      const idx = parseInt(tr?.dataset.taskIdx, 10);
      if (!Number.isNaN(idx)) wfMoveTask(idx, -1);
    });
  });
  body.querySelectorAll('.wf-t-down').forEach(btn => {
    btn.addEventListener('click', () => {
      const tr = btn.closest('tr');
      const idx = parseInt(tr?.dataset.taskIdx, 10);
      if (!Number.isNaN(idx)) wfMoveTask(idx, 1);
    });
  });
  body.querySelectorAll('.wf-t-del').forEach(btn => {
    btn.addEventListener('click', () => {
      const tasksNow = wfReadForm().tasks;
      const tr = btn.closest('tr');
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
  const tasksSnapshot = hadEditor ? wfReadForm().tasks : null;
  await wfLoadMeta();
  await wfLoadList();
  if (tasksSnapshot && tasksSnapshot.length) {
    wfRenderTasks(tasksSnapshot);
  } else if (_wfCurrentId && _wfList.some(w => w.id === _wfCurrentId)) {
    await wfSelect(_wfCurrentId);
  }
}

function setupWorkflowTab() {
  if (!DOM['wf-list']) {
    console.error('workflow tab DOM 未就绪');
    return;
  }
  DOM['wf-new']?.addEventListener('click', wfNew);
  DOM['wf-save']?.addEventListener('click', wfSave);
  DOM['wf-delete']?.addEventListener('click', wfDelete);
  DOM['wf-suggest']?.addEventListener('click', wfSuggestTasks);
  DOM['wf-add-task']?.addEventListener('click', () => {
    const tasks = wfReadForm().tasks;
    tasks.push({ id: `t${tasks.length + 1}`, name: '', agent: 'research', task_type: 'research', dependencies: [], description: '' });
    wfRenderTasks(tasks);
    wfMarkDirty();
  });
  ['wf-id', 'wf-version', 'wf-description', 'wf-max-parallel'].forEach(id => {
    DOM[id]?.addEventListener('input', wfMarkDirty);
  });
  ['wf-review', 'wf-split', 'wf-parallel'].forEach(id => {
    DOM[id]?.addEventListener('change', wfMarkDirty);
  });
}
