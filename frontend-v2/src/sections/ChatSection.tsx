import { useEffect, useMemo, useReducer, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { listAgents } from "@/lib/api/agents"
import {
  restoreAgentChat,
  searchChatArchives,
  type ChatArchiveEntry,
} from "@/lib/api/chat"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { isAgentStreamBusy, subscribeAgentChatGlobal } from "@/lib/agentChatStream"
import { formatRelativeTime } from "@/lib/thinking"
import { AgentChatPanel } from "@/components/chat/AgentChatPanel"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"

export function ChatSection() {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const { data: agents } = useResourceQuery("agents", listAgents, [])
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState("")
  const [archiveHits, setArchiveHits] = useState<ChatArchiveEntry[]>([])
  const [, streamTick] = useReducer((x: number) => x + 1, 0)

  useEffect(() => subscribeAgentChatGlobal(streamTick), [])

  useEffect(() => {
    searchChatArchives("")
      .then((rows) => setHiddenIds(new Set(rows.map((r) => r.agent_id))))
      .catch(() => setHiddenIds(new Set()))
  }, [])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setArchiveHits([])
      return
    }
    const t = setTimeout(() => {
      searchChatArchives(q)
        .then(setArchiveHits)
        .catch(() => setArchiveHits([]))
    }, 200)
    return () => clearTimeout(t)
  }, [query])

  const visible = useMemo(() => {
    return agents.filter((a) => !hiddenIds.has(a.id))
  }, [agents, hiddenIds])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const base = q
      ? visible.filter(
          (a) => a.name?.toLowerCase().includes(q) || a.id.toLowerCase().includes(q),
        )
      : visible
    return [...base].sort(
      (a, b) => (b.last_message_at || 0) - (a.last_message_at || 0),
    )
  }, [visible, query])

  const current = agents.find((a) => a.id === agentId)

  async function restoreArchived(id: string) {
    try {
      await restoreAgentChat(id)
      setHiddenIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      setArchiveHits([])
      setQuery("")
      navigate(`/chat/${encodeURIComponent(id)}`)
    } catch {
      /* toast handled by panel if needed */
    }
  }

  return (
    <DiscordShell
      list={
        <ListColumn
          title="Agent 对话"
          search={
            <input
              placeholder="搜索 Agent 或归档…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          }
        >
          {archiveHits.length > 0 && (
            <div className="search-results">
              {archiveHits.map((hit) => (
                <div
                  key={hit.agent_id}
                  className="search-result-item"
                  onClick={() => restoreArchived(hit.agent_id)}
                  onKeyDown={(e) => e.key === "Enter" && restoreArchived(hit.agent_id)}
                  role="button"
                  tabIndex={0}
                >
                  <div>{hit.label || hit.agent_id}</div>
                  <div className="sub">{hit.agent_id} · 点击恢复归档</div>
                </div>
              ))}
            </div>
          )}
          {filtered.map((a) => (
            <ListItemRow
              key={a.id}
              name={a.name || a.id}
              sub={
                isAgentStreamBusy(a.id)
                  ? "处理中…"
                  : a.last_message_preview
                    ? `${a.last_message_preview.slice(0, 48)}${a.last_message_preview.length > 48 ? "…" : ""}${
                        a.last_message_at ? ` · ${formatRelativeTime(a.last_message_at)}` : ""
                      }`
                    : a.id
              }
              avatar={a.name || a.id}
              active={a.id === agentId}
              onClick={() => navigate(`/chat/${encodeURIComponent(a.id)}`)}
            />
          ))}
        </ListColumn>
      }
    >
      {current ? (
        <AgentChatPanel
          agent={current}
          onArchived={() => {
            setHiddenIds((prev) => new Set(prev).add(current.id))
            navigate("/chat")
          }}
        />
      ) : (
        <WelcomePane
          title="选择一个 Agent 开始对话"
          description="左侧列出团队中的 AI 成员。支持流式回复、Markdown、清空/归档对话，以及 Agent 后端与模型配置。"
        />
      )}
    </DiscordShell>
  )
}
