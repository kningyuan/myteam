// ============ Settings ============
let _settingsCfg = {};
const CLI_PATH_LABELS = { opencode: 'OpenCode CLI 路径', claude: 'Claude CLI 路径' };

function updateSettingsCliPath(backendId) {
  const label = DOM['set-cli-path-label']; const hint = DOM['set-cli-path-hint']; const input = DOM['set-cli-path'];
  if (label) label.textContent = CLI_PATH_LABELS[backendId] || `${backendId} CLI 路径`;
  if (input) { input.value = _settingsCfg.backends?.[backendId]?.cli_path || ''; input.placeholder = backendId === 'claude' ? '留空则从 PATH 检测 claude' : '留空则自动检测'; }
  if (hint) { hint.textContent = backendId === 'opencode' ? 'OpenCode 可执行文件；模型别名仅作用于 OpenCode' : 'Claude Code 可执行文件；留空则依次尝试配置路径、CLAUDE_CLI_PATH、PATH'; }
}

async function loadSettings() {
  await loadBackends();
  try {
    const [rSys, rSkill] = await Promise.all([fetch('/api/config'), fetch('/api/skill-config')]);
    const cfg = (await rSys.json()).config || {}; _settingsCfg = cfg;
    const skillCfg = (await rSkill.json()).config || {};
    const defBackend = cfg.system?.default_backend || 'opencode';
    const bSel = DOM['set-default-backend'];
    bSel.innerHTML = S.backends.map(b => `<option value="${b.id}" ${b.id === defBackend ? 'selected' : ''}>${b.name}</option>`).join('');
    const defModel = cfg.system?.default_model || '';
  // 首屏用 /api/backends 已缓存的模型，避免每次打开设置都 refresh CLI（OpenCode 要数秒）
    await refreshSettingsModelSelect(defBackend, defModel, { refresh: false });
    bSel.onchange = () => onSettingsBackendChange(bSel.value);
    updateSettingsCliPath(defBackend);
    DOM['set-port'].value = cfg.system?.port || 8765;
    DOM['set-debug'].checked = !!cfg.system?.debug;
    DOM['set-audit-log'].checked = !!cfg.system?.audit_log;
    DOM['set-audit-log-max-bytes'].value = cfg.system?.audit_log_max_bytes ?? 500000;
    DOM['set-price'].value = cfg.system?.price_per_mtok ?? '';
    DOM['set-default-review'].checked = !!cfg.system?.default_review;
    DOM['set-model-aliases'].value = JSON.stringify(cfg.backends?.opencode?.model_aliases || {}, null, 2);
    DOM['set-use-project-group'].checked = skillCfg.notifications?.use_project_group !== false;
    DOM['set-enable-telegram'].checked = skillCfg.notifications?.enable_telegram !== false;
    DOM['set-auto-group'].checked = skillCfg.auto_group?.enabled !== false;
    DOM['set-auto-group-include-main'].checked = skillCfg.auto_group?.include_main !== false;
    DOM['set-auto-group-name-prefix'].value = skillCfg.auto_group?.name_prefix || '';
    DOM['set-hub-url'].value = skillCfg.hub?.url || 'http://127.0.0.1:8765';
    DOM['set-poll-interval'].value = skillCfg.executor?.poll_interval ?? 5;
    DOM['set-ack-timeout'].value = skillCfg.executor?.ack_timeout ?? 300;
    DOM['set-task-timeout'].value = skillCfg.executor?.task_timeout ?? 3600;
    DOM['set-agent-msg-timeout'].value = skillCfg.executor?.agent_msg_timeout ?? 1800;
    DOM['set-team-config-timeout'].value = skillCfg.executor?.team_config_timeout ?? 600;
    DOM['set-task-plan-timeout'].value = skillCfg.executor?.task_plan_timeout ?? 600;
    DOM['set-max-retries'].value = skillCfg.executor?.max_retries ?? 3;
    const pd = skillCfg.process_defaults || {};
    if (DOM['set-default-budget']) DOM['set-default-budget'].value = pd.default_project_budget ?? 1000000;
    if (DOM['set-max-gate-retries']) DOM['set-max-gate-retries'].value = pd.max_gate_retries ?? 5;
    if (DOM['set-soft-idle']) DOM['set-soft-idle'].value = pd.soft_idle_sec ?? 240;
    if (DOM['set-hard-idle']) DOM['set-hard-idle'].value = pd.hard_idle_sec ?? 900;
    if (DOM['set-max-cycles']) DOM['set-max-cycles'].value = pd.max_cycles ?? 3;
    if (DOM['set-split-default']) DOM['set-split-default'].checked = !!pd.split_enabled;
    if (DOM['set-parallel-default']) DOM['set-parallel-default'].checked = !!pd.parallel_enabled;
    if (DOM['set-max-parallel']) DOM['set-max-parallel'].value = pd.max_parallel ?? 3;
    if (DOM['set-max-concurrent-projects']) DOM['set-max-concurrent-projects'].value = pd.max_concurrent_projects ?? 2;
    const degThr = pd.budget_degrade_threshold ?? 0.8;
    if (DOM['set-budget-degrade-threshold']) {
      DOM['set-budget-degrade-threshold'].value = Math.round(degThr * 100);
    }
    const degBackend = pd.budget_degrade_backend || '';
    updateSettingsDegradeBackendSelect(degBackend);
    const degBSel = DOM['set-budget-degrade-backend'];
    if (degBSel) {
      degBSel.onchange = () => refreshSettingsDegradeModel(degBSel.value, '', { refresh: true });
      await refreshSettingsDegradeModel(degBackend, pd.budget_degrade_model || '', { refresh: false });
    }
  } catch(e) { showSetStatus('加载配置失败: '+e.message, 'error'); }
}

