import { useEffect, useMemo, useState, type ReactNode } from "react"
import { MarkdownBody } from "@/components/MarkdownBody"
import { ThinkingStream } from "@/components/chat/ThinkingStream"
import type { GroupMessage } from "@/lib/api/groups"
import type { LiveAgentReply } from "@/lib/groupChatLive"
import type { ThinkingEvent } from "@/lib/thinking"

/** 超过此长度才显示折叠控件 */
const FOLD_MIN_CHARS = 240
/** 超过此长度（或圆桌消息）默认折叠 */
const FOLD_DEFAULT_CHARS = 420

function messagePreview(text: string, maxLen = 100): string {
  const trimmed = text.trim()
  if (!trimmed) return "（空消息）"
  const heading = trimmed.match(/^#{1,3}\s+(.+)$/m)?.[1]?.trim()
  const firstLine = trimmed.split("\n").find((ln) => ln.trim() && !ln.startsWith("#"))
  const base = heading || firstLine?.trim() || trimmed
  const one = base.replace(/\s+/g, " ")
  if (one.length <= maxLen) return one
  return `${one.slice(0, maxLen - 1)}…`
}

function canFoldReply(
  text: string,
  streaming: boolean,
  opts: { roundtable?: boolean },
): boolean {
  if (streaming || !text.trim()) return false
  if (opts.roundtable) return true
  return text.trim().length >= FOLD_MIN_CHARS
}

function shouldDefaultReplyCollapsed(
  text: string,
  opts: { roundtable?: boolean; streaming?: boolean },
): boolean {
  if (opts.streaming) return false
  if (opts.roundtable) return true
  return text.trim().length >= FOLD_DEFAULT_CHARS
}

function fmtTime(ts: number) {
  if (!ts) return ""
  const d = new Date(ts > 1e12 ? ts : ts * 1000)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

export function GroupReadReceiptRow({
  targets,
  seen,
  active,
  agentName,
}: {
  targets: string[]
  seen: string[]
  active?: string
  agentName: (id: string) => string
}) {
  if (!targets.length) return null
  return (
    <div className="group-read-receipt">
      {targets.map((id) => {
        const done = seen.includes(id)
        const speaking = active === id
        return (
          <span
            key={id}
            className={`group-read-chip${done ? " done" : ""}${speaking ? " active" : ""}`}
            title={done ? "已回复" : speaking ? "发言中" : "等待中"}
          >
            {agentName(id)}
            {done ? " ✓" : speaking ? " …" : ""}
          </span>
        )
      })}
    </div>
  )
}

function GroupMessageFoldButton({
  collapsed,
  onToggle,
  preview,
  label = "回复",
}: {
  collapsed: boolean
  onToggle: () => void
  preview?: string
  label?: string
}) {
  return (
    <button
      type="button"
      className="group-msg-fold-btn"
      onClick={onToggle}
      aria-expanded={!collapsed}
      title={collapsed ? `展开${label}` : `折叠${label}`}
    >
      <span className="group-msg-fold-toggle" aria-hidden>
        ▼
      </span>
      <span className="group-msg-fold-label">
        {collapsed ? `展开${label}` : `折叠${label}`}
      </span>
      {collapsed && preview ? (
        <span className="group-msg-fold-preview">{preview}</span>
      ) : null}
    </button>
  )
}

function GroupMessageReplySection({
  collapsed,
  onToggle,
  preview,
  foldable,
  children,
}: {
  collapsed: boolean
  onToggle: () => void
  preview: string
  foldable: boolean
  children: ReactNode
}) {
  if (!foldable) {
    return <div className="group-msg-reply">{children}</div>
  }
  return (
    <div className={`group-msg-reply${collapsed ? " collapsed" : ""}`}>
      <GroupMessageFoldButton
        collapsed={collapsed}
        onToggle={onToggle}
        preview={preview}
        label="回复"
      />
      {collapsed ? (
        <div className="group-msg-preview-line">{preview}</div>
      ) : (
        <div className="group-msg-body">{children}</div>
      )}
    </div>
  )
}

function GroupSystemMessageBubble({ message }: { message: GroupMessage }) {
  const consensus = message.roundtable_consensus
  const summary = message.roundtable_user_decision_summary ?? ""
  const systemFoldable = summary.length >= FOLD_MIN_CHARS
  const [systemCollapsed, setSystemCollapsed] = useState(
    systemFoldable && summary.length >= FOLD_DEFAULT_CHARS,
  )

  return (
    <div className="group-msg-row system">
      <div
        className={`group-msg-system-pill${systemFoldable && systemCollapsed ? " collapsed" : ""}`}
      >
        {consensus === "await_user" && (
          <span className="mb-1 block text-xs font-medium text-amber-500/90">
            待你拍板 · 最佳实践草案 / 分歧见下方摘要
          </span>
        )}
        {consensus === "yes" && message.roundtable_meta?.artifact_type === "best_practice" && (
          <span className="mb-1 block text-xs font-medium text-emerald-500/90">
            已产出本题最佳实践
          </span>
        )}
        {message.text}
        {summary ? (
          <>
            {systemFoldable ? (
              <GroupMessageFoldButton
                collapsed={systemCollapsed}
                onToggle={() => setSystemCollapsed((v) => !v)}
                preview={messagePreview(summary, 80)}
              />
            ) : null}
            <div
              className={`group-msg-system-summary${systemFoldable && systemCollapsed ? " is-collapsed" : ""}`}
            >
              {summary}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

export function GroupMessageBubble({
  message,
  agentName,
  live,
}: {
  message?: GroupMessage
  agentName: (id: string) => string
  live?: LiveAgentReply
}) {
  const sender = live?.agentId ?? message?.sender ?? ""
  const isUser = sender === "user"
  const isSystem = sender === "system"
  const text = live?.text ?? message?.text ?? ""
  const thinking = live?.thinking ?? message?.thinking ?? []
  const streaming = live?.streaming ?? false
  const failedTurn = message?.turn_meta?.status === "failed"
  const timestamp = message?.timestamp ?? Date.now() / 1000
  const displayName = isUser ? "你" : agentName(sender)
  const roundtable = message?.roundtable ?? false
  const hasThinking = !isUser && (thinking.length > 0 || streaming)
  const foldable = canFoldReply(text, streaming, { roundtable })
  const preview = useMemo(() => messagePreview(text), [text])
  const [replyCollapsed, setReplyCollapsed] = useState(() =>
    foldable ? shouldDefaultReplyCollapsed(text, { roundtable, streaming }) : false,
  )

  useEffect(() => {
    if (streaming) setReplyCollapsed(false)
  }, [streaming])

  if (isSystem && message) {
    return <GroupSystemMessageBubble message={message} />
  }

  const replyBody =
    text ? (
      isUser ? (
        <div className="group-msg-text plain">{text}</div>
      ) : (
        <MarkdownBody content={text} />
      )
    ) : streaming && !thinking.length ? (
      <span className="thinking-wait text-[var(--color-muted-foreground)]">
        等待 Agent 响应…
      </span>
    ) : null

  return (
    <div className={`group-msg-row${isUser ? " own" : " other"}`}>
      <div className="group-msg-stack">
        {!isUser && (
          <div className="group-msg-meta">
            <span className="group-msg-sender">{displayName}</span>
            <span className="group-msg-time">{fmtTime(timestamp)}</span>
          </div>
        )}
        <div className={`group-msg-bubble${isUser ? " own" : " other"}`}>
          {hasThinking ? (
            <ThinkingStream
              events={thinking}
              streaming={streaming}
              defaultOpen={failedTurn}
            />
          ) : null}
          {isUser ? (
            <GroupMessageReplySection
              collapsed={replyCollapsed}
              onToggle={() => setReplyCollapsed((v) => !v)}
              preview={preview}
              foldable={foldable}
            >
              {replyBody}
            </GroupMessageReplySection>
          ) : replyBody ? (
            <GroupMessageReplySection
              collapsed={replyCollapsed}
              onToggle={() => setReplyCollapsed((v) => !v)}
              preview={preview}
              foldable={foldable}
            >
              {replyBody}
            </GroupMessageReplySection>
          ) : null}
        </div>
        {isUser && (
          <div className="group-msg-meta own">
            <span className="group-msg-time">{fmtTime(timestamp)}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function GroupLiveAgentBubble({
  live,
  agentName,
}: {
  live: LiveAgentReply
  agentName: (id: string) => string
}) {
  return (
    <GroupMessageBubble
      agentName={agentName}
      live={live}
    />
  )
}

export type { ThinkingEvent }
