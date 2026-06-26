import type { ProjectEvent } from "@/lib/api/projects"

const TL_META: Record<string, { label: string; color: string }> = {
  "project.created": { label: "项目创建", color: "#6366f1" },
  "project.completed": { label: "项目完成", color: "#22c55e" },
  "project.failed": { label: "项目失败", color: "#ef4444" },
  "project.task.updated": { label: "任务更新", color: "#3b82f6" },
  "project.task.blocked": { label: "任务阻塞", color: "#f59e0b" },
  "project.gate.completed": { label: "门禁通过", color: "#22c55e" },
  "project.gate.rejected": { label: "门禁拒绝", color: "#ef4444" },
  "project.deliverable.ready": { label: "交付物就绪", color: "#8b5cf6" },
  "chat.message.posted": { label: "聊天消息", color: "#06b6d4" },
  "budget.threshold.reached": { label: "预算告警", color: "#ef4444" },
  "project.cycle.completed": { label: "周期完成", color: "#22c55e" },
  "budget.threshold.exceeded": { label: "预算超限", color: "#dc2626" },
  "agent.error": { label: "Agent 异常", color: "#ef4444" },
  "project.plan.rejected": { label: "计划被拒", color: "#f97316" },
  "project.event": { label: "项目事件", color: "#94a3b8" },
}

export function mapEventsToTimeline(events: ProjectEvent[]) {
  return events.map((e) => ({
    type:
      e.kind === "gate_passed"
        ? "project.gate.completed"
        : e.kind === "gate_failed"
          ? "project.gate.rejected"
          : e.kind === "cycle_done"
            ? "project.cycle.completed"
            : e.kind === "message"
              ? "chat.message.posted"
              : e.kind === "budget_alert"
                ? "budget.threshold.reached"
                : e.kind === "budget_over"
                  ? "budget.threshold.exceeded"
                  : e.kind === "watchdog_hard_kill"
                    ? "agent.error"
                    : e.kind === "plan_rejected"
                      ? "project.plan.rejected"
                      : e.kind === "blocked"
                        ? "project.task.blocked"
                        : e.category === "interaction"
                          ? "project.task.updated"
                          : "project.event",
    timestamp: e.ts || "",
    payload: e.payload || {},
    metadata: { task_id: e.task_id, agent_id: e.agent_id, interaction_id: e.interaction_id },
  }))
}

function fmtTime(ts?: string) {
  if (!ts) return ""
  try {
    return new Date(ts).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return ts
  }
}

function dateLabel(ts?: string) {
  if (!ts) return ""
  try {
    const d = new Date(ts)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) return "今天"
    const y = new Date(today)
    y.setDate(today.getDate() - 1)
    if (d.toDateString() === y.toDateString()) return "昨天"
    return d.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" })
  } catch {
    return ""
  }
}

function summarize(type: string, payload: Record<string, unknown>, meta?: Record<string, unknown>) {
  if (type === "project.gate.rejected") {
    const f = payload.failures as string[] | undefined
    return `门禁拒绝：${(f || []).join(", ") || String(meta?.interaction_id || "")}`
  }
  if (type === "project.task.blocked") return `阻塞：${payload.reason || ""}`
  if (type === "chat.message.posted") {
    return `${payload.sender || payload.author || ""}: ${String(payload.text || "").slice(0, 80)}`
  }
  if (type === "budget.threshold.reached") return `预算告警`
  return JSON.stringify(payload).slice(0, 100)
}

export function ProjectTimeline({ events }: { events: ProjectEvent[] }) {
  const mapped = mapEventsToTimeline(events).sort((a, b) =>
    (a.timestamp || "").localeCompare(b.timestamp || ""),
  )

  if (!mapped.length) {
    return <div className="tl-empty">暂无时间线事件</div>
  }

  let lastDate = ""
  return (
    <div className="timeline-container">
      <div className="tl-list">
        {mapped.map((ev, i) => {
          const dl = dateLabel(ev.timestamp)
          const showDate = dl && dl !== lastDate
          if (showDate) lastDate = dl
          const meta = TL_META[ev.type] || { label: ev.type, color: "#94a3b8" }
          const isNew = i >= mapped.length - 5
          return (
            <div key={`${ev.timestamp}-${ev.type}-${i}`}>
              {showDate && <div className="tl-date-sep">{dl}</div>}
              <div className={cnItem(isNew)}>
                <div className="tl-line">
                  <div className="tl-dot" style={{ background: meta.color }} />
                  {i < mapped.length - 1 && <div className="tl-bar" />}
                </div>
                <div className="tl-body">
                  <div className="tl-header">
                    <span className="tl-badge" style={{ background: meta.color }}>
                      {meta.label}
                    </span>
                    <span className="tl-time">{fmtTime(ev.timestamp)}</span>
                  </div>
                  <div className="tl-summary">{summarize(ev.type, ev.payload, ev.metadata)}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function cnItem(isNew: boolean) {
  return `tl-item${isNew ? " tl-new" : ""}`
}