function updateDefaultModelSelect(backendId, selected) {
  const models = getBackendModels(backendId);
  const mSel = DOM['set-default-model'];
  if (!mSel) return;
  if (!models.length) {
    // 模型列表拉取失败时仍保留已保存的 default_model，避免「应用到全部」无法点击
    if (selected) {
      mSel.innerHTML = `<option value="${esc(selected)}" selected>${esc(selected)}</option>`;
      return;
    }
    mSel.innerHTML = '<option value="">（无可用模型）</option>';
    return;
  }
  mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`).join('');
}

function setModelSelectLoading(loading) {
  const mSel = DOM['set-default-model'];
  if (!mSel) return;
  mSel.disabled = loading;
  if (loading) mSel.innerHTML = '<option value="">加载模型中…</option>';
}

async function refreshSettingsModelSelect(backendId, selected, { refresh = true } = {}) {
  setModelSelectLoading(true);
  try {
    await loadBackendModels(backendId, { refresh });
    updateDefaultModelSelect(backendId, selected);
  } catch (e) {
    updateDefaultModelSelect(backendId, selected);
    showSetStatus('模型列表加载失败: ' + e.message, 'error');
  } finally {
    setModelSelectLoading(false);
  }
}

async function onSettingsBackendChange(backendId) {
  updateSettingsCliPath(backendId);
  const prev = DOM['set-default-model']?.value || '';
  await refreshSettingsModelSelect(backendId, prev, { refresh: true });
}

function updateSettingsDegradeBackendSelect(selected) {
  const bSel = DOM['set-budget-degrade-backend'];
  if (!bSel) return;
  const opts = ['<option value="">（不修改 backend）</option>'];
  opts.push(...S.backends.map(b =>
    `<option value="${b.id}" ${b.id === selected ? 'selected' : ''}>${b.name}</option>`));
  bSel.innerHTML = opts.join('');
}

async function refreshSettingsDegradeModel(backendId, selected, { refresh = false } = {}) {
  const mSel = DOM['set-budget-degrade-model'];
  if (!mSel) return;
  if (!backendId) {
    mSel.disabled = true;
    mSel.innerHTML = '<option value="">（先选降级 backend）</option>';
    return;
  }
  mSel.disabled = false;
  try {
    await loadBackendModels(backendId, { refresh });
  } catch (_) { /* 保留已有列表 */ }
  const models = getBackendModels(backendId);
  if (!models.length) {
    mSel.innerHTML = '<option value="">（无可用模型）</option>';
    return;
  }
  mSel.innerHTML = ['<option value="">（不修改 model）</option>',
    ...models.map(m => `<option value="${m.id}" ${m.id === selected ? 'selected' : ''}>${m.name}</option>`),
  ].join('');
}

async function applyModelToAll() {
  const backend = DOM['set-default-backend'].value; const model = DOM['set-default-model'].value;
  if (!model) { showSetStatus('请先选择模型', 'error'); return; }
  if (!await showConfirm(`将全部 agent 的后端改为「${backend}」，模型改为：\n${model}`, {title:'批量应用模型', okText:'应用'})) return;
  try {
    const r = await fetch('/api/agents/apply-model', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ backend, model }) });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '应用失败'));
    if (!d.applied?.length) throw new Error('没有可更新的 agent（请确认已创建 agent workspace）');
    const mig = (d.migrated || []).length;
    const extra = mig ? `，其中 ${mig} 个已切换后端` : '';
    showSetStatus(`✓ 已应用到 ${d.applied.length} 个 agent${extra}`, 'success');
  } catch(e) { showSetStatus('应用失败: '+e.message, 'error'); }
}

async function saveSettings() {
  const backend = DOM['set-default-backend'].value; const model = DOM['set-default-model'].value;
  const port = parseInt(DOM['set-port'].value) || 8765;
  const cliPath = (DOM['set-cli-path']?.value || '').trim();
  let aliases = {};
  try { aliases = JSON.parse(DOM['set-model-aliases'].value || '{}'); } catch(e) { showSetStatus('模型别名 JSON 格式错误', 'error'); return; }
  try {
    const r0 = await fetch('/api/config'); const cfg = (await r0.json()).config || {};
    cfg.system = cfg.system || {}; cfg.system.default_backend = backend; cfg.system.default_model = model; cfg.system.port = port;
    cfg.system.debug = !!DOM['set-debug']?.checked; cfg.system.audit_log = !!DOM['set-audit-log']?.checked;
    cfg.system.audit_log_max_bytes = parseInt(DOM['set-audit-log-max-bytes']?.value, 10) || 500000;
    cfg.system.price_per_mtok = Number(DOM['set-price']?.value) || 0; cfg.system.default_review = !!DOM['set-default-review']?.checked;
    cfg.backends = cfg.backends || {}; cfg.backends[backend] = cfg.backends[backend] || {}; cfg.backends[backend].cli_path = cliPath;
    if (backend === 'opencode') cfg.backends.opencode.model_aliases = aliases;
    const rSkill0 = await fetch('/api/skill-config'); const existingSkill = (await rSkill0.json()).config || {};
    const skillCfg = {
      ...existingSkill, notifications: { ...(existingSkill.notifications || {}), enable_telegram: DOM['set-enable-telegram']?.checked !== false, use_project_group: DOM['set-use-project-group']?.checked !== false },
      hub: { ...(existingSkill.hub || {}), url: (DOM['set-hub-url']?.value || '').trim() || 'http://127.0.0.1:8765' },
      executor: { ...(existingSkill.executor || {}), poll_interval: parseInt(DOM['set-poll-interval']?.value) || 5, ack_timeout: parseInt(DOM['set-ack-timeout']?.value) || 300, task_timeout: parseInt(DOM['set-task-timeout']?.value) || 3600, agent_msg_timeout: parseInt(DOM['set-agent-msg-timeout']?.value) || 1800, team_config_timeout: parseInt(DOM['set-team-config-timeout']?.value) || 600, task_plan_timeout: parseInt(DOM['set-task-plan-timeout']?.value) || 600, max_retries: parseInt(DOM['set-max-retries']?.value) || 3 },
      auto_group: { ...(existingSkill.auto_group || {}), enabled: DOM['set-auto-group']?.checked !== false, include_main: DOM['set-auto-group-include-main']?.checked !== false, name_prefix: (DOM['set-auto-group-name-prefix']?.value || '').trim() },
      process_defaults: (() => {
        const thrPct = parseFloat(DOM['set-budget-degrade-threshold']?.value);
        const thr = (!Number.isNaN(thrPct) && thrPct > 0 && thrPct < 100) ? thrPct / 100 : 0.8;
        return {
          max_gate_retries: parseInt(DOM['set-max-gate-retries']?.value, 10) || 5,
          split_enabled: !!DOM['set-split-default']?.checked,
          soft_idle_sec: parseInt(DOM['set-soft-idle']?.value, 10) || 240,
          hard_idle_sec: parseInt(DOM['set-hard-idle']?.value, 10) || 900,
          max_cycles: parseInt(DOM['set-max-cycles']?.value, 10) || 3,
          parallel_enabled: !!DOM['set-parallel-default']?.checked,
          max_parallel: parseInt(DOM['set-max-parallel']?.value, 10) || 3,
          max_concurrent_projects: parseInt(DOM['set-max-concurrent-projects']?.value, 10) || 2,
          default_project_budget: parseInt(DOM['set-default-budget']?.value, 10) || 1000000,
          budget_degrade_threshold: thr,
          budget_degrade_backend: (DOM['set-budget-degrade-backend']?.value || '').trim(),
          budget_degrade_model: (DOM['set-budget-degrade-model']?.value || '').trim(),
        };
      })(),
    };
    const [rSys, rSkill] = await Promise.all([
      fetch('/api/config', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ config: cfg }) }),
      fetch('/api/skill-config', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ config: skillCfg }) }),
    ]);
    if (!rSys.ok || !rSkill.ok) throw new Error('保存失败');
    _sysCfg = null; _settingsCfg = cfg;
    showSetStatus('✓ 已保存（端口变更需重启 Hub）', 'success');
  } catch(e) { showSetStatus('保存失败: '+e.message, 'error'); }
}

function showSetStatus(msg, type) {
  if (msg) showToast(msg, type || 'info');
  const s = DOM['set-status']; if (!s) return;
  s.textContent = msg; s.className = 'form-status';
  if (msg) { s.style.display = 'block'; if (type) s.classList.add(type); } else s.style.display = 'none';
}