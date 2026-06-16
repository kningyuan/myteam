import type { GroupMessage } from "@/lib/api/groups"
import {
  applyThinkingEvent,
  type ThinkingEvent,
} from "@/lib/thinking"

export type LiveAgentReply = {
  agentId: string
  replyTo: string
  thinking: ThinkingEvent[]
  text: string
  streaming: boolean
}

export type GroupReadReceipt = {
  msgId: string
  targets: string[]
  seen: string[]
  active?: string
}

export function liveReplyKey(replyTo: string, agentId: string): string {
  return `${replyTo}:${agentId}`
}

export function pendingAgentMessageId(replyTo: string, agentId: string): string {
  return `m_pending_${replyTo}_${agentId}`
}

export function mergeAgentDoneIntoMessages(
  msgs: GroupMessage[],
  replyTo: string,
  agentId: string,
  live: { text?: string; thinking?: ThinkingEvent[] },
): GroupMessage[] {
  const idx = msgs.findIndex(
    (m) => m.in_reply_to === replyTo && m.sender === agentId,
  )
  const thinking = live.thinking?.length ? live.thinking : undefined
  const text = live.text?.trim() ?? ""
  if (idx >= 0) {
    const cur = msgs[idx]
    const nextThinking = thinking?.length ? thinking : cur.thinking
    const nextText = text || cur.text
    if (nextThinking === cur.thinking && nextText === cur.text) return msgs
    const next = [...msgs]
    next[idx] = {
      ...cur,
      text: nextText,
      thinking: nextThinking?.length ? nextThinking : undefined,
    }
    return next
  }
  if (!text && !thinking?.length) return msgs
  return [
    ...msgs,
    {
      id: pendingAgentMessageId(replyTo, agentId),
      sender: agentId,
      text,
      timestamp: Date.now() / 1000,
      in_reply_to: replyTo,
      roundtable: true,
      thinking,
    },
  ]
}

export function mergeGroupMessages(
  prev: GroupMessage[],
  fromServer: GroupMessage[],
): GroupMessage[] {
  const byId = new Map<string, GroupMessage>()
  for (const m of prev) byId.set(m.id, m)
  for (const m of fromServer) {
    const pendingKey =
      m.in_reply_to && m.sender !== "user" && m.sender !== "system"
        ? pendingAgentMessageId(m.in_reply_to, m.sender)
        : null
    const pending = pendingKey ? byId.get(pendingKey) : undefined
    const thinking =
      m.thinking?.length
        ? m.thinking
        : pending?.thinking?.length
          ? pending.thinking
          : undefined
    byId.set(m.id, thinking?.length ? { ...m, thinking } : m)
    if (pendingKey) byId.delete(pendingKey)
  }
  return [...byId.values()].sort((a, b) => a.timestamp - b.timestamp)
}

export function flushLiveRepliesToMessages(
  prevMessages: GroupMessage[],
  liveReplies: Record<string, LiveAgentReply>,
): GroupMessage[] {
  let next = prevMessages
  for (const live of Object.values(liveReplies)) {
    if (!live.text.trim() && !live.thinking.length) continue
    next = mergeAgentDoneIntoMessages(next, live.replyTo, live.agentId, {
      text: live.text,
      thinking: live.thinking.length ? [...live.thinking] : undefined,
    })
  }
  return next
}

export function applyThinkingChunk(
  reply: LiveAgentReply,
  data: Record<string, unknown>,
): LiveAgentReply {
  const next = applyThinkingEvent(reply.thinking, reply.text, data)
  return { ...reply, thinking: next.thinking, text: next.text }
}

export function seenAgentsForMessage(msgId: string, messages: GroupMessage[]): string[] {
  const seen = messages
    .filter(
      (m) =>
        m.in_reply_to === msgId &&
        m.sender !== "user" &&
        m.sender !== "system",
    )
    .map((m) => m.sender)
  return [...new Set(seen)]
}

export function mergeReadReceipt(
  msg: GroupMessage,
  messages: GroupMessage[],
  active: GroupReadReceipt | null,
): GroupReadReceipt | null {
  const targets = msg.mentions?.length ? msg.mentions : []
  if (!targets.length) return null
  const persistedSeen = seenAgentsForMessage(msg.id, messages)
  if (active?.msgId === msg.id) {
    const seen = [...new Set([...persistedSeen, ...active.seen])]
    return {
      msgId: msg.id,
      targets: active.targets.length ? active.targets : targets,
      seen,
      active: active.active,
    }
  }
  if (!persistedSeen.length && !active) return null
  return { msgId: msg.id, targets, seen: persistedSeen }
}

export function resolveLiveForMessage(
  message: GroupMessage,
  liveReplies: Record<string, LiveAgentReply>,
): LiveAgentReply | undefined {
  if (
    message.sender === "user" ||
    message.sender === "system" ||
    message.thinking?.length ||
    !message.in_reply_to
  ) {
    return undefined
  }
  const live = liveReplies[liveReplyKey(message.in_reply_to, message.sender)]
  if (!live) return undefined
  if (!live.streaming && !live.thinking.length && !live.text.trim()) {
    return undefined
  }
  return live
}

export function shouldShowLiveReply(
  live: LiveAgentReply,
  messages: GroupMessage[],
): boolean {
  const hasPersisted = messages.some(
    (m) => m.in_reply_to === live.replyTo && m.sender === live.agentId,
  )
  if (hasPersisted) return false
  return live.streaming || live.thinking.length > 0 || live.text.trim().length > 0
}

/** 刷新后根据已落库消息 + Hub active 状态，恢复进行中的群聊回复 UI。 */
export function buildInflightGroupState(messages: GroupMessage[]): {
  activeTurn: { userMsgId: string; targets: string[] }
  liveReplies: Record<string, LiveAgentReply>
  readReceipt: GroupReadReceipt
  activeAgent?: string
} | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.sender !== "user" || !m.mentions?.length) continue
    const replied = seenAgentsForMessage(m.id, messages)
    const pending = m.mentions.filter((id) => !replied.includes(id))
    if (!pending.length) return null
    const liveReplies: Record<string, LiveAgentReply> = {}
    for (const agentId of pending) {
      liveReplies[liveReplyKey(m.id, agentId)] = {
        agentId,
        replyTo: m.id,
        thinking: [],
        text: "",
        streaming: true,
      }
    }
    return {
      activeTurn: { userMsgId: m.id, targets: m.mentions },
      liveReplies,
      readReceipt: {
        msgId: m.id,
        targets: m.mentions,
        seen: replied,
        active: pending[0],
      },
      activeAgent: pending[0],
    }
  }
  return null
}
