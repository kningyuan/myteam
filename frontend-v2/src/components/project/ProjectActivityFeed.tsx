import type { ProjectEvent } from "@/lib/api/projects"
import { EVENT_LABELS, eventDetail, fmtExecTs, truncateText } from "@/lib/project-labels"

/** 项目级动态：消息、门禁、预算等，不属于交互步骤本身。 */
export function ProjectActivityFeed({ events }: { events: ProjectEvent[] }) {
  const sorted = [...events].sort((a, b) => (a.ts || "").localeCompare(b.ts || ""))

  if (!sorted.length) {
    return <p className="hint exec-activity-empty">暂无项目动态</p>
  }

  return (
    <div className="exec-activity-feed">
      {sorted.map((ev, idx) => {
        const label = EVENT_LABELS[ev.kind || ""] || ev.kind || "事件"
        const summary = truncateText(eventDetail(ev), 160)
        return (
          <div key={`${ev.kind}-${ev.ts}-${idx}`} className="exec-activity-row">
            <span className="exec-activity-ts">{fmtExecTs(ev.ts)}</span>
            <span className="exec-activity-label">{label}</span>
            {summary && <span className="exec-activity-summary">{summary}</span>}
          </div>
        )
      })}
    </div>
  )
}
