import { invalidateResources } from "@/lib/dataRefresh"
import {
  hubFetch,
  parseSseLineBuffer,
  readStreamWithAbort,
} from "./client"
import type { GroupMessage } from "./groups"

export type ChatMessage = {
  seq?: number
  role: string
  author?: string
  text: string
  created_at?: string
  /** Agent 思考链，由 Hub 落库并在 GET messages 返回 */
  thinking?: GroupMessage["thinking"]
}

export type ChatArchiveEntry = {
  agent_id: string
  label?: string
  hidden_at?: number
}

export async function cancelAgentChat(agentId: string): Promise<void> {
  await hubFetch(`/api/chat/${encodeURIComponent(agentId)}/cancel`, { method: "POST" })
}

export async function getAgentChatStatus(agentId: string): Promise<{ active: boolean }> {
  return hubFetch(`/api/chat/${encodeURIComponent(agentId)}/status`)
}

export async function getAgentChatMessages(agentId: string): Promise<ChatMessage[]> {
  const data = await hubFetch<{ messages?: ChatMessage[] }>(
    `/api/chat/${encodeURIComponent(agentId)}/messages`,
  )
  return data.messages ?? []
}

export async function sendAgentChat(
  agentId: string,
  message: string,
  onChunk: (event: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `/api/chat/${encodeURIComponent(agentId)}?message=${encodeURIComponent(message)}`
  const res = await fetch(url, { signal })
  if (!res.ok || !res.body) throw new Error(`${res.status}`)
  const dec = new TextDecoder()
  let buf = ""
  await readStreamWithAbort(res.body, signal, (value) => {
    if (signal?.aborted) return
    buf += dec.decode(value, { stream: true })
    buf = parseSseLineBuffer(buf, (raw) => {
      try {
        onChunk(JSON.parse(raw) as Record<string, unknown>)
      } catch {
        /* ignore */
      }
    })
  })
}

export async function clearAgentChat(agentId: string): Promise<void> {
  await hubFetch(`/api/chat/${encodeURIComponent(agentId)}/clear`, { method: "POST" })
  invalidateResources("agents")
}

export async function archiveAgentChat(
  agentId: string,
  snapshot: { label?: string; messages: { role: string; content?: string; text?: string }[] },
): Promise<void> {
  await hubFetch(`/api/chat/${encodeURIComponent(agentId)}/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot }),
  })
  invalidateResources("agents")
}

export async function restoreAgentChat(agentId: string): Promise<{
  snapshot?: { messages?: ChatMessage[] }
}> {
  const data = await hubFetch<{ snapshot?: { messages?: ChatMessage[] } }>(
    `/api/chat/${encodeURIComponent(agentId)}/restore`,
    { method: "POST" },
  )
  invalidateResources("agents")
  return data
}

export async function searchChatArchives(q: string): Promise<ChatArchiveEntry[]> {
  const data = await hubFetch<{ results?: ChatArchiveEntry[] }>(
    `/api/chat/archives/search?q=${encodeURIComponent(q)}`,
  )
  return data.results ?? []
}
