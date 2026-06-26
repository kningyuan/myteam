import { useEffect, useRef, useState } from "react"
import { Copy, MoreVertical, Settings } from "lucide-react"
import { toast } from "sonner"
import {
  getAgentBackendConfig,
  updateAgentConfig,
  type AgentSummary,
} from "@/lib/api/agents"
import {
  archiveAgentChat,
  clearAgentChat,
} from "@/lib/api/chat"
import {
  listBackendModels,
  listBackends,
  type BackendModel,
  type BackendSummary,
} from "@/lib/api/config"
import {
  cancelAgentChatStream,
  getContextTokenBudget,
  resetAgentChatSession,
  sendAgentChatMessage,
  syncAgentChatFromServer,
  type CitationPart,
} from "@/lib/agentChatStream"
import { useImeCompositionGuard } from "@/lib/ime"
import { useAgentChat, useRestoreDraft } from "@/hooks/useAgentChat"
import { MarkdownBody } from "@/components/MarkdownBody"
import { ThinkingStream } from "@/components/chat/ThinkingStream"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function ContextIndicator({ used }: { used: number }) {
  const budget = getContextTokenBudget()
  if (!used) return null
  const pct = Math.min(100, (used / budget) * 100)
  const warn = pct >= 75 && pct < 90
  const over = pct >= 90
  return (
    <div className={`context-indicator${warn ? " ctx-warn" : ""}${over ? " ctx-over" : ""}`}>
      <div className="ctx-bar">
        <div className="ctx-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="ctx-label">
        {used.toLocaleString()} / {Math.round(budget / 1000)}k tokens
      </span>
    </div>
  )
}

