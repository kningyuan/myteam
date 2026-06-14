// ============ Dashboard ============

let _dashboardInflight = null;

function isHomeTabActive() {
  return document.getElementById('tab-home')?.classList.contains('active') === true;
}

/** 首页总览：仅依赖 /api/obs/summary，不阻塞于 backends/config */
async function renderDashboard() {
  const stats = DOM['home-stats'];
  const cards = DOM['home-projects'];
  if (!stats || !cards) return;
  if (!isHomeTabActive()) return;

  if (_dashboardInflight) {
    try { await _dashboardInflight; } catch (_) { /* 新一轮会重试 */ }
    if (!isHomeTabActive()) return;
  }

  const run = (async () => {
    const r = await fetch('/api/obs/summary');
    const d = await r.json();
    if (!r.ok) throw new Error(apiErr(d, `HTTP ${r.status}`));
    if (!isHomeTabActive()) return;

    let rate = 0;
    try { rate = await getPriceRate(); } catch (_) { rate = 0; }
    if (!isHomeTabActive()) return;

    const t = d.totals || {};
    stats.innerHTML = `
      <div class="stat-card"><div class="stat-num">${t.projects || 0}</div><div class="stat-lbl">项目总数</div></div>
      <div class="stat-card"><div class="stat-num stat-run">${t.running || 0}</div><div class="stat-lbl">运行中</div></div>
      <div class="stat-card"><div class="stat-num">${(t.tokens || 0).toLocaleString()}</div><div class="stat-lbl">总 Token</div></div>
      ${rate ? `<div class="stat-card"><div class="stat-num">¥${((t.tokens || 0) / 1e6 * rate).toFixed(2)}</div><div class="stat-lbl">预估成本</div></div>` : ''}`;
    const ps = d.projects || [];
    if (!ps.length) {
      cards.innerHTML = '<div class="empty-state-guide"><h3>欢迎使用 myteam Agent Team Workspace</h3><p>编排、协作、交付 — 一切尽在浏览器</p><div class="empty-state-actions"><button type="button" class="btn-primary" onclick="S.api.init()">初始化 Agent</button><button type="button" class="btn-secondary" onclick="S.api.runDemo()">运行 Demo</button><button type="button" class="btn-outline" onclick="S.ui.showNewProjectModal()">创建项目</button></div></div>';
      return;
    }
    cards.innerHTML = ps.map(p => {
      const pct = Math.round((p.progress || 0) * 100);
      const sl = PROJ_STATUS_LABEL[p.status] || p.status || '—';
      return `<div class="home-card clickable" data-pid="${esc(p.id)}">
        <div class="home-card-top"><span class="home-card-title">${esc(p.title || p.id)}</span><span class="status-chip s-${esc(p.status || '')}">${esc(sl)}</span></div>
        <div class="home-card-prog"><div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div><span>${pct}%</span></div>
        ${budgetBar(p.tokens || 0, p.budget, p.budget_ratio, p.budget_state)}
        <div class="home-card-foot">${p.task_count || 0} 任务 · ${(p.tokens || 0).toLocaleString()} tok${fmtYuan(p.tokens || 0, rate)}</div>
      </div>`;
    }).join('');
    cards.querySelectorAll('.home-card.clickable').forEach(el => {
      el.addEventListener('click', () => { switchTab('projects'); selectProject(el.dataset.pid); });
    });
  })();

  _dashboardInflight = run;
  try {
    await run;
  } catch (e) {
    if (isHomeTabActive()) {
      stats.innerHTML = '';
      cards.innerHTML = `<div class="empty">加载失败：${esc(e.message || e)}</div>`;
    }
  } finally {
    if (_dashboardInflight === run) _dashboardInflight = null;
  }
}

function ensureHomeDashboard() {
  if (isHomeTabActive() && typeof renderDashboard === 'function') void renderDashboard();
}

const HUB2_BANNER_KEY = 'myteam_hub2_banner_dismissed';

function initHub2Banner() {
  const banner = document.getElementById('hub2-upgrade-banner');
  const dismiss = document.getElementById('hub2-banner-dismiss');
  if (!banner) return;
  try {
    if (localStorage.getItem(HUB2_BANNER_KEY) === '1') return;
  } catch (_) { /* ignore */ }
  banner.classList.remove('hidden');
  dismiss?.addEventListener('click', () => {
    banner.classList.add('hidden');
    try { localStorage.setItem(HUB2_BANNER_KEY, '1'); } catch (_) { /* ignore */ }
  });
}
