// myteam DAG 图渲染器 — 纯 SVG，无外部依赖
// 使用：renderDAG(containerElement, tasksArray)
// tasksArray: [{task_id, name, status, dependencies, agent, token_used, duration_s}]
// 状态色：completed=#22c55e, running=#3b82f6, failed=#ef4444, blocked=#6b7280, pending=#93c5fd

const DAG_COLORS = {
  completed: '#22c55e', running: '#3b82f6', failed: '#ef4444',
  blocked: '#6b7280', pending: '#93c5fd', cancelled: '#a1a1aa',
};

const DAG_LABELS = {
  completed: '已完成', running: '运行中', failed: '失败',
  blocked: '阻塞', pending: '等待中', cancelled: '已取消',
};

function dagLayout(tasks) {
  if (!tasks || !tasks.length) return { nodes: [], edges: [], width: 400, height: 200 };

  // 拓扑排序确定层级
  const byId = {};
  tasks.forEach(t => { byId[t.id || t.task_id] = { ...t, deps: t.dependencies || [] }; });

  const level = {}, done = {};
  function assignLevel(id) {
    if (level[id] !== undefined) return level[id];
    const t = byId[id];
    if (!t || !t.deps.length) { level[id] = 0; return 0; }
    const pl = Math.max(...t.deps.map(d => {
      if (done[d]) return level[d] + 1;
      // 检查环
      return assignLevel(d) + 1;
    }), 0);
    level[id] = pl;
    done[id] = true;
    return pl;
  }
  tasks.forEach(t => { try { assignLevel(t.task_id); } catch(_) { level[t.task_id] = 0; } });

  // 按层级分组
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
      const x = startX + i * (NODE_W + H_GAP);
      nodes.push({ id, label: t.name || id, status: t.status, agent: t.agent,
        token: t.token_used, duration: t.duration_s, x, y, w: NODE_W, h: NODE_H });
      (t.deps || []).forEach(dep => {
        const src = nodes.find(n => n.id === dep);
        if (src) edges.push({ from: src, to: nodes[nodes.length - 1] });
      });
    });
  });

  return { nodes, edges, width, height };
}

function renderDAG(container, tasks) {
  if (!container) return;
  const { nodes, edges, width, height } = dagLayout(tasks);
  if (!nodes.length) { container.innerHTML = '<div class="dag-empty">暂无任务</div>'; return; }

  let svg = `<svg viewBox="0 0 ${width} ${height}" class="dag-svg" xmlns="http://www.w3.org/2000/svg">
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#94a3b8"/></marker></defs>`;

  // 边
  edges.forEach(e => {
    const x1 = e.from.x + e.from.w, y1 = e.from.y + e.from.h / 2;
    const x2 = e.to.x, y2 = e.to.y + e.to.h / 2;
    const cy = (y1 + y2) / 2;
    svg += `<path d="M${x1},${y1} Q${(x1+x2)/2},${y1} ${(x1+x2)/2},${cy} T${x2},${y2}" fill="none" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)"/>`;
  });

  // 节点
  nodes.forEach(n => {
    const color = DAG_COLORS[n.status] || '#94a3b8';
    const label = DAG_LABELS[n.status] || n.status;
    svg += `<g class="dag-node" data-id="${n.id}" style="cursor:pointer">
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="8" fill="${color}" opacity="0.9" stroke="${color}" stroke-width="2"/>
      <text x="${n.x + n.w/2}" y="${n.y + 18}" text-anchor="middle" fill="white" font-size="12" font-weight="600">${escHtml(n.label)}</text>
      <text x="${n.x + n.w/2}" y="${n.y + 34}" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-size="10">${label}${n.agent ? ' · ' + escHtml(n.agent) : ''}${n.token ? ' · ' + n.token + 'tok' : ''}</text>
    </g>`;
  });

  svg += '</svg>';
  container.innerHTML = svg;

  // 点击事件
  container.querySelectorAll('.dag-node').forEach(el => {
    el.addEventListener('click', () => {
      if (typeof window._onDagNodeClick === 'function') window._onDagNodeClick(el.dataset.id);
    });
  });
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}