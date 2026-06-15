/**
 * 全局 Agent 对话流 — 对齐 v1 的 S.streams / S.agentMessages：
 * 切页、换 Agent 不中断底层 CLI（经 Hub → CLIAdapter）；仅用户点「停止」才取消。
 */

import { isAbortError } from "@/lib/api/client"
import {
  cancelAgentChat,
  getAgentChatMessages,
  sendAgentChat,
  type ChatMessage,
} from "@/lib/api/chat"
import { invalidateResources } from "@/lib/dataRefresh"
import { applyThinkingEvent, type ThinkingEvent } from "@/lib/thinking"

export type CitationPart = {
  title?: string
  url?: string
  snippet?: string
  source?: string
}

export type AgentUiMessage = {
  id: string
  role: "user" | "agent"
  text: string
  thinking?: ThinkingEvent[]
  citations?: CitationPart[]
  streaming?: boolean
}

type ActiveTurn = { userId: string; agentMsgId: string }

type AgentChatSession = {
  messages: AgentUiMessage[]
  loaded: boolean
  busy: boolean
  userCancelled: boolean
  pendingText: string
  restoreDraft: string
  activeTurn: ActiveTurn | null
  abortCtrl: AbortController | null
  error: string
  contextTokens: number
}

const CONTEXT_TOKEN_BUDGET = 25000
const agentEventSources = new Map<string, EventSource>()

const sessions = new Map<string, AgentChatSession>()
const agentListeners = new Map<string, Set<() => void>>()
const globalListeners = new Set<() => void>()
const settleListeners = new Set<(agentId: string) => void>()

function ensureSession(agentId: string): AgentChatSession {
  let s = sessions.get(agentId)
  if (!s) {
    s = {
      messages: [],
      loaded: false,
      busy: false,
      userCancelled: false,
      pendingText: "",
      restoreDraft: "",
      activeTurn: null,
      abortCtrl: null,
      error: "",
      contextTokens: 0,
    }
    sessions.set(agentId, s)
  }
  return s
}

function notify(agentId: string) {
  agentListeners.get(agentId)?.forEach((fn) => fn())
  globalListeners.forEach((fn) => fn())
}

function toUiMessages(msgs: ChatMessage[]): AgentUiMessage[] {
  return msgs.map((m, i) => ({
    id: String(m.seq ?? i),
    role: m.role === "user" ? "user" : "agent",
    text: m.text || "",
    thinking: m.thinking?.length ? [...m.thinking] : undefined,
  }))
}

function attachInflight(serverMsgs: AgentUiMessage[], localMsgs: AgentUiMessage[]): AgentUiMessage[] {
  if (!serverMsgs.length) return localMsgs
  const out = serverMsgs.slice()
  const lastLocal = localMsgs[localMsgs.length - 1]
  const prevLocal = localMsgs[localMsgs.length - 2]
  if (lastLocal?.role === "agent" && prevLocal?.role === "user") {
    const lastSrv = out[out.length - 1]
    if (lastSrv?.role === "user") {
      out.push({
        ...lastLocal,
        thinking: lastLocal.thinking ? [...lastLocal.thinking] : [],
      })
    }
  }
  return out
}

export async function syncAgentChatFromServer(agentId: string): Promise<void> {
  const s = ensureSession(agentId)
  try {
    const msgs = await getAgentChatMessages(agentId)
    const mapped = toUiMessages(msgs)
    s.messages = s.busy ? attachInflight(mapped, s.messages) : mapped
    s.loaded = true
    s.error = ""
    notify(agentId)
  } catch (e) {
    s.error = e instanceof Error ? e.message : "加载失败"
    notify(agentId)
  }
}

function rollbackTurn(s: AgentChatSession) {
  const turn = s.activeTurn
  if (!turn) return
  s.messages = s.messages.filter((m) => m.id !== turn.userId && m.id !== turn.agentMsgId)
  s.restoreDraft = s.pendingText
  s.activeTurn = null
}

export function isAgentStreamBusy(agentId: string): boolean {
  return ensureSession(agentId).busy
}

export function getAgentChatSnapshot(agentId: string) {
  const s = ensureSession(agentId)
  return {
    messages: s.messages,
    busy: s.busy,
    error: s.error,
    loaded: s.loaded,
    restoreDraft: s.restoreDraft,
    contextTokens: s.contextTokens,
  }
}

export function consumeRestoreDraft(agentId: string): string {
  const s = ensureSession(agentId)
  const d = s.restoreDraft
  s.restoreDraft = ""
  return d
}

export function subscribeAgentChat(agentId: string, fn: () => void): () => void {
  if (!agentListeners.has(agentId)) agentListeners.set(agentId, new Set())
  agentListeners.get(agentId)!.add(fn)
  return () => agentListeners.get(agentId)?.delete(fn)
}

export function subscribeAgentChatGlobal(fn: () => void): () => void {
  globalListeners.add(fn)
  return () => globalListeners.delete(fn)
}

export function onAgentStreamSettled(fn: (agentId: string) => void): () => void {
  settleListeners.add(fn)
  return () => settleListeners.delete(fn)
}

function emitSettled(agentId: string) {
  invalidateResources("agents")
  settleListeners.forEach((fn) => fn(agentId))
}

export function getAgentContextTokens(agentId: string): number {
  return ensureSession(agentId).contextTokens
}

export function getContextTokenBudget(): number {
  return CONTEXT_TOKEN_BUDGET
}

