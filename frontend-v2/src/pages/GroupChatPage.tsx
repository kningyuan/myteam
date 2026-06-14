import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ChevronLeft } from "lucide-react"
import {
  getGroup,
  sendGroupChat,
  subscribeGroupEvents,
  type GroupMessage,
  type GroupSummary,
} from "@/lib/api/groups"
import { MarkdownBody } from "@/components/MarkdownBody"
import { Button } from "@/components/ui/button"
import { useImeCompositionGuard } from "@/lib/ime"

function fmtTime(ts: number) {
  if (!ts) return ""
  const d = new Date(ts > 1e12 ? ts : ts * 1000)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

function looksLikeMarkdown(text: string): boolean {
  return /^#{1,4}\s/m.test(text) || /\*\*[^*]+\*\*/.test(text) || /^[-*]\s/m.test(text)
}

export function GroupChatPage() {
  const { groupId = "" } = useParams()
  const [group, setGroup] = useState<GroupSummary | null>(null)
  const [messages, setMessages] = useState<GroupMessage[]>([])
  const [draft, setDraft] = useState("")
  const [error, setError] = useState("")
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { compositionProps, isImeComposing } = useImeCompositionGuard()

  const reload = useCallback(() => {
    if (!groupId) return
    getGroup(groupId)
      .then((g) => {
        setGroup(g)
        setMessages(g.messages ?? [])
      })
      .catch((e: Error) => setError(e.message))
  }, [groupId])

  useEffect(() => {
    reload()
  }, [reload])

  useEffect(() => {
    if (!groupId) return
    return subscribeGroupEvents(groupId, () => reload())
  }, [groupId, reload])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || !groupId || sending) return
    setSending(true)
    setDraft("")
    try {
      await sendGroupChat(groupId, text, (evt) => {
        if (evt.event === "group_message") {
          const d = evt.data as { sender?: string; text?: string; msg_id?: string; timestamp?: number }
          if (d?.text) {
            const msgText = d.text
            setMessages((prev) => [
              ...prev,
              {
                id: d.msg_id || `m_${Date.now()}`,
                sender: String(d.sender || "user"),
                text: msgText,
                timestamp: d.timestamp || Date.now() / 1000,
              },
            ])
          }
        }
        if (evt.event === "agent_thinking" || evt.event === "done") {
          reload()
        }
      })
      reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败")
    } finally {
      setSending(false)
    }
  }

  if (!group && !error) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载群聊…</p>
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4">
      <Link to="/groups" className="inline-flex items-center gap-1 text-sm text-[#00a8fc] hover:underline">
        <ChevronLeft className="h-4 w-4" /> 返回群组
      </Link>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
        <header className="border-b border-[var(--color-border)] px-5 py-4">
          <h1 className="text-lg font-semibold">{group?.name || groupId}</h1>
          <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
            成员：{(group?.members ?? []).join("、 ") || "—"}
          </p>
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-[var(--color-background)] p-4">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}
          {messages.map((m) => {
            const isUser = m.sender === "user"
            return (
              <div key={m.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[min(85%,640px)] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                    isUser
                      ? "rounded-br-md bg-[var(--color-chat-own)] text-white"
                      : "rounded-bl-md border border-[var(--color-border)] bg-[var(--color-chat-other)]"
                  }`}
                >
                  {!isUser && (
                    <div className="mb-1 text-xs font-medium text-[var(--color-brand-light)]">@{m.sender}</div>
                  )}
                  {looksLikeMarkdown(m.text) ? (
                    <MarkdownBody content={m.text} className="text-[inherit]" />
                  ) : (
                    <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                  )}
                  <div className={`mt-1.5 text-[10px] ${isUser ? "text-blue-100/80" : "text-[var(--color-muted-foreground)]"}`}>
                    {fmtTime(m.timestamp)}
                  </div>
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSend} className="flex gap-2 border-t border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <input
            className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5 text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:border-[var(--color-brand)] focus:outline-none"
            placeholder="输入消息，可 @agent 或 @all"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
            {...compositionProps}
            onKeyDown={(e) => {
              if (e.key === "Enter" && isImeComposing(e)) {
                e.preventDefault()
              }
            }}
          />
          <Button type="submit" disabled={sending || !draft.trim()}>
            发送
          </Button>
        </form>
      </div>
    </div>
  )
}
