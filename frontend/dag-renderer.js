// myteam DAG 图渲染器 — 纯 SVG，无外部依赖
// 使用：renderDAG(containerElement, tasksArray, selectedId?)
// tasksArray: [{id, name, status, dependencies, agent, token, summary}]

const DAG_COLORS = {
  completed: 'var(--status-completed, #22c55e)',
  running: 'var(--status-running, #3b82f6)',
  failed: 'var(--status-failed, #ef4444)',
  blocked: 'var(--status-blocked, #6b7280)',
  pending: 'var(--status-pending, #93c5fd)',
  cancelled: 'var(--status-cancelled, #a1a1aa)',
};

const DAG_LABELS = {
  completed: '已完成', running: '运行中', failed: '失败',
  blocked: '阻塞', pending: '等待中', cancelled: '已取消',
};

const DAG_SCALE_MIN = 0.35;
const DAG_SCALE_MAX = 2.5;

function dagLayout(tasks) {
  if (!tasks || !tasks.length) return { nodes: [], edges: [], width: 400, height: 200 };

  const byId = {};
  tasks.forEach(t => { byId[t.id || t.task_id] = { ...t, deps: t.dependencies || [] }; });

  const level = {}, done = {};
  function assignLevel(id) {
    if (level[id] !== undefined) return level[id];
    const t = byId[id];
    if (!t || !t.deps.length) { level[id] = 0; return 0; }
    const pl = Math.max(...t.deps.map(d => {
      if (done[d]) return level[d] + 1;
      return assignLevel(d) + 1;
    }), 0);
    level[id] = pl;
    done[id] = true;
    return pl;
  }
  tasks.forEach(t => {
    const tid = t.id || t.task_id;
    try { assignLevel(tid); } catch (_) { level[tid] = 0; }
  });

  const layers = {};
  Object.entries(level).forEach(([id, lv]) => {
    if (!layers[lv]) layers[lv] = [];
    layers[lv].push(id);
  });

  const NODE_W = 160, NODE_H = 44, H_GAP = 30, V_GAP = 60, PAD = 20;
  const maxCols = Math.max(...Object.values(layers).map(a => a.length), 1);
  const width = maxCols * (NODE_W + H_GAP) + PAD;
  const height = Object.keys(layers).length * (NODE_H + V_GAP) + PAD;

  const nodes = [], edges = [];
  Object.entries(layers).sort((a, b) => Number(a[0]) - Number(b[0])).forEach(([lv, ids]) => {
    const y = PAD + Number(lv) * (NODE_H + V_GAP);
    const totalW = ids.length * (NODE_W + H_GAP) - H_GAP;
    const startX = (width - totalW) / 2;
    ids.forEach((id, i) => {
      const t = byId[id];
      if (!t) return;
      const x = startX + i * (NODE_W + H_GAP);
      nodes.push({ id, label: t.name || id, status: t.status, agent: t.agent,
        token: t.token, x, y, w: NODE_W, h: NODE_H });
      (t.deps || []).forEach(dep => {
        const src = nodes.find(n => n.id === dep);
        if (src) edges.push({ from: src, to: nodes[nodes.length - 1] });
      });
    });
  });

  return { nodes, edges, width, height };
}

