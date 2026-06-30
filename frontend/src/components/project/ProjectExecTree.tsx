import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ThinkingStream } from "@/components/chat/ThinkingStream"
import {
  getInteractionTimeline,
  subscribeInteractionEvents,
  listSkillReviews,
  type ProjectEvent,
  type SkillReviewEntry,
  type TimelineEvent,
} from "@/lib/api/projects"
import {
  DAG_LABELS,
  EVENT_LABELS,
  EXEC_TIMELINE_KINDS,
  eventDetail,
  execContentTag,
  execPhaseTag,
  fmtExecTs,
  INTERACTION_LABELS,
  INTERACTION_STATUS_LABEL,
  isExecThinkingKind,
  payloadPre,
  truncateText,
} from "@/lib/project/project-labels"
import {
  groupInteractionsByTask,
  listExecChildTasks,
  listExecRootTasks,
  listProjectLevelInteractions,
  taskActivityEvents,
  taskSplitEventsFor,
  type ExecTask,
} from "@/lib/project/project-exec"
import { timelineToThinkingEvents } from "@/lib/thinking"
import { GateFailureList } from "@/components/project/GateFailureList"
import { ProjectActivityFeed } from "@/components/project/ProjectActivityFeed"

function execStatusClass(status?: string) {
  if (status === "completed" || status === "done") return "status-completed"
  if (status === "running" || status === "in_progress") return "status-running"
  if (status === "failed" || status === "timed_out") return "status-failed"
  return `status-${status || "pending"}`
}

function ExecTag({ label, tone }: { label: string; tone: string }) {
  return <span className={`exec-tag exec-tag--${tone}`}>{label}</span>
}

function TimelineDetail({ ev }: { ev: TimelineEvent }) {
  const p = ev.payload || {}
  const kind = ev.kind || ""
  if (kind === "text") {
    return (
      <div className="trace-section">
        <ExecTag {...execContentTag(kind)} />
        <div className="trace-msg">{String(p.content || "").slice(0, 8000)}</div>
      </div>
    )
  }
  if (kind === "gate_failed" && Array.isArray(p.failures)) {
    return <GateFailureList failures={p.failures as Parameters<typeof GateFailureList>[0]["failures"]} />
  }
  if (kind === "prompt_sent") {
    return (
      <div className="trace-section">
        <ExecTag {...execContentTag(kind)} />
        <div className="trace-msg">{String(p.prompt || "").slice(0, 8000)}</div>
      </div>
    )
  }
  if (kind === "tool_result") {
    return (
      <div className="trace-section">
        <ExecTag {...execContentTag(kind)} />
        <div className="trace-msg">{String(p.content || "").slice(0, 8000)}</div>
      </div>
    )
  }
  return (
    <div className="trace-section">
      <ExecTag {...execContentTag(kind)} />
      <pre className="trace-pre">{payloadPre(p)}</pre>
    </div>
  )
}

function TaggedContentRow({
  ev,
  childId,
  open,
  onToggle,
}: {
  ev: TimelineEvent
  childId: string
  open: boolean
  onToggle: () => void
}) {
  const p = ev.payload || {}
  const tag = execContentTag(ev.kind)
  const title = EVENT_LABELS[ev.kind || ""] || ev.kind || "事件"
  const summary = truncateText(eventDetail({ kind: ev.kind, payload: p }), open ? 500 : 120)
  const expandable = !isExecThinkingKind(ev.kind) || ev.kind === "text"

  if (!expandable && summary) {
    return (
      <div className="exec-feed-row exec-feed-row--inline">
        <ExecTag {...tag} />
        <span className="exec-feed-title">{title}</span>
        <span className="exec-feed-summary">{summary}</span>
      </div>
    )
  }

  return (
    <div className={`exec-feed-row${open ? " open" : ""}`} data-child-id={childId}>
      <div className="exec-feed-head" role="button" tabIndex={0} onClick={onToggle}>
        <ExecTag {...tag} />
        <span className="exec-feed-title">{title}</span>
        {summary && <span className="exec-feed-summary">{summary}</span>}
        <span className="exec-chevron exec-chevron--sm">{open ? "▾" : "▸"}</span>
      </div>
      {open && (
        <div className="exec-feed-body">
          <TimelineDetail ev={ev} />
        </div>
      )}
    </div>
  )
}

