import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ThinkingStream } from "@/components/chat/ThinkingStream"
import {
  getInteractionTimeline,
  subscribeInteractionEvents,
  type ProjectEvent,
  type TimelineEvent,
} from "@/lib/api/projects"
import {
  DAG_LABELS,
  EVENT_LABELS,
  EXEC_CHILD_LABELS,
  EXEC_TIMELINE_KINDS,
  eventDetail,
  fmtExecTs,
  INTERACTION_LABELS,
  INTERACTION_STATUS_LABEL,
  isExecThinkingKind,
  payloadPre,
  truncateText,
} from "@/lib/project-labels"
import {
  groupInteractionsByTask,
  listExecChildTasks,
  listExecRootTasks,
  taskActivityEvents,
  taskSplitEventsFor,
  type ExecTask,
} from "@/lib/project-exec"
import { timelineToThinkingEvents } from "@/lib/thinking"
import { GateFailureList } from "@/components/project/GateFailureList"
import { ProjectActivityFeed } from "@/components/project/ProjectActivityFeed"

function execStatusClass(status?: string) {
  if (status === "completed" || status === "done") return "status-completed"
  if (status === "running" || status === "in_progress") return "status-running"
  if (status === "failed" || status === "timed_out") return "status-failed"
  return `status-${status || "pending"}`
}

function TimelineDetail({ ev }: { ev: TimelineEvent }) {
  const p = ev.payload || {}
  const kind = ev.kind || ""
  if (kind === "text") {
    return (
      <div className="trace-section">
        <span className="trace-tag">输出</span>
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
        <span className="trace-tag">Prompt</span>
        <div className="trace-msg">{String(p.prompt || "").slice(0, 8000)}</div>
      </div>
    )
  }
  if (kind === "tool_result") {
    return (
      <div className="trace-section">
        <span className="trace-tag">返回</span>
        <div className="trace-msg">{String(p.content || "").slice(0, 8000)}</div>
      </div>
    )
  }
  return (
    <div className="trace-section">
      <span className="trace-tag">详情</span>
      <pre className="trace-pre">{payloadPre(p)}</pre>
    </div>
  )
}

function ExecChildRow({
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
  const summary = truncateText(eventDetail({ kind: ev.kind, payload: p }), open ? 500 : 140)
  const label = EVENT_LABELS[ev.kind || ""] || EXEC_CHILD_LABELS[ev.kind || ""] || ev.kind
  const cls =
    ev.kind === "tool_use"
      ? "exec-child-tool"
      : ev.kind === "text"
        ? "exec-child-text"
        : ["error", "transport_error", "watchdog_hard_kill"].includes(ev.kind || "")
          ? "exec-child-error"
          : "exec-child-mile"

  return (
    <div className={`exec-child ${cls}${open ? " open" : ""}`} data-child-id={childId}>
      <div className="exec-child-head" role="button" tabIndex={0} onClick={onToggle}>
        <span className="exec-chevron">{open ? "▾" : "▸"}</span>
        <div className="exec-child-main">
          <div className="exec-child-label">{label}</div>
          {summary && <div className="exec-child-summary">{summary}</div>}
        </div>
      </div>
      {open && (
        <div className="exec-child-body">
          <TimelineDetail ev={ev} />
        </div>
      )}
    </div>
  )
}

function PhaseBlock({
  event,
  open,
  onToggle,
  childrenOpen,
  onChildToggle,
  timeline,
  loading,
}: {
  event: ProjectEvent
  open: boolean
  onToggle: () => void
  childrenOpen: Record<string, boolean>
  onChildToggle: (id: string) => void
  timeline: TimelineEvent[]
  loading: boolean
}) {
  const label = INTERACTION_LABELS[event.kind || ""] || event.kind || "交互"
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
    <div className={`exec-node exec-phase ${execStatusClass(event.status)}${open ? " open" : ""}`}>
      <div className="exec-node-head" role="button" tabIndex={0} onClick={onToggle}>
        <span className="exec-chevron">{open ? "▾" : "▸"}</span>
        <div className="exec-node-main">
          <div className="exec-node-row1">
            <span className="exec-node-title">
              {label}
              {att}
            </span>
            <span className={`exec-status-badge s-${event.status || "pending"}`}>{stLabel}</span>
            {tok && <span className="exec-node-tok">{tok}</span>}
            <span className="exec-node-ts">{fmtExecTs(event.ts)}</span>
          </div>
        </div>
      </div>
      {open && (
        <div className="exec-node-body">
          {loading && <div className="exec-loading hint">加载明细…</div>}
          {!loading && timeline.length === 0 && (
            <div className="exec-empty hint">该步骤暂无 skill 调用或其它明细</div>
          )}
          {!loading && thinkingEvents.length > 0 && (
            <div className="exec-thinking-wrap">
              <ThinkingStream events={thinkingEvents} streaming={streaming} defaultOpen={streaming} />
            </div>
          )}
          {!loading &&
            milestoneEvents.map((ev, idx) => {
              const childId = `${event.interaction_id}:${ev.seq ?? idx}`
              return (
                <ExecChildRow
                  key={childId}
                  ev={ev}
                  childId={childId}
                  open={!!childrenOpen[childId]}
                  onToggle={() => onChildToggle(childId)}
                />
              )
            })}
        </div>
      )}
    </div>
  )
}

