// myteam 时间线渲染器 — 基于 WorkspaceEvent 的统一事件视图
// 使用：renderTimeline(containerElement, eventsArray)
// eventsArray: [{id, type, source, payload, timestamp, metadata}]
// 类型映射用于中文标签和图标

const TL_TYPE_META = {
  'project.created':         { label: '项目创建', color: '#6366f1' },
  'project.completed':       { label: '项目完成', color: '#22c55e' },
  'project.failed':          { label: '项目失败', color: '#ef4444' },
  'project.task.updated':    { label: '任务更新', color: '#3b82f6' },
  'project.task.blocked':    { label: '任务阻塞', color: '#f59e0b' },
  'project.gate.completed':  { label: '门禁通过', color: '#22c55e' },
  'project.gate.rejected':   { label: '门禁拒绝', color: '#ef4444' },
  'project.deliverable.ready': { label: '交付物就绪', color: '#8b5cf6' },
  'project.triage.requested':  { label: '升级处理', color: '#f97316' },
  'chat.message.posted':     { label: '聊天消息', color: '#06b6d4' },
  'budget.threshold.reached': { label: '预算告警', color: '#ef4444' },
  'agent.status.changed':    { label: 'Agent 状态', color: '#64748b' },
};

function formatTime(ts) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch(_) { return ts; }
}

function tlTypeMeta(type) {
  return TL_TYPE_META[type] || { label: type || '事件', color: '#94a3b8' };
}

function renderTimeline(container, events) {
  if (!container) return;
  if (!events || !events.length) {
    container.innerHTML = '<div class="tl-empty">暂无事件</div>';
    return;
  }

  // 按时间升序
  const sorted = [...events].sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));

  let html = '<div class="tl-list">';
  sorted.forEach((ev, i) => {
    const meta = tlTypeMeta(ev.type);
    const payload = typeof ev.payload === 'string' ? tryJson(ev.payload) : (ev.payload || {});
    const time = formatTime(ev.timestamp);
    const isNew = i > sorted.length - 5; // 最近 5 条 "新" 高亮

    html += `<div class="tl-item${isNew ? ' tl-new' : ''}">
      <div class="tl-line"><div class="tl-dot" style="background:${meta.color}"></div>${i < sorted.length - 1 ? '<div class="tl-bar"></div>' : ''}</div>
      <div class="tl-body">
        <div class="tl-header"><span class="tl-badge" style="background:${meta.color}">${meta.label}</span><span class="tl-time">${time}</span></div>
        <div class="tl-summary">${summarizeEvent(ev, payload)}</div>
      </div>
    </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

function summarizeEvent(ev, payload) {
  const type = ev.type || '';
  if (type === 'project.task.updated') {
    const s = payload.status || '';
    return `任务 ${escHtml(ev.metadata?.task_id || payload.interaction_id || '')} ${statusLabel(s)}`;
  }
  if (type === 'project.gate.completed') return `门禁校验通过：${escHtml(payload.interaction_id || '')}`;
  if (type === 'project.gate.rejected') return `门禁校验拒绝：${escHtml((payload.failures || []).join(', ') || payload.interaction_id || '')}`;
  if (type === 'project.task.blocked') return `任务阻塞：${escHtml(payload.reason || '')}`;
  if (type === 'project.deliverable.ready') return `交付物已就绪`;
  if (type === 'budget.threshold.reached') return `预算${payload.alert === 'over' ? '超支' : '告警'}：已用 ${payload.used_pct || 0}%`;
  if (type === 'chat.message.posted') return `${escHtml(payload.author || '')}: ${escHtml((payload.text || '').slice(0, 80))}`;
  if (type === 'project.created') return `项目创建`;
  if (type === 'project.completed') return `项目完成`;
  if (type === 'project.failed') return `项目失败`;
  return escHtml(JSON.stringify(payload).slice(0, 80));
}

function statusLabel(s) {
  const map = { running: '开始运行', completed: '已完成', failed: '失败', blocked: '已阻塞', awaiting_gate: '等待门禁', resumed: '已续跑', review_done: '评审完成' };
  return map[s] || s || '';
}

function tryJson(s) {
  try { return JSON.parse(s); } catch(_) { return {}; }
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}