function dagTruncate(s, max = 20) {
  const t = String(s || '');
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

function buildDagSvg(nodes, edges, width, height) {
  const markerId = `dag-arrow-${Math.random().toString(36).slice(2, 9)}`;
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" class="dag-svg" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="任务依赖图">
    <defs><marker id="${markerId}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--text-tertiary, #94a3b8)"/></marker></defs>`;

  edges.forEach(e => {
    const x1 = e.from.x + e.from.w, y1 = e.from.y + e.from.h / 2;
    const x2 = e.to.x, y2 = e.to.y + e.to.h / 2;
    const cy = (y1 + y2) / 2;
    svg += `<path class="dag-edge" d="M${x1},${y1} Q${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${cy} T${x2},${y2}" fill="none" stroke="var(--text-tertiary, #94a3b8)" stroke-width="1.5" marker-end="url(#${markerId})"/>`;
  });

  nodes.forEach(n => {
    const color = DAG_COLORS[n.status] || 'var(--text-tertiary, #94a3b8)';
    const label = DAG_LABELS[n.status] || n.status;
    const meta = `${label}${n.agent ? ' · ' + n.agent : ''}${n.token ? ' · ' + n.token + ' tok' : ''}`;
    const st = escHtml(n.status || 'pending');
    svg += `<g class="dag-node status-${st}" data-id="${escHtml(n.id)}" tabindex="0" role="button" aria-label="${escHtml(n.label)} · ${escHtml(meta)}">
      <rect class="dag-node-bg" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="8" fill="${color}" stroke="${color}" stroke-width="2"/>
      <title>${escHtml(n.label)} · ${escHtml(meta)}</title>
      <text class="dag-node-label" x="${n.x + n.w / 2}" y="${n.y + 18}" text-anchor="middle" fill="white" font-size="12" font-weight="600">${escHtml(dagTruncate(n.label))}</text>
      <text class="dag-node-meta" x="${n.x + n.w / 2}" y="${n.y + 34}" text-anchor="middle" fill="rgba(255,255,255,0.85)" font-size="10">${escHtml(dagTruncate(meta, 28))}</text>
    </g>`;
  });

  svg += '</svg>';
  return svg;
}

function applyDagTransform(container) {
  const stage = container.querySelector('.dag-stage');
  const label = container.querySelector('.dag-zoom-label');
  if (!stage) return;
  const scale = Number(container.dataset.dagScale) || 1;
  const panX = Number(container.dataset.dagPanX) || 0;
  const panY = Number(container.dataset.dagPanY) || 0;
  stage.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  if (label) label.textContent = `${Math.round(scale * 100)}%`;
}

function setDagScale(container, scale) {
  const next = Math.min(DAG_SCALE_MAX, Math.max(DAG_SCALE_MIN, scale));
  container.dataset.dagScale = String(next);
  applyDagTransform(container);
}

function dagZoomFit(container, contentW, contentH) {
  const wrap = container.querySelector('.dag-stage-wrap');
  if (!wrap || !contentW || !contentH) return;
  const pad = 20;
  const sx = (wrap.clientWidth - pad) / contentW;
  const sy = (wrap.clientHeight - pad) / contentH;
  const scale = Math.min(1.25, Math.max(DAG_SCALE_MIN, Math.min(sx, sy)));
  container.dataset.dagScale = String(scale);
  container.dataset.dagPanX = String(Math.max(8, (wrap.clientWidth - contentW * scale) / 2));
  container.dataset.dagPanY = String(Math.max(8, (wrap.clientHeight - contentH * scale) / 2));
  applyDagTransform(container);
}

function resetDagView(container, contentW, contentH) {
  delete container.dataset.dagScale;
  delete container.dataset.dagPanX;
  delete container.dataset.dagPanY;
  requestAnimationFrame(() => dagZoomFit(container, contentW, contentH));
}

function bindDagPanZoom(container, contentW, contentH) {
  const wrap = container.querySelector('.dag-stage-wrap');
  if (!wrap) return;

  container.querySelector('.dag-zoom-in')?.addEventListener('click', () => {
    setDagScale(container, (Number(container.dataset.dagScale) || 1) + 0.15);
  });
  container.querySelector('.dag-zoom-out')?.addEventListener('click', () => {
    setDagScale(container, (Number(container.dataset.dagScale) || 1) - 0.15);
  });
  container.querySelector('.dag-zoom-reset')?.addEventListener('click', () => {
    container.dataset.dagScale = '1';
    container.dataset.dagPanX = '12';
    container.dataset.dagPanY = '12';
    applyDagTransform(container);
  });
  container.querySelector('.dag-zoom-fit')?.addEventListener('click', () => {
    dagZoomFit(container, contentW, contentH);
  });

  if (!container.dataset.dagScale) {
    requestAnimationFrame(() => dagZoomFit(container, contentW, contentH));
  } else {
    applyDagTransform(container);
  }

  if (container._dagPanSetup) return;
  container._dagPanSetup = true;

  const state = { dragging: false, startX: 0, startY: 0, startPanX: 0, startPanY: 0 };

  container.addEventListener('mousedown', e => {
    const w = container.querySelector('.dag-stage-wrap');
    if (!w || e.button !== 0 || !w.contains(e.target) || e.target.closest('.dag-node')) return;
    state.dragging = true;
    state.startX = e.clientX;
    state.startY = e.clientY;
    state.startPanX = Number(container.dataset.dagPanX) || 0;
    state.startPanY = Number(container.dataset.dagPanY) || 0;
    w.classList.add('dag-panning');
  });

  window.addEventListener('mousemove', e => {
    if (!state.dragging) return;
    container.dataset.dagPanX = String(state.startPanX + (e.clientX - state.startX));
    container.dataset.dagPanY = String(state.startPanY + (e.clientY - state.startY));
    applyDagTransform(container);
  });

  window.addEventListener('mouseup', () => {
    if (!state.dragging) return;
    state.dragging = false;
    container.querySelector('.dag-stage-wrap')?.classList.remove('dag-panning');
  });

  container.addEventListener('wheel', e => {
    const w = container.querySelector('.dag-stage-wrap');
    if (!w || !w.contains(e.target)) return;
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setDagScale(container, (Number(container.dataset.dagScale) || 1) + delta);
  }, { passive: false });
}

function renderDAG(container, tasks, selectedId) {
  if (!container) return;
  const { nodes, edges, width, height } = dagLayout(tasks);
  if (!nodes.length) {
    container.innerHTML = '<div class="dag-empty">暂无任务</div>';
    delete container._dagPanSetup;
    return;
  }

  const svg = buildDagSvg(nodes, edges, width, height);
  container.innerHTML = `
    <div class="dag-toolbar">
      <button type="button" class="btn-xs primary dag-zoom-in" aria-label="放大">+</button>
      <button type="button" class="btn-xs primary dag-zoom-out" aria-label="缩小">−</button>
      <button type="button" class="btn-xs primary dag-zoom-reset" aria-label="重置缩放">1:1</button>
      <button type="button" class="btn-xs primary dag-zoom-fit" aria-label="适应窗口">适应</button>
      <span class="dag-zoom-label">100%</span>
    </div>
    <div class="dag-stage-wrap">
      <div class="dag-stage">${svg}</div>
    </div>`;

  container.querySelectorAll('.dag-node').forEach(el => {
    el.classList.toggle('dag-selected', !!(selectedId && el.dataset.id === selectedId));
    const activate = () => {
      if (typeof window._onDagNodeClick === 'function') window._onDagNodeClick(el.dataset.id);
    };
    el.addEventListener('click', e => { e.stopPropagation(); activate(); });
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
    });
  });

  bindDagPanZoom(container, width, height);
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