function TaskActivityStrip({ events }: { events: ProjectEvent[] }) {
  if (!events.length) return null
  return (
    <div className="exec-task-activity">
      {events.map((e, idx) => {
        const label = EVENT_LABELS[e.kind || ""] || e.kind || "事件"
        const summary = eventDetail(e)
        return (
          <div key={`${e.kind}-${e.ts}-${idx}`} className="exec-activity-row exec-activity-row--compact">
            <span className="exec-activity-ts">{fmtExecTs(e.ts)}</span>
            <span className="exec-activity-label">{label}</span>
            {summary && <span className="exec-activity-summary">{summary}</span>}
          </div>
        )
      })}
    </div>
  )
}

function SplitBanner({ events }: { events: ProjectEvent[] }) {
  if (!events.length) return null
  const last = events[events.length - 1]
  const summary = eventDetail(last)
  return (
    <div className="exec-split-banner">
      <div className="exec-split-title">{EVENT_LABELS.task_split}</div>
      {summary && <div className="exec-split-summary">{summary}</div>}
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
  openPhases,
  onPhaseToggle,
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
  openPhases: Record<string, boolean>
  onPhaseToggle: (iid: string) => void
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
  const subtitle = [task.agent, task.task_type].filter(Boolean).join(" · ")

  useEffect(() => {
    if (!open) return
    for (const p of phases) {
      const iid = p.interaction_id
      if (!iid || !openPhases[iid]) continue
      void loadTimeline(iid)
      if (p.status === "running") startStream(iid)
      else stopStream(iid)
    }
  }, [open, openPhases, phases, loadTimeline, startStream, stopStream])

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
          {subtitle && <div className="exec-node-meta">{subtitle}</div>}
        </div>
      </div>
      {open && (
        <div className="exec-node-body exec-task-body">
          <SplitBanner events={splitEvents} />
          <TaskActivityStrip events={activity} />
          {childTasks.length > 0 ? (
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
                  openPhases={openPhases}
                  onPhaseToggle={onPhaseToggle}
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
          ) : phases.length > 0 ? (
            <div className="exec-phases">
              {phases.map((p, idx) => {
                const iid = p.interaction_id!
                return (
                  <PhaseBlock
                    key={`${iid}-${idx}`}
                    event={p}
                    open={openPhases[iid] ?? p.status === "running"}
                    onToggle={() => onPhaseToggle(iid)}
                    childrenOpen={openChildren}
                    onChildToggle={onChildToggle}
                    timeline={timelines[iid] ?? []}
                    loading={!!loading[iid]}
                  />
                )
              })}
            </div>
          ) : (
            <div className="exec-empty hint">该任务暂无执行记录</div>
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
}: {
  tasks?: ExecTask[]
  events: ProjectEvent[]
  selectedTaskId?: string
  onSelectTask?: (taskId: string) => void
}) {
  const [openTasks, setOpenTasks] = useState<Record<string, boolean>>({})
  const [openPhases, setOpenPhases] = useState<Record<string, boolean>>({})
  const [openChildren, setOpenChildren] = useState<Record<string, boolean>>({})
  const [timelines, setTimelines] = useState<Record<string, TimelineEvent[]>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})

  const interactionsByTask = useMemo(() => groupInteractionsByTask(events), [events])
  const rootTasks = useMemo(() => listExecRootTasks(tasks, events), [tasks, events])

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
    const next: Record<string, boolean> = {}
    for (const list of Object.values(interactionsByTask)) {
      for (const p of list) {
        const iid = p.interaction_id
        if (!iid) continue
        if (p.status === "running") next[iid] = true
      }
    }
    if (Object.keys(next).length) {
      setOpenPhases((prev) => ({ ...next, ...prev }))
    }
  }, [interactionsByTask])

  if (!rootTasks.length && !activityEvents.length) {
    return <span className="hint">暂无执行事件</span>
  }

  return (
    <div className="exec-panel">
      <p className="exec-panel-hint">
        按任务折叠：展开后依次为派发评估、执行与评审阶段；若已拆分则展示子任务；循环轮次显示在任务内。
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
            openPhases={openPhases}
            onPhaseToggle={(iid) => setOpenPhases((prev) => ({ ...prev, [iid]: !prev[iid] }))}
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
      {activityEvents.length > 0 && (
        <details className="exec-activity-section">
          <summary>
            项目动态
            <span className="exec-activity-count">{activityEvents.length}</span>
          </summary>
          <ProjectActivityFeed events={activityEvents} />
        </details>
      )}
    </div>
  )
}