function accumulateContextTokens(agentId: string, tokenData?: ThinkingEvent["tokens"]) {
  if (!tokenData) return
  const add =
    tokenData.total ||
    (Number(tokenData.input) || 0) + (Number(tokenData.output) || 0)
  if (!add) return
  const s = ensureSession(agentId)
  s.contextTokens += add
  notify(agentId)
}

export function resetAgentContextTokens(agentId: string) {
  const s = ensureSession(agentId)
  s.contextTokens = 0
  notify(agentId)
}

function connectAgentBackgroundEvents(agentId: string) {
  if (!agentId || agentEventSources.has(agentId)) return
  const es = new EventSource(`/api/agents/${encodeURIComponent(agentId)}/events`)
  agentEventSources.set(agentId, es)
  es.onmessage = (e) => {
    if (!e.data || e.data === "[DONE]") return
    try {
      const ev = JSON.parse(e.data) as { event?: string; data?: Record<string, unknown> }
      if (ev.event === "agent_thinking" && ev.data) {
        const s = ensureSession(agentId)
        const blockId = `bg_${Date.now()}`
        s.messages = [
          ...s.messages,
          {
            id: blockId,
            role: "agent",
            text: String(ev.data.preview || ev.data.message || "[后台任务进行中]"),
            thinking: [],
            streaming: true,
          },
        ]
        notify(agentId)
      } else if (ev.event === "agent_done") {
        notify(agentId)
      }
    } catch {
      /* ignore */
    }
  }
  es.onerror = () => {
    es.close()
    agentEventSources.delete(agentId)
    window.setTimeout(() => connectAgentBackgroundEvents(agentId), 3000)
  }
}

export async function ensureAgentChatLoaded(agentId: string): Promise<void> {
  connectAgentBackgroundEvents(agentId)
  await syncAgentChatFromServer(agentId)
}

export async function sendAgentChatMessage(agentId: string, text: string): Promise<void> {
  const s = ensureSession(agentId)
  if (s.busy) return
  const trimmed = text.trim()
  if (!trimmed) return

  s.pendingText = trimmed
  s.userCancelled = false
  s.restoreDraft = ""
  s.error = ""

  const userId = `u_${Date.now()}`
  const agentMsgId = `a_${Date.now()}`
  s.activeTurn = { userId, agentMsgId }
  s.messages = [
    ...s.messages,
    { id: userId, role: "user", text: trimmed },
    { id: agentMsgId, role: "agent", text: "", thinking: [], streaming: true },
  ]

  const ac = new AbortController()
  s.abortCtrl = ac
  s.busy = true
  notify(agentId)

  let content = ""
  let thinkingEvents: ThinkingEvent[] = []

  try {
    await sendAgentChat(agentId, trimmed, (ev) => {
      if (ac.signal.aborted || s.userCancelled) return
      if (ev.event === "thinking") {
        const d = ev.data as ThinkingEvent
        if (d?.type === "step_finish" && d.tokens) accumulateContextTokens(agentId, d.tokens)
        const next = applyThinkingEvent(thinkingEvents, content, d as Record<string, unknown>)
        content = next.text
        thinkingEvents = next.thinking
        s.messages = s.messages.map((m) =>
          m.id === agentMsgId
            ? { ...m, text: content, thinking: [...thinkingEvents], streaming: true }
            : m,
        )
        notify(agentId)
      } else if (ev.event === "citations") {
        const cites = Array.isArray(ev.data) ? (ev.data as CitationPart[]) : []
        if (cites.length) {
          s.messages = s.messages.map((m) =>
            m.id === agentMsgId ? { ...m, citations: cites } : m,
          )
          notify(agentId)
        }
      } else if (ev.event === "error") {
        const d = ev.data as { message?: string }
        content = d?.message || "发生错误"
      } else if (ev.event === "done") {
        s.messages = s.messages.map((m) =>
          m.id === agentMsgId ? { ...m, streaming: false } : m,
        )
        notify(agentId)
      }
    }, ac.signal)

    if (!s.userCancelled) {
      s.messages = s.messages.map((m) =>
        m.id === agentMsgId
          ? {
              ...m,
              text: content || "（无回复）",
              thinking: [...thinkingEvents],
              streaming: false,
            }
          : m,
      )
      notify(agentId)
    }
  } catch (err) {
    if (!(isAbortError(err) && s.userCancelled)) {
      s.error = err instanceof Error ? err.message : "发送失败"
      s.messages = s.messages.filter((m) => m.id !== agentMsgId)
      notify(agentId)
    }
  } finally {
    const wasCancelled = s.userCancelled
    s.busy = false
    s.abortCtrl = null
    if (!wasCancelled) {
      s.activeTurn = null
      await syncAgentChatFromServer(agentId)
      emitSettled(agentId)
    } else {
      s.userCancelled = false
    }
    notify(agentId)
  }
}

/** 用户主动停止：先通知 Hub 取消活跃会话（→ RunRequest.cancel_event → 具体 CLIAdapter），再断开 SSE。 */
export function cancelAgentChatStream(agentId: string): void {
  const s = ensureSession(agentId)
  if (!s.busy && !s.abortCtrl) return
  s.userCancelled = true
  void cancelAgentChat(agentId).catch(() => {})
  s.abortCtrl?.abort()
  rollbackTurn(s)
  s.busy = false
  s.abortCtrl = null
  s.error = ""
  notify(agentId)
}
