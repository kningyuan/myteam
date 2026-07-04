import { Badge } from "@/components/ui/badge"

export type IterationSummary = {
  loop_id?: string
  placeholder_task_id?: string
  state?: string
  current_round?: number
  max_rounds?: number
  body_key?: string
  last_assess_marker?: string
  last_assess_action?: string
  last_assess_matched_rule?: number
  rounds_used?: number
  placeholder_status?: string
}

const STATE_LABEL: Record<string, string> = {
  running: "进行中",
  passed: "已通过",
  exhausted: "轮次用尽",
  needs_review: "待复核",
  finished: "已结束",
}

export function IterationProgressCard({
  iterations,
  highlightTaskId,
}: {
  iterations?: IterationSummary[]
  highlightTaskId?: string
}) {
  const rows = iterations || []
  if (!rows.length) return null

  return (
    <div className="iteration-progress-card space-y-3">
      <h4 className="text-sm font-medium">迭代轮次</h4>
      {rows.map((it) => {
        const active =
          highlightTaskId &&
          (it.placeholder_task_id === highlightTaskId ||
            (it.loop_id && highlightTaskId.includes(it.loop_id)))
        return (
          <div
            key={`${it.loop_id}-${it.placeholder_task_id}`}
            className={`iteration-progress-row rounded-md border p-3 text-sm ${
              active ? "border-[var(--color-primary)] bg-[var(--color-muted)]/30" : ""
            }`}
          >
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="font-medium">{it.loop_id}</span>
              <Badge variant="outline">{STATE_LABEL[it.state || ""] || it.state || "—"}</Badge>
              {it.body_key && it.body_key !== "default" && (
                <Badge variant="secondary">body: {it.body_key}</Badge>
              )}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-[var(--color-muted-foreground)]">
              <span>
                轮次 {it.current_round ?? 0}
                {it.max_rounds ? ` / ${it.max_rounds}` : ""}
              </span>
              <span>已用 {it.rounds_used ?? 0} 轮</span>
              {it.last_assess_marker && (
                <span className="col-span-2">Assess: {it.last_assess_marker}</span>
              )}
              {it.last_assess_action && (
                <span className="col-span-2">Transition: {it.last_assess_action}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
