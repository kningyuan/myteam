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
    updateDefaultModelSelect(defBackend, defModel);
    bSel.onchange = () => { updateDefaultModelSelect(bSel.value); updateSettingsCliPath(bSel.value); };
    updateSettingsCliPath(defBackend);
    DOM['set-port'].value = cfg.system?.port || 8765;
    DOM['set-debug'].checked = !!cfg.system?.debug;
    DOM['set-audit-log'].checked = !!cfg.system?.audit_log;
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
  mSel.innerHTML = models.map(m => `<option value="${m.id}" ${m.id === selected || (!selected && m.default) ? 'selected' : ''}>${m.name}</option>`).join('');
}

async function applyModelToAll() {
  const backend = DOM['set-default-backend'].value; const model = DOM['set-default-model'].value;
  if (!model) { showSetStatus('请先选择模型', 'error'); return; }
  if (!await showConfirm(`把后端「${backend}」下的所有 agent 模型都改成：\n${model}\n（其它后端的 agent 不受影响）`, {title:'批量应用模型', okText:'应用'})) return;
  try {
    const r = await fetch('/api/agents/apply-model', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ backend, model }) });
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, '应用失败'));
    showSetStatus(`✓ 已应用到 ${d.applied.length} 个 agent，跳过 ${d.skipped.length} 个（非 ${backend}）`, 'success');
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
    cfg.system.price_per_mtok = Number(DOM['set-price']?.value) || 0; cfg.system.default_review = !!DOM['set-default-review']?.checked;
    cfg.backends = cfg.backends || {}; cfg.backends[backend] = cfg.backends[backend] || {}; cfg.backends[backend].cli_path = cliPath;
    if (backend === 'opencode') cfg.backends.opencode.model_aliases = aliases;
    const allModels = getBackendModels(backend); cfg.models = cfg.models || {};
    cfg.models[backend] = allModels.map(m => ({ id: m.id, name: m.name, provider: m.provider, default: m.id === model }));
    const rSkill0 = await fetch('/api/skill-config'); const existingSkill = (await rSkill0.json()).config || {};
    const skillCfg = {
      ...existingSkill, notifications: { ...(existingSkill.notifications || {}), enable_telegram: false, use_project_group: DOM['set-use-project-group']?.checked !== false },
      hub: { ...(existingSkill.hub || {}), url: (DOM['set-hub-url']?.value || '').trim() || 'http://127.0.0.1:8765' },
      executor: { ...(existingSkill.executor || {}), poll_interval: parseInt(DOM['set-poll-interval']?.value) || 5, ack_timeout: parseInt(DOM['set-ack-timeout']?.value) || 300, task_timeout: parseInt(DOM['set-task-timeout']?.value) || 3600, agent_msg_timeout: parseInt(DOM['set-agent-msg-timeout']?.value) || 1800, team_config_timeout: parseInt(DOM['set-team-config-timeout']?.value) || 600, task_plan_timeout: parseInt(DOM['set-task-plan-timeout']?.value) || 600, max_retries: parseInt(DOM['set-max-retries']?.value) || 3 },
      auto_group: { ...(existingSkill.auto_group || {}), enabled: DOM['set-auto-group']?.checked !== false, include_main: existingSkill.auto_group?.include_main !== false, name_prefix: existingSkill.auto_group?.name_prefix ?? '' },
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