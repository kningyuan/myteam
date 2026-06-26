import { useMemo, useState, type ReactNode } from "react"
import {
  describeStepFinishReason,
  describeToolAction,
  formatToolInputJson,
  isToolStepComplete,
  resolveToolResultContent,
  thinkingSectionLabel,
  toolIconAbbr,
  type ThinkingEvent,
} from "@/lib/thinking"

function ActivityResult({ content, label = "返回" }: { content: string; label?: string }) {
  return (
    <details className="activity-detail activity-result">
      <summary>
        {label} ({content.length.toLocaleString()} 字符)
      </summary>
      <pre className="activity-pre activity-pre-result">{content}</pre>
    </details>
  )
}

function StepFinishRow({ event }: { event: ThinkingEvent }) {
  const tok = event.tokens
  const reasoning = tok?.reasoning || 0
  const reasonLabel = describeStepFinishReason(event.reason || "")

  return (
    <div className="activity-meta activity-step-finish">
      <span>{reasonLabel}</span>
      {tok ? (
        <span className="activity-step-tokens">
          Token ↑{tok.input || 0} ↓{tok.output || 0}
          {reasoning > 0 ? ` · 内部推理 ≈${reasoning}` : null}
        </span>
      ) : null}
    </div>
  )
}

function StreamTextRow({ content, label = "中间输出" }: { content: string; label?: string }) {
  return (
    <details className="activity-detail activity-stream-block">
      <summary>
        {label} ({content.length.toLocaleString()} 字符)
      </summary>
      <pre className="activity-pre activity-stream-text">{content}</pre>
    </details>
  )
}

function ActivityRow({
  toolUse,
  toolResult,
}: {
  toolUse: ThinkingEvent
  toolResult?: ThinkingEvent
}) {
  const act = describeToolAction(toolUse.name || "tool", toolUse.input)
  const resultContent = resolveToolResultContent(toolUse, toolResult)
  const pending = !isToolStepComplete(toolUse, toolResult)
  const args = formatToolInputJson(toolUse.input)
  const isThink = (toolUse.name || "").toLowerCase() === "think"
  const thinkPreview =
    isThink && !resultContent
      ? act.target
      : ""

  return (
    <div className={`activity-row${pending ? " pending" : " done"}`}>
      <div className="activity-main">
        <span className="activity-icon" title={toolUse.name || ""}>
          {toolIconAbbr(toolUse.name || "tool")}
        </span>
        <span className="activity-verb">{act.verb}</span>
        {act.mono ? (
          <code className="activity-target">{act.target}</code>
        ) : (
          <span className="activity-target-text">{act.target}</span>
        )}
        <span className="activity-status">{pending ? "…" : "✓"}</span>
      </div>
      {thinkPreview ? (
        <div className="activity-think-preview">{thinkPreview}</div>
      ) : null}
      {!isThink || args.trim() !== thinkPreview ? (
        <details className="activity-detail">
          <summary>参数</summary>
          <pre className="activity-pre">{args}</pre>
        </details>
      ) : null}
      {resultContent ? <ActivityResult content={resultContent} /> : null}
    </div>
  )
}

export function ThinkingStream({
  events,
  streaming = false,
  defaultOpen = false,
}: {
  events: ThinkingEvent[]
  streaming?: boolean
  /** 默认折叠；仅调试时可传 true */
  defaultOpen?: boolean
}) {
  const [collapsed, setCollapsed] = useState(!defaultOpen)
  const { title, hint, live } = thinkingSectionLabel(events, streaming)

  const body = useMemo(() => {
    const nodes: ReactNode[] = []
    let step = 0
    for (let i = 0; i < events.length; i++) {
      const t = events[i]
      if (t.type === "step_start") {
        step += 1
        nodes.push(
          <div key={`step-${step}`} className="activity-step">
            <span className="activity-step-label">步骤 {step}</span>
          </div>,
        )
      } else if (t.type === "tool_use") {
        const next = events[i + 1]
        const paired = next?.type === "tool_result" ? next : undefined
        nodes.push(
          <ActivityRow key={`tool-${i}`} toolUse={t} toolResult={paired} />,
        )
        if (paired) i += 1
      } else if (t.type === "tool_result") {
        const content = typeof t.content === "string" ? t.content : ""
        nodes.push(
          <div key={`result-${i}`} className="activity-row done">
            {content ? <ActivityResult content={content} /> : null}
          </div>,
        )
      } else if (t.type === "step_finish") {
        nodes.push(<StepFinishRow key={`finish-${i}`} event={t} />)
      } else if (t.type === "stream_text" && t.content) {
        nodes.push(<StreamTextRow key={`stream-${i}`} content={t.content} />)
      } else if (t.type === "reasoning" && t.content) {
        nodes.push(
          <StreamTextRow key={`reason-${i}`} content={t.content} label="内部推理" />,
        )
      }
    }
    if (streaming && !nodes.length) {
      nodes.push(
        <div key="waiting" className="activity-meta">
          等待 CLI 返回思考事件…
        </div>,
      )
    }
    return nodes
  }, [events, streaming])

  if (!events.length && !streaming) return null

  return (
    <div
      className={`thinking-section${collapsed ? " collapsed" : ""}${live ? " thinking-live" : ""}`}
    >
      <button
        type="button"
        className="thinking-header"
        onClick={() => setCollapsed((v) => !v)}
        aria-expanded={!collapsed}
        title={collapsed ? "展开查看思考过程" : "折叠思考过程"}
      >
        <span className="thinking-toggle">▼</span>
        {live && collapsed ? (
          <span className="thinking-live-dot" aria-hidden />
        ) : null}
        <span className="thinking-title">{title}</span>
        {hint && collapsed ? (
          <span className="thinking-hint">{hint}</span>
        ) : null}
      </button>
      <div className="thinking-body">{body}</div>
    </div>
  )
}
