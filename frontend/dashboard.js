// ============ Dashboard ============

async function renderDashboard() {
  const stats = DOM['home-stats'], cards = DOM['home-projects'];
  if (!stats || !cards) return;
  const rate = await getPriceRate();
  try {
    const d = await (await fetch('/api/obs/summary')).json();
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
    cards.querySelectorAll('.home-card.clickable').forEach(el => { el.addEventListener('click', () => { switchTab('projects'); selectProject(el.dataset.pid); }); });
  } catch (e) { cards.innerHTML = `<div class="empty">加载失败：${esc(e.message || e)}</div>`; }
}