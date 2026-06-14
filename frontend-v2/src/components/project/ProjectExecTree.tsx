import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ThinkingStream } from "@/components/chat/ThinkingStream"
import {
  getInteractionTimeline,
  subscribeInteractionEvents,
  type ProjectEvent,
  type TimelineEvent,
} from "@/lib/api/projects"
import {
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
import { timelineToThinkingEvents } from "@/lib/thinking"
import { GateFailureList } from "@/components/project/GateFailureList"
import { ProjectActivityFeed } from "@/components/project/ProjectActivityFeed"

function execStatusClass(status?: string) {
  if (status === "completed" || status === "done") return "status-completed"
  if (status === "running") return "status-running"
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

function InteractionNode({
  event,
  open,
  onToggle,
  childrenOpen,
  onChildToggle,
  timeline,
  loading,
  onSelectTask,
  selectedTaskId,
}: {
  event: ProjectEvent
  open: boolean
  onToggle: () => void
  childrenOpen: Record<string, boolean>
  onChildToggle: (id: string) => void
  timeline: TimelineEvent[]
  loading: boolean
  onSelectTask?: (taskId: string) => void
  selectedTaskId?: string
}) {
  const label = INTERACTION_LABELS[event.kind || ""] || event.kind || "交互"
  const att = (event.attempt ?? 0) > 1 ? ` ×${event.attempt}` : ""
  const who = [event.task_id, event.agent_id].filter(Boolean).join(" · ")
  const tok = event.tokens ? `${Number(event.tokens).toLocaleString()} tok` : ""
  const stLabel = INTERACTION_STATUS_LABEL[event.status || ""] || event.status || ""
  const streaming = event.status === "running"
  const thinkingEvents = useMemo(
    () => timelineToThinkingEvents(timeline),
    [timeline],
  )
  const milestoneEvents = useMemo(
    () => timeline.filter((ev) => !isExecThinkingKind(ev.kind)),
    [timeline],
  )

  return (
    <div className={`exec-node ${execStatusClass(event.status)}${open ? " open" : ""}`}>
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
          {who && (
            <div className="exec-node-meta">
              {event.task_id ? (
                <button
                  type="button"
                  className={`exec-task-link${selectedTaskId === event.task_id ? " active" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectTask?.(event.task_id!)
                  }}
                >
                  {who}
                </button>
              ) : (
                who
              )}
            </div>
          )}
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
              <ThinkingStream
                events={thinkingEvents}
                streaming={streaming}
                defaultOpen={streaming}
              />
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

export function ProjectExecTree({
  events,
  selectedTaskId,
  onSelectTask,
}: {
  events: ProjectEvent[]
  selectedTaskId?: string
  onSelectTask?: (taskId: string) => void
}) {
  const [openNodes, setOpenNodes] = useState<Record<string, boolean>>({})
  const [openChildren, setOpenChildren] = useState<Record<string, boolean>>({})
  const [timelines, setTimelines] = useState<Record<string, TimelineEvent[]>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})

  const { interactionEvents, activityEvents } = useMemo(() => {
    const ids = new Set(
      events.filter((e) => e.category === "interaction" && e.interaction_id).map((e) => e.interaction_id!),
    )
    const interactions = events.filter((e) => e.category === "interaction" && e.interaction_id)
    const activity = events.filter((e) => {
      if (e.category !== "event") return false
      const iid = e.interaction_id || ""
      if (iid && ids.has(iid)) return false
      return true
    })
    return { interactionEvents: interactions, activityEvents: activity }
  }, [events])

  const loadedRef = useRef<Set<string>>(new Set())
  const streamsRef = useRef<Record<string, () => void>>({})

  const loadTimeline = useCallback(async (iid: string, force = false) => {
    if (!force && loadedRef.current.has(iid)) return
    loadedRef.current.add(iid)
    setLoading((prev) => ({ ...prev, [iid]: true }))
    try {
      const data = await getInteractionTimeline(iid)
      const tl = (data.timeline ?? []).filter((e) => EXEC_TIMELINE_KINDS.has(e.kind || ""))
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
    for (const [iid, isOpen] of Object.entries(openNodes)) {
      if (isOpen) {
        void loadTimeline(iid)
        const ev = events.find((e) => e.interaction_id === iid)
        if (ev?.status === "running") startStream(iid)
        else stopStream(iid)
      } else {
        stopStream(iid)
      }
    }
  }, [openNodes, events, loadTimeline, startStream, stopStream])

  if (!interactionEvents.length && !activityEvents.length) {
    return <span className="hint">暂无执行事件</span>
  }

  return (
    <div className="exec-panel">
      <p className="exec-panel-hint">
        交互步骤：展开后上方为思考过程（工具调用与模型输出），下方为门禁、Prompt 等里程碑。
        项目动态含循环轮次完成（loop_round_done）与循环结束（loop_finished）事件。
      </p>
      <div className="exec-tree">
        {interactionEvents.map((e, idx) => {
          const iid = e.interaction_id!
          return (
            <InteractionNode
              key={`i-${iid}-${idx}`}
              event={e}
              open={!!openNodes[iid]}
              onToggle={() => setOpenNodes((prev) => ({ ...prev, [iid]: !prev[iid] }))}
              childrenOpen={openChildren}
              onChildToggle={(cid) => setOpenChildren((prev) => ({ ...prev, [cid]: !prev[cid] }))}
              timeline={timelines[iid] ?? []}
              loading={!!loading[iid]}
              onSelectTask={onSelectTask}
              selectedTaskId={selectedTaskId}
            />
          )
        })}
        {!interactionEvents.length && (
          <p className="hint exec-tree-empty">暂无交互步骤记录</p>
        )}
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