function CitationsList({ parts }: { parts: CitationPart[] }) {
  if (!parts.length) return null
  return (
    <div className="chat-citations">
      <p className="chat-citations-title">引用来源</p>
      <ul>
        {parts.map((c, i) => (
          <li key={i}>
            {c.url ? (
              <a href={c.url} target="_blank" rel="noreferrer">
                {c.title || c.url}
              </a>
            ) : (
              <span>{c.title || c.source || "来源"}</span>
            )}
            {c.snippet ? <span className="chat-citation-snippet"> — {c.snippet}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function MoreMenu({
  onClear,
  onArchive,
  onConfig,
}: {
  onClear: () => void
  onArchive: () => void
  onConfig: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("click", onDoc)
    return () => document.removeEventListener("click", onDoc)
  }, [open])

  return (
    <div className="more-menu-wrap" ref={ref}>
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen((v) => !v)}>
        <MoreVertical className="h-4 w-4" />
      </Button>
      {open && (
        <div className="more-menu-dropdown">
          <button type="button" onClick={() => { setOpen(false); onConfig() }}>
            <Settings className="h-3.5 w-3.5" />
            Agent 配置
          </button>
          <button type="button" onClick={() => { setOpen(false); onClear() }}>
            清空对话
          </button>
          <button type="button" className="danger" onClick={() => { setOpen(false); onArchive() }}>
            删除对话窗口
          </button>
        </div>
      )}
    </div>
  )
}

export function AgentChatPanel({
  agent,
  onArchived,
}: {
  agent: AgentSummary
  onArchived?: () => void
}) {
  const { messages, busy, error, contextTokens } = useAgentChat(agent.id)
  const [draft, setDraft] = useState("")
  useRestoreDraft(agent.id, setDraft)

  const [configOpen, setConfigOpen] = useState(false)
  const [backend, setBackend] = useState("")
  const [model, setModel] = useState("")
  const [backends, setBackends] = useState<BackendSummary[]>([])
  const [models, setModels] = useState<BackendModel[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const { compositionProps, isImeComposing } = useImeCompositionGuard()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    if (!configOpen) return
    getAgentBackendConfig(agent.id)
      .then((cfg) => {
        setBackend(cfg.backend || agent.backend || "opencode")
        setModel(cfg.model || agent.model || "")
      })
      .catch(() => {
        setBackend(agent.backend || "opencode")
        setModel(agent.model || "")
      })
    listBackends().then(setBackends).catch(() => setBackends([]))
  }, [configOpen, agent])

  useEffect(() => {
    if (!backend) return
    listBackendModels(backend).then(setModels).catch(() => setModels([]))
  }, [backend])

  function handleCancel() {
    cancelAgentChatStream(agent.id)
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (busy) {
      handleCancel()
      return
    }
    const text = draft.trim()
    if (!text) return
    setDraft("")
    void sendAgentChatMessage(agent.id, text)
  }

  async function handleClear() {
    if (
      !window.confirm(
        "清空后将删除本页对话记录与 Agent 多轮上下文，下次对话 Agent 不会记得之前聊过什么。",
      )
    ) {
      return
    }
    if (busy) cancelAgentChatStream(agent.id)
    resetAgentChatSession(agent.id)
    try {
      await clearAgentChat(agent.id)
      await syncAgentChatFromServer(agent.id)
      toast.success("对话已清空")
    } catch (e) {
      toast.error("清空失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleArchive() {
    if (
      !window.confirm(
        `删除与「${agent.name || agent.id}」的对话窗口？\n侧栏隐藏，可用搜索找回；不会删除 Agent 配置。`,
      )
    ) {
      return
    }
    try {
      await archiveAgentChat(agent.id, {
        label: agent.name || agent.id,
        messages: messages.map((m) => ({ role: m.role, text: m.text })),
      })
      resetAgentChatSession(agent.id)
      toast.success("对话已归档")
      onArchived?.()
    } catch (e) {
      toast.error("归档失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function saveConfig() {
    try {
      await updateAgentConfig(agent.id, { backend, model })
      toast.success("Agent 配置已保存")
      setConfigOpen(false)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <header className="chat-header-bar">
        <div className="min-w-0">
          <div className="font-semibold truncate">{agent.name || agent.id}</div>
          <div className="text-xs text-[var(--color-muted-foreground)] truncate">
            {[agent.id, agent.backend, agent.model].filter(Boolean).join(" · ")}
            {busy ? " · 处理中" : ""}
          </div>
        </div>
        <MoreMenu onClear={handleClear} onArchive={handleArchive} onConfig={() => setConfigOpen(true)} />
      </header>
      <ContextIndicator used={contextTokens} />
      <div className="chat-messages">
        {error && (
          <div className="mb-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`mb-3 flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`agent-bubble group max-w-[min(85%,640px)] rounded-2xl px-4 py-2.5 text-sm ${
                m.role === "user"
                  ? "rounded-br-md bg-[var(--color-chat-own)] text-[var(--color-chat-own-fg)]"
                  : "rounded-bl-md border border-[var(--color-border)] bg-[var(--color-chat-other)] text-[var(--color-foreground)]"
              }`}
            >
              {m.role === "agent" && (
                <div className="mb-1 text-xs font-medium text-[var(--color-brand-light)]">@{agent.id}</div>
              )}
              {m.role === "agent" && (m.thinking?.length || m.streaming) ? (
                <ThinkingStream
                  events={m.thinking ?? []}
                  streaming={!!m.streaming}
                />
              ) : null}
              {m.text ? (
                m.role === "agent" ? (
                  <MarkdownBody content={m.text} />
                ) : (
                  <div className="whitespace-pre-wrap break-words">{m.text}</div>
                )
              ) : m.streaming && !(m.thinking?.length) ? (
                <span className="thinking-wait text-[var(--color-muted-foreground)]">等待 CLI 响应…</span>
              ) : null}
              {m.role === "agent" && m.citations?.length ? (
                <CitationsList parts={m.citations} />
              ) : null}
              <div className="msg-meta mt-1 flex items-center justify-end gap-2">
                <button
                  type="button"
                  className="msg-copy opacity-0 transition group-hover:opacity-70"
                  title="复制"
                  onClick={() => {
                    void navigator.clipboard.writeText(m.text || "").then(() => toast.success("已复制"))
                  }}
                >
                  <Copy className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form className="chat-input-bar" onSubmit={handleSend}>
        <textarea
          rows={1}
          placeholder="输入消息… Enter 发送，Shift+Enter 换行"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          {...compositionProps}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !isImeComposing(e)) {
              e.preventDefault()
              handleSend(e)
            }
          }}
        />
        {busy ? (
          <Button type="button" className="chat-send-stop" onClick={handleCancel}>
            停止
          </Button>
        ) : (
          <Button type="submit" disabled={!draft.trim()}>
            发送
          </Button>
        )}
      </form>

      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Agent 配置</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>后端</Label>
              <Select value={backend} onValueChange={setBackend}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {backends.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name || b.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>模型</Label>
              <Select value={model || "__default__"} onValueChange={(v) => setModel(v === "__default__" ? "" : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="默认" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">系统默认</SelectItem>
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name || m.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigOpen(false)}>
              取消
            </Button>
            <Button onClick={saveConfig}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
