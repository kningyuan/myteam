import { invalidateResources } from "@/lib/dataRefresh"
import {
  hubFetch,
  parseSseDataLines,
  readStreamWithAbort,
} from "./client"

export type GroupMessage = {
  id: string
  sender: string
  text: string
  timestamp: number
  mentions?: string[]
  in_reply_to?: string
  roundtable?: boolean
  roundtable_consensus?: string
  roundtable_transcript?: string
  roundtable_user_decision_summary?: string
  roundtable_phase?: string
  roundtable_meta?: {
    artifact_type?: string
    agenda?: string
    facilitator?: string
    participants?: string[]
    cycles_run?: number
  }
  /** 圆桌 turn 元数据（status / error_code / duration_ms），由服务端持久化 */
  turn_meta?: {
    status?: "ok" | "failed"
    error_code?: string
    phase?: string
    round?: number
    duration_ms?: number
  }
  /** Agent 活动轨迹（工具调用等），圆桌 turn 由服务端持久化 */
  thinking?: {
    type: string
    content?: string
    name?: string
    input?: unknown
    output?: unknown
    tokens?: { input?: number; output?: number; total?: number }
  }[]
}

export type GroupSummary = {
  id: string
  name: string
  description?: string
  members?: string[]
  messages?: GroupMessage[]
  project_id?: string
  status?: string
  member_count?: number
  last_message?: string
  last_message_at?: number
  roundtable_facilitator?: string
  roundtable_max_rounds?: number
  roundtable_uses_global_max_rounds?: boolean
  agent_names?: Record<string, string>
}

export type GroupChatMode = "roundtable" | "notify"

/** @all → 圆桌；@一个或多个具体 Agent → 群聊回复（同私聊，展示在群内） */
export function detectGroupChatMode(text: string): GroupChatMode {
  if (/@(?:all|everyone)\b/i.test(text)) {
    return "roundtable"
  }
  return "notify"
}

export async function listGroups(): Promise<GroupSummary[]> {
  const data = await hubFetch<{ groups: GroupSummary[] }>("/api/groups")
  return data.groups ?? []
}

export async function getGroup(groupId: string): Promise<GroupSummary> {
  const data = await hubFetch<{ group: GroupSummary }>(`/api/groups/${encodeURIComponent(groupId)}`)
  return data.group
}

export function subscribeGroupEvents(
  groupId: string,
  onEvent: (payload: unknown) => void,
): () => void {
  const es = new EventSource(`/api/groups/${encodeURIComponent(groupId)}/events`)
  es.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data))
    } catch {
      /* ignore */
    }
  }
  return () => es.close()
}

export async function cancelGroupChat(groupId: string): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/cancel`, { method: "POST" })
}

export async function getGroupChatStatus(groupId: string): Promise<{ active: boolean }> {
  return hubFetch(`/api/groups/${encodeURIComponent(groupId)}/chat/status`)
}

export async function sendGroupChat(
  groupId: string,
  text: string,
  onEvent: (payload: Record<string, unknown>) => void,
  signal?: AbortSignal,
  mode?: GroupChatMode,
  rounds?: number,
): Promise<void> {
  const resolvedMode = mode ?? detectGroupChatMode(text)
  const params = new URLSearchParams({
    sender: "user",
    text,
    mode: resolvedMode,
  })
  if (rounds != null && rounds > 0) {
    params.set("rounds", String(rounds))
  }
  const url = `/api/groups/${encodeURIComponent(groupId)}/chat?${params.toString()}`
  const res = await fetch(url, { signal })
  if (!res.ok || !res.body) throw new Error(`${res.status}`)
  const dec = new TextDecoder()
  let buf = ""
  await readStreamWithAbort(res.body, signal, (value) => {
    if (signal?.aborted) return
    buf += dec.decode(value, { stream: true })
    buf = parseSseDataLines(buf, (raw) => {
      try {
        onEvent(JSON.parse(raw) as Record<string, unknown>)
      } catch {
        /* ignore */
      }
    })
  })
}

export async function createGroup(body: {
  name: string
  description?: string
  members?: string[]
  project_id?: string
}): Promise<{ group_id: string }> {
  const data = await hubFetch<{ group?: { id: string } }>("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: body.name,
      description: body.description,
      project_id: body.project_id,
    }),
  })
  const groupId = data.group?.id
  if (!groupId) throw new Error("创建群组失败")
  for (const agentId of body.members ?? []) {
    await addGroupMember(groupId, agentId, { skipInvalidate: true }).catch(() => {})
  }
  invalidateResources("groups")
  return { group_id: groupId }
}

export async function addGroupMember(
  groupId: string,
  agentId: string,
  opts?: { skipInvalidate?: boolean },
): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId }),
  })
  if (!opts?.skipInvalidate) invalidateResources("groups")
}

export async function removeGroupMember(groupId: string, agentId: string): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(agentId)}`, {
    method: "DELETE",
  })
  invalidateResources("groups")
}

export async function reorderGroupMembers(
  groupId: string,
  members: string[],
): Promise<GroupSummary> {
  const data = await hubFetch<{ group?: GroupSummary }>(
    `/api/groups/${encodeURIComponent(groupId)}/members/order`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ members }),
    },
  )
  if (!data.group) throw new Error("更新成员顺序失败")
  invalidateResources("groups")
  return data.group
}

export async function updateGroupRoundtableSettings(
  groupId: string,
  settings: { roundtable_facilitator?: string; roundtable_max_rounds?: number },
): Promise<GroupSummary> {
  const data = await hubFetch<{ group?: GroupSummary }>(
    `/api/groups/${encodeURIComponent(groupId)}/roundtable-settings`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    },
  )
  if (!data.group) throw new Error("更新圆桌设置失败")
  invalidateResources("groups")
  return data.group
}

export async function clearGroupChat(groupId: string): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/clear`, { method: "POST" })
  invalidateResources("groups")
}

export async function dissolveGroup(groupId: string): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/dissolve`, { method: "POST" })
  invalidateResources("groups")
}

export async function restoreGroup(groupId: string): Promise<void> {
  await hubFetch(`/api/groups/${encodeURIComponent(groupId)}/restore`, { method: "POST" })
  invalidateResources("groups")
}

export async function searchGroups(
  q: string,
  includeDissolved = true,
): Promise<GroupSummary[]> {
  const data = await hubFetch<{ groups?: GroupSummary[] }>(
    `/api/groups/search?q=${encodeURIComponent(q)}&include_dissolved=${includeDissolved}`,
  )
  return data.groups ?? []
}