function TaggedPhaseSection({
  event,
  timeline,
  loading,
  childrenOpen,
  onChildToggle,
}: {
  event: ProjectEvent
  timeline: TimelineEvent[]
  loading: boolean
  childrenOpen: Record<string, boolean>
  onChildToggle: (id: string) => void
}) {
  const phaseTag = execPhaseTag(event.kind)
  const phaseLabel = INTERACTION_LABELS[event.kind || ""] || event.kind || "步骤"
  const att = (event.attempt ?? 0) > 1 ? ` ×${event.attempt}` : ""
  const tok = event.tokens ? `${Number(event.tokens).toLocaleString()} tok` : ""
  const stLabel = INTERACTION_STATUS_LABEL[event.status || ""] || event.status || ""
  const streaming = event.status === "running"
  const thinkingEvents = useMemo(() => timelineToThinkingEvents(timeline), [timeline])
  const milestoneEvents = useMemo(
    () => timeline.filter((ev) => !isExecThinkingKind(ev.kind)),
    [timeline],
  )

  return (
    <section className={`exec-step ${execStatusClass(event.status)}`}>
      <header className="exec-step-head">
        <ExecTag {...phaseTag} />
        <span className="exec-step-title">
          {phaseLabel}
          {att}
        </span>
        <span className={`exec-status-badge s-${event.status || "pending"}`}>{stLabel}</span>
        {tok && <span className="exec-node-tok">{tok}</span>}
        <span className="exec-node-ts">{fmtExecTs(event.ts)}</span>
      </header>
      <div className="exec-step-body">
        {loading && <div className="exec-loading hint">加载中…</div>}
        {!loading && timeline.length === 0 && (
          <div className="exec-empty hint">暂无明细</div>
        )}
        {!loading && thinkingEvents.length > 0 && (
          <div className="exec-thinking-wrap">
            <div className="exec-feed-row exec-feed-row--think-label">
              <ExecTag label="思考" tone="think" />
              <span className="exec-feed-title">Agent 思考与 Skill 调用</span>
            </div>
            <ThinkingStream events={thinkingEvents} streaming={streaming} defaultOpen={streaming} />
          </div>
        )}
        {!loading &&
          milestoneEvents.map((ev, idx) => {
            const childId = `${event.interaction_id}:${ev.seq ?? idx}`
            return (
              <TaggedContentRow
                key={childId}
                ev={ev}
                childId={childId}
                open={!!childrenOpen[childId]}
                onToggle={() => onChildToggle(childId)}
              />
            )
          })}
      </div>
    </section>
  )
}

