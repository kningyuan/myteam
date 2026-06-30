import { useEffect, useMemo, useState } from "react"
import { getTaskDetail, type TaskDetail } from "@/lib/api/projects"
import { DAG_LABELS, formatGateFailures } from "@/lib/project/project-labels"
import { StatusBadge, statusLabel } from "@/components/ui/page"
import { Badge } from "@/components/ui/badge"

const FAIL_REASON_LABEL: Record<string, string> = {
  gate_exhausted: "门禁重试耗尽",
  no_response: "Agent 未响应",
  timeout_idle: "执行超时",
  cli_error: "CLI 错误",
}

export function ProjectTaskQualityCard({
  projectId,
  taskId,
  compact = false,
}: {
  projectId: string
  taskId: string
  compact?: boolean
}) {
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    setLoading(true)
    setError("")
    getTaskDetail(projectId, taskId)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch((e) => {
        if (!cancelled) {
          setDetail(null)
          setError(e instanceof Error ? e.message : "加载失败")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, taskId])

  const lastGateFailures = useMemo(() => {
    if (!detail?.interactions?.length) return []
    for (let i = detail.interactions.length - 1; i >= 0; i -= 1) {
      const fails = detail.interactions[i].gate_failures
      if (fails?.length) return fails
    }
    return []
  }, [detail])

  const lastReview = useMemo(() => {
    if (!detail?.interactions?.length) return null
    for (let i = detail.interactions.length - 1; i >= 0; i -= 1) {
      const r = detail.interactions[i].review
      if (r) return r
    }
    return null
  }, [detail])

  if (loading) {
    return (
      <div className="task-quality-card task-quality-card--loading">
        <span className="hint">加载任务质量…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="task-quality-card task-quality-card--error">
        <span className="text-sm text-red-400">{error}</span>
      </div>
    )
  }

  if (!detail) return null

  const task = detail.task
  const quality = detail.latest_quality
  const gateLines = formatGateFailures(lastGateFailures)
  const failLabel = task.fail_reason ? FAIL_REASON_LABEL[task.fail_reason] || task.fail_reason : ""

  return (
    <div className={`task-quality-card${compact ? " task-quality-card--compact" : ""}`}>
      <div className="task-quality-head">
        <div className="min-w-0">
          <div className="task-quality-title-row">
            <span className="task-quality-name">{task.name || task.id}</span>
            {task.status && (
              <StatusBadge status={task.status} label={DAG_LABELS[task.status] || statusLabel(task.status)} />
            )}
          </div>
          <p className="task-quality-meta">
            <span className="font-mono text-xs">{task.id}</span>
            {task.agent && ` · ${task.agent}`}
            {task.task_type && ` · ${task.task_type}`}
            {task.reviewer && ` · 评审 ${task.reviewer}`}
          </p>
        </div>
        {quality?.score != null && (
          <div className="task-quality-score">
            <span className="task-quality-score-val">{Math.round(Number(quality.score) * 100)}%</span>
            <span className="task-quality-score-label">自评</span>
          </div>
        )}
      </div>

      {(task.fail_reason || task.fail_detail) && (
        <div className="task-quality-block task-quality-block--fail">
          <div className="task-quality-block-title">失败原因</div>
          {failLabel && <p className="task-quality-fail-reason">{failLabel}</p>}
          {task.fail_detail && <p className="task-quality-fail-detail">{task.fail_detail}</p>}
        </div>
      )}

      {gateLines.length > 0 && (
        <div className="task-quality-block">
          <div className="task-quality-block-title">最近门禁未过</div>
          <ul className="task-quality-gate-list">
            {gateLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {quality && (quality.known_gaps?.length || quality.notes) && (
        <div className="task-quality-block">
          <div className="task-quality-block-title">Agent 自评</div>
          {quality.known_gaps?.length ? (
            <div className="task-quality-gaps">
              {quality.known_gaps.map((g) => (
                <Badge key={g} variant="secondary" className="text-xs">
                  {g}
                </Badge>
              ))}
            </div>
          ) : null}
          {quality.notes && <p className="task-quality-notes">{quality.notes}</p>}
        </div>
      )}

      {lastReview && (
        <div className="task-quality-block">
          <div className="task-quality-block-title">同行评审</div>
          <p className="task-quality-review">
            {lastReview.passed ? "通过" : "打回"}
            {lastReview.feedback ? ` · ${lastReview.feedback}` : ""}
          </p>
        </div>
      )}

      {task.summary && !compact && (
        <div className="task-quality-block">
          <div className="task-quality-block-title">交付摘要</div>
          <p className="task-quality-summary">{task.summary}</p>
        </div>
      )}

      {!gateLines.length &&
        !task.fail_reason &&
        !quality?.known_gaps?.length &&
        !lastReview &&
        !task.summary && (
          <p className="hint text-xs">暂无门禁或自评记录（任务可能尚未执行或仍在排队）</p>
        )}
    </div>
  )
}