function TaskActivityStrip({ events }: { events: ProjectEvent[] }) {
  if (!events.length) return null
  return (
    <div className="exec-step exec-step--activity">
      <header className="exec-step-head">
        <ExecTag label="循环" tone="loop" />
        <span className="exec-step-title">轮次与分支</span>
      </header>
      <div className="exec-step-body">
        {events.map((e, idx) => {
          const tag = execContentTag(e.kind)
          const summary = eventDetail(e)
          return (
            <div key={`${e.kind}-${e.ts}-${idx}`} className="exec-feed-row exec-feed-row--inline">
              <ExecTag {...tag} />
              <span className="exec-feed-title">{EVENT_LABELS[e.kind || ""] || e.kind}</span>
              {summary && <span className="exec-feed-summary">{summary}</span>}
              <span className="exec-node-ts">{fmtExecTs(e.ts)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SplitBanner({ events }: { events: ProjectEvent[] }) {
  if (!events.length) return null
  const last = events[events.length - 1]
  const summary = eventDetail(last)
  return (
    <div className="exec-step exec-step--split">
      <header className="exec-step-head">
        <ExecTag label="拆分" tone="split" />
        <span className="exec-step-title">{EVENT_LABELS.task_split}</span>
      </header>
      {summary && <div className="exec-split-summary">{summary}</div>}
    </div>
  )
}

function SkillReviewStrip({ reviews }: { reviews: SkillReviewEntry[] }) {
  if (!reviews.length) return null
  const latest = reviews[0]
  const statusColor = latest.status === "completed" ? "status-completed"
    : latest.status === "failed" ? "status-failed"
    : "status-running"

  return (
    <div className={`exec-step exec-step--skill-review ${statusColor}`}>
      <header className="exec-step-head">
        <ExecTag label="复盘" tone="review" />
        <span className="exec-step-title">Skill 复盘</span>
        <span className={`exec-status-badge s-${latest.status || "pending"}`}>
          {latest.status === "completed" ? "已完成"
            : latest.status === "failed" ? "失败"
            : latest.status === "running" ? "运行中"
            : "等待中"}
        </span>
      </header>
      <div className="exec-step-body">
        {reviews.map((r, idx) => {
          const result = (r.result as Record<string, unknown>) || {}
          const action = String(result.action || "noop")
          const skillId = String(result.skill_id || "")
          const notes = String(result.notes || "")
          const error = String(r.error || "")
          return (
            <div key={`${r.review_id ?? idx}`} className="exec-feed-row exec-feed-row--inline">
              <ExecTag label={EVENT_LABELS[`skill_review_${r.status}`] || "复盘"} tone="review" />
              <span className="exec-feed-title">
                {action === "noop" ? "无需修改" : `action=${action}`}
                {skillId && <span className="exec-feed-summary"> · skill={skillId}</span>}
              </span>
              {notes && <span className="exec-feed-summary">{truncateText(notes, 80)}</span>}
              {error && <span className="exec-feed-summary" style={{ color: "var(--color-error)" }}>Error: {truncateText(error, 60)}</span>}
              <span className="exec-node-ts">{fmtExecTs(r.created_at)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TaskFold({
  task,
  allTasks,
  events,
  interactionsByTask,
  depth,
  open,
  onToggle,
  openChildren,
  onChildToggle,
  timelines,
  loading,
  loadTimeline,
  startStream,
  stopStream,
  selectedTaskId,
  onSelectTask,
  openTasks,
  onTaskToggle,
}: {
  task: ExecTask
  allTasks: ExecTask[]
  events: ProjectEvent[]
  interactionsByTask: Record<string, ProjectEvent[]>
  depth: number
  open: boolean
  onToggle: () => void
  openChildren: Record<string, boolean>
  onChildToggle: (id: string) => void
  timelines: Record<string, TimelineEvent[]>
  loading: Record<string, boolean>
  loadTimeline: (iid: string, force?: boolean) => void
  startStream: (iid: string) => void
  stopStream: (iid: string) => void
  selectedTaskId?: string
  onSelectTask?: (taskId: string) => void
  openTasks: Record<string, boolean>
  onTaskToggle: (taskId: string) => void
}) {
  const childTasks = listExecChildTasks(task, allTasks)
  const phases = interactionsByTask[task.id] ?? []
  const splitEvents = taskSplitEventsFor(events, task.id)
  const activity = taskActivityEvents(events, task.id)
  const stLabel = DAG_LABELS[task.status || ""] || task.status || ""
  const agentLine = [task.agent && `Agent · ${task.agent}`, task.task_type].filter(Boolean).join(" · ")

  useEffect(() => {
    if (!open) return
    for (const p of phases) {
      const iid = p.interaction_id
      if (!iid) continue
      void loadTimeline(iid)
      if (p.status === "running") startStream(iid)
      else stopStream(iid)
    }
  }, [open, phases, loadTimeline, startStream, stopStream])

  const hasBody = phases.length > 0 || splitEvents.length > 0 || activity.length > 0 || childTasks.length > 0

  return (
    <div
      className={`exec-node exec-task-fold ${execStatusClass(task.status)}${open ? " open" : ""}${
        depth > 0 ? " exec-task-fold--nested" : ""
      }${selectedTaskId === task.id ? " selected" : ""}`}
    >
      <div className="exec-node-head" role="button" tabIndex={0} onClick={onToggle}>
        <span className="exec-chevron">{open ? "▾" : "▸"}</span>
        <div className="exec-node-main">
          <div className="exec-node-row1">
            <ExecTag label="任务" tone="task" />
            <button
              type="button"
              className={`exec-task-title${selectedTaskId === task.id ? " active" : ""}`}
              onClick={(e) => {
                e.stopPropagation()
                onSelectTask?.(task.id)
              }}
            >
              {task.name || task.id}
            </button>
            <span className={`exec-status-badge s-${task.status || "pending"}`}>{stLabel}</span>
          </div>
          {agentLine && <div className="exec-node-meta">{agentLine}</div>}
        </div>
      </div>
      {open && (
        <div className="exec-node-body exec-task-body">
          {!hasBody && <div className="exec-empty hint">该任务暂无执行记录</div>}
          {phases.map((p, idx) => {
            const iid = p.interaction_id!
            return (
              <TaggedPhaseSection
                key={`${iid}-${idx}`}
                event={p}
                timeline={timelines[iid] ?? []}
                loading={!!loading[iid]}
                childrenOpen={openChildren}
                onChildToggle={onChildToggle}
              />
            )
          })}
          <SplitBanner events={splitEvents} />
          <TaskActivityStrip events={activity} />
          {childTasks.length > 0 && (
            <div className="exec-subtasks">
              {childTasks.map((child) => (
                <TaskFold
                  key={child.id}
                  task={child}
                  allTasks={allTasks}
                  events={events}
                  interactionsByTask={interactionsByTask}
                  depth={depth + 1}
                  open={!!openTasks[child.id]}
                  onToggle={() => onTaskToggle(child.id)}
                  openChildren={openChildren}
                  onChildToggle={onChildToggle}
                  timelines={timelines}
                  loading={loading}
                  loadTimeline={loadTimeline}
                  startStream={startStream}
                  stopStream={stopStream}
                  selectedTaskId={selectedTaskId}
                  onSelectTask={onSelectTask}
                  openTasks={openTasks}
                  onTaskToggle={onTaskToggle}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ProjectExecTree({
  tasks = [],
  events,
  selectedTaskId,
  onSelectTask,
  projectId: propProjectId,
}: {
  tasks?: ExecTask[]
  events: ProjectEvent[]
  selectedTaskId?: string
  onSelectTask?: (taskId: string) => void
  projectId?: string
}) {
  const [openTasks, setOpenTasks] = useState<Record<string, boolean>>({})
  const [openChildren, setOpenChildren] = useState<Record<string, boolean>>({})
  const [timelines, setTimelines] = useState<Record<string, TimelineEvent[]>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [skillReviews, setSkillReviews] = useState<SkillReviewEntry[]>([])
  const [skillReviewLoading, setSkillReviewLoading] = useState(false)

  const interactionsByTask = useMemo(() => groupInteractionsByTask(events), [events])
  const rootTasks = useMemo(() => listExecRootTasks(tasks, events), [tasks, events])
  const projectLevelInteractions = useMemo(() => listProjectLevelInteractions(events), [events])

  const visibleTaskIds = useMemo(() => {
    const ids = new Set<string>()
    const walk = (t: ExecTask) => {
      ids.add(t.id)
      for (const c of listExecChildTasks(t, tasks)) walk(c)
    }
    for (const t of rootTasks) walk(t)
    return ids
  }, [rootTasks, tasks])

  const activityEvents = useMemo(() => {
    const interactionIds = new Set(
      events.filter((e) => e.category === "interaction" && e.interaction_id).map((e) => e.interaction_id!),
    )
    return events.filter((e) => {
      if (e.category !== "event") return false
      if (e.kind === "task_split") return false
      if (e.task_id && visibleTaskIds.has(e.task_id)) return false
      const iid = e.interaction_id || ""
      if (iid && interactionIds.has(iid)) return false
      return true
    })
  }, [events, visibleTaskIds])

  const loadedRef = useRef<Set<string>>(new Set())
  const streamsRef = useRef<Record<string, () => void>>({})

  const loadTimeline = useCallback(async (iid: string, force = false) => {
    if (!force && loadedRef.current.has(iid)) return
    loadedRef.current.add(iid)
    setLoading((prev) => ({ ...prev, [iid]: true }))
    try {
      const data = await getInteractionTimeline(iid)
      const tl = (data.timeline ?? []).filter((ev) => EXEC_TIMELINE_KINDS.has(ev.kind || ""))
      setTimelines((prev) => ({ ...prev, [iid]: tl }))
    } catch {
      setTimelines((prev) => ({ ...prev, [iid]: [] }))
    } finally {
      setLoading((prev) => ({ ...prev, [iid]: false }))
    }
  }, [])

  const stopStream = useCallback((iid: string) => {
    streamsRef.current[iid]?.()
    delete streamsRef.current[iid]
  }, [])

  const startStream = useCallback(
    (iid: string) => {
      stopStream(iid)
      streamsRef.current[iid] = subscribeInteractionEvents(iid, () => {
        loadedRef.current.delete(iid)
        void loadTimeline(iid, true)
      })
    },
    [loadTimeline, stopStream],
  )

  useEffect(() => {
    return () => {
      for (const stop of Object.values(streamsRef.current)) stop()
      streamsRef.current = {}
    }
  }, [])

  useEffect(() => {
    if (!rootTasks.length) return
    setOpenTasks((prev) => {
      const next = { ...prev }
      for (const t of rootTasks) {
        if ((t.status === "running" || t.status === "in_progress") && next[t.id] === undefined) {
          next[t.id] = true
        }
      }
      if (selectedTaskId && next[selectedTaskId] === undefined) {
        next[selectedTaskId] = true
      }
      return next
    })
  }, [rootTasks, selectedTaskId])

  useEffect(() => {
    if (!propProjectId) return
    setSkillReviewLoading(true)
    listSkillReviews(propProjectId)
      .then(setSkillReviews)
      .catch(() => setSkillReviews([]))
      .finally(() => setSkillReviewLoading(false))
  }, [propProjectId])

  if (!rootTasks.length && !activityEvents.length && !projectLevelInteractions.length) {
    return <span className="hint">暂无执行事件</span>
  }

  return (
    <div className="exec-panel">
      <p className="exec-panel-hint">
        每个任务展示 Agent 的思考与执行过程；彩色标签标出阶段与内容类型。
      </p>
      <div className="exec-tree">
        {rootTasks.map((task) => (
          <TaskFold
            key={task.id}
            task={task}
            allTasks={tasks}
            events={events}
            interactionsByTask={interactionsByTask}
            depth={0}
            open={!!openTasks[task.id]}
            onToggle={() => setOpenTasks((prev) => ({ ...prev, [task.id]: !prev[task.id] }))}
            openChildren={openChildren}
            onChildToggle={(cid) => setOpenChildren((prev) => ({ ...prev, [cid]: !prev[cid] }))}
            timelines={timelines}
            loading={loading}
            loadTimeline={loadTimeline}
            startStream={startStream}
            stopStream={stopStream}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
            openTasks={openTasks}
            onTaskToggle={(id) => setOpenTasks((prev) => ({ ...prev, [id]: !prev[id] }))}
          />
        ))}
        {!rootTasks.length && <p className="hint exec-tree-empty">暂无可展示的任务执行记录</p>}
      </div>
      {(projectLevelInteractions.length > 0 || activityEvents.length > 0) && (
        <details className="exec-activity-section">
          <summary>
            项目动态
            <span className="exec-activity-count">
              {projectLevelInteractions.length + activityEvents.length}
            </span>
          </summary>
          <ProjectActivityFeed
            events={[
              ...projectLevelInteractions.map((e) => ({
                ...e,
                category: "interaction" as const,
              })),
              ...activityEvents,
            ]}
          />
        </details>
      )}
      {skillReviews.length > 0 && (
        <SkillReviewStrip reviews={skillReviews} />
      )}
      {skillReviewLoading && skillReviews.length === 0 && (
        <div className="exec-step exec-step--skill-review">
          <header className="exec-step-head">
            <ExecTag label="复盘" tone="review" />
            <span className="exec-step-title">Skill 复盘</span>
          </header>
          <div className="exec-step-body">
            <p className="hint">加载中...</p>
          </div>
        </div>
      )}
    </div>
  )
}
