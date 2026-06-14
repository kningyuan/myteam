import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { MoreVertical, ChevronDown, ChevronUp } from "lucide-react"
import { toast } from "sonner"
import { isAbortError } from "@/lib/api/client"
import { getAgentRegistry, listAgents } from "@/lib/api/agents"
import { getSkillConfig } from "@/lib/api/config"
import {
  addGroupMember,
  cancelGroupChat,
  clearGroupChat,
  createGroup,
  detectGroupChatMode,
  dissolveGroup,
  getGroup,
  getGroupChatStatus,
  listGroups,
  removeGroupMember,
  reorderGroupMembers,
  restoreGroup,
  searchGroups,
  sendGroupChat,
  subscribeGroupEvents,
  updateGroupRoundtableSettings,
  type GroupMessage,
  type GroupSummary,
} from "@/lib/api/groups"
import { useResourceQuery, useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { invalidateResources } from "@/lib/dataRefresh"
import {
  agentDisplayName,
  buildAgentNameLookup,
  formatMemberList,
  roundtablePhaseLabel,
} from "@/lib/agentLabels"
import {
  GroupLiveAgentBubble,
  GroupMessageBubble,
  GroupReadReceiptRow,
} from "@/components/chat/GroupMessageBubble"
import { formatRelativeTime } from "@/lib/thinking"
import {
  DEFAULT_GROUP_DISCUSSION_SETTINGS,
  effectiveGroupMaxRounds,
  groupChatInputPlaceholder,
  parseGroupDiscussionSettings,
  primaryTerminateCommand,
  type GroupDiscussionSettings,
} from "@/lib/groupDiscussionSettings"
import {
  applyThinkingChunk,
  liveReplyKey,
  mergeGroupMessages,
  mergeReadReceipt,
  flushLiveRepliesToMessages,
  resolveLiveForMessage,
  seenAgentsForMessage,
  shouldShowLiveReply,
  type GroupReadReceipt,
  type LiveAgentReply,
} from "@/lib/groupChatLive"
import { useImeCompositionGuard } from "@/lib/ime"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

function GroupMoreMenu({
  onClear,
  onDissolve,
  onMembers,
}: {
  onClear: () => void
  onDissolve: () => void
  onMembers: () => void
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
          <button type="button" onClick={() => { setOpen(false); onMembers() }}>
            成员管理
          </button>
          <button type="button" onClick={() => { setOpen(false); onClear() }}>
            清空消息
          </button>
          <button type="button" className="danger" onClick={() => { setOpen(false); onDissolve() }}>
            解散群组
          </button>
        </div>
      )}
    </div>
  )
}

const GROUP_CHAT_INPUT_MIN = 120
const GROUP_CHAT_INPUT_MAX = 240

function GroupChatPanel({ groupId }: { groupId: string }) {
  const navigate = useNavigate()
  const [group, setGroup] = useState<GroupSummary | null>(null)
  const [messages, setMessages] = useState<GroupMessage[]>([])
  const [draft, setDraft] = useState("")
  const [error, setError] = useState("")
  const [sending, setSending] = useState(false)
  const [membersOpen, setMembersOpen] = useState(false)
  const [agentRegistry, setAgentRegistry] = useState<
    Record<string, { name?: string }>
  >({})
  const [mentionOpen, setMentionOpen] = useState(false)
  const [mentionFilter, setMentionFilter] = useState("")
  const [activeAgent, setActiveAgent] = useState("")
  const [roundtableProgress, setRoundtableProgress] = useState<{
    index: number
    total: number
    round?: number
    phase?: string
    facilitator?: string
  } | null>(null)
  const [liveReplies, setLiveReplies] = useState<Record<string, LiveAgentReply>>({})
  const [readReceipt, setReadReceipt] = useState<GroupReadReceipt | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const messagesScrollRef = useRef<HTMLDivElement>(null)
  /** 用户在底部附近时为 true；上滑阅读历史时不再强制滚到底 */
  const stickToBottomRef = useRef(true)
  const [atBottom, setAtBottom] = useState(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const userCancelledRef = useRef(false)
  const roundtableActiveRef = useRef(false)
  const notifyBgRef = useRef(false)
  const pendingTextRef = useRef("")
  const [roundtableBackground, setRoundtableBackground] = useState(false)
  const [gdSettings, setGdSettings] = useState<GroupDiscussionSettings>(
    DEFAULT_GROUP_DISCUSSION_SETTINGS,
  )
  const activeTurnRef = useRef({ userMsgId: "", targets: [] as string[] })
  const { compositionProps, isImeComposing } = useImeCompositionGuard()

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const reload = useCallback(() => {
    getGroup(groupId)
      .then((g) => {
        setGroup(g)
        setMessages((prev) => mergeGroupMessages(prev, g.messages ?? []))
      })
      .catch((e: Error) => setError(e.message))
  }, [groupId])

  useOnResourceInvalidate("groups", reload)

  const { data: allAgents } = useResourceQuery("agents", listAgents, [])

  useEffect(() => {
    stickToBottomRef.current = true
    setAtBottom(true)
    reload()
    getAgentRegistry()
      .then((reg) => setAgentRegistry(reg.agents ?? {}))
      .catch(() => setAgentRegistry({}))
    getGroupChatStatus(groupId)
      .then((s) => {
        if (s.active) {
          roundtableActiveRef.current = true
          setRoundtableBackground(true)
          setSending(true)
        }
      })
      .catch(() => {})
    getSkillConfig()
      .then((skill) => setGdSettings(parseGroupDiscussionSettings(skill)))
      .catch(() => {})
  }, [reload, groupId])

  const SCROLL_STICK_THRESHOLD = 80

  const updateStickToBottom = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const near = distanceFromBottom <= SCROLL_STICK_THRESHOLD
    stickToBottomRef.current = near
    setAtBottom(near)
  }, [])

  const scrollToBottom = useCallback(() => {
    stickToBottomRef.current = true
    setAtBottom(true)
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, liveReplies, readReceipt])

  const nameLookup = useMemo(
    () => buildAgentNameLookup(allAgents, agentRegistry, group?.agent_names),
    [allAgents, agentRegistry, group?.agent_names],
  )

  const effectiveMaxRounds = useMemo(
    () => effectiveGroupMaxRounds(group?.roundtable_max_rounds, gdSettings),
    [group?.roundtable_max_rounds, gdSettings],
  )

  const inputPlaceholder = useMemo(
    () => groupChatInputPlaceholder(gdSettings),
    [gdSettings],
  )

  const nameFor = useCallback(
    (id: string) => agentDisplayName(id, nameLookup),
    [nameLookup],
  )

  const applyStreamEvent = useCallback((evt: Record<string, unknown>) => {
    const event = String(evt.event || "")
    const data = (evt.data || {}) as Record<string, unknown>

    if (event === "group_message") {
      const msgId = String(data.msg_id || "")
      const mentions = Array.isArray(data.mentions) ? (data.mentions as string[]) : []
      const sender = String(data.sender || "user")
      const msgText = String(data.text || "")
      const timestamp = Number(data.timestamp || Date.now() / 1000)
      if (msgText) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === msgId)) return prev
          return [
            ...prev,
            {
              id: msgId || `m_${Date.now()}`,
              sender,
              text: msgText,
              timestamp,
              mentions: mentions.length ? mentions : undefined,
            },
          ]
        })
      }
      if (mentions.length && sender === "user") {
        activeTurnRef.current = { userMsgId: msgId, targets: mentions }
        setReadReceipt({ msgId, targets: mentions, seen: [], active: undefined })
      }
    }
    if (event === "roundtable_detached") {
      roundtableActiveRef.current = true
      setRoundtableBackground(true)
      setSending(true)
    }
    if (event === "notify_detached") {
      roundtableActiveRef.current = true
      notifyBgRef.current = true
      setRoundtableBackground(true)
      setSending(true)
    }
    if (event === "roundtable_start") {
      const speakers = Array.isArray(data.speakers) ? (data.speakers as string[]) : []
      const rtMsgId = String(data.msg_id || "")
      const msgId = rtMsgId || activeTurnRef.current.userMsgId
      const facilitator = String(data.facilitator || "")
      const maxRounds = Number(data.max_rounds || 0)
      if (msgId && speakers.length) {
        activeTurnRef.current = { userMsgId: msgId, targets: speakers }
        setReadReceipt({ msgId, targets: speakers, seen: [], active: undefined })
      }
      setRoundtableProgress({
        index: 0,
        total: speakers.length,
        round: 1,
        phase: "opening",
        facilitator,
      })
      if (facilitator) {
        setGroup((prev) =>
          prev ? { ...prev, roundtable_facilitator: facilitator, roundtable_max_rounds: maxRounds || prev.roundtable_max_rounds } : prev,
        )
      }
    }
    if (event === "group_cleared") {
      setMessages([])
      setLiveReplies({})
      setReadReceipt(null)
      setRoundtableProgress(null)
      return
    }
    if (event === "roundtable_phase") {
      const phase = String(data.phase || "")
      const count = Number(data.speaker_count || 0)
      setRoundtableProgress({
        index: 0,
        total: count || 1,
        round: 0,
        phase,
      })
    }
    if (event === "roundtable_round") {
      const round = Number(data.round || 0)
      const phase = String(data.phase || "")
      setRoundtableProgress((prev) =>
        prev
          ? { ...prev, round, phase }
          : { index: 0, total: 1, round, phase },
      )
    }
    if (event === "roundtable_turn") {
      const index = Number(data.index || 0)
      const total = Number(data.total || 0)
      const round = Number(data.round || 0)
      const phase = String(data.phase || "")
      if (index > 0 && total > 0) {
        setRoundtableProgress((prev) => ({
          index,
          total,
          round: round || prev?.round,
          phase: phase || prev?.phase,
          facilitator: prev?.facilitator,
        }))
      }
    }
    if (event === "roundtable_done") {
      setRoundtableProgress(null)
    }
    if (event === "roundtable_turn_failed") {
      const agentId = String(data.agent_id || "")
      const phase = String(data.phase || "")
      const message = String(data.message || data.error_code || "发言失败")
      toast.error(`圆桌发言失败：${nameFor(agentId || "agent")}`, {
        description: `${phase} · ${message}`.slice(0, 240),
      })
      reload()
    }
    if (event === "roundtable_aborted") {
      roundtableActiveRef.current = false
      setRoundtableBackground(false)
      setSending(false)
      setRoundtableProgress(null)
      setActiveAgent("")
      const reason = String(data.reason || "")
      if (reason === "user_terminate") {
        const killed = Array.isArray(data.killed_pids) ? data.killed_pids.length : 0
        toast.info("讨论已终止", {
          description: killed ? `已停止后台进程 ${killed} 个` : undefined,
        })
      }
      reload()
    }
    if (event === "routing") {
      const agentId = String(data.to || "")
      if (agentId) {
        setActiveAgent(agentId)
        const replyTo = activeTurnRef.current.userMsgId
        if (replyTo) {
          const key = liveReplyKey(replyTo, agentId)
          setLiveReplies((prev) => ({
            ...prev,
            [key]: prev[key] ?? {
              agentId,
              replyTo,
              thinking: [],
              text: "",
              streaming: true,
            },
          }))
          setReadReceipt((prev) =>
            prev ? { ...prev, active: agentId } : prev,
          )
        }
      }
    }
    if (event === "agent_thinking") {
      const agentId = String(data.agent_id || "")
      const replyTo =
        String(data.reply_to || "") || activeTurnRef.current.userMsgId
      if (!agentId || !replyTo) return
      const key = liveReplyKey(replyTo, agentId)
      setLiveReplies((prev) => {
        const cur =
          prev[key] ??
          ({
            agentId,
            replyTo,
            thinking: [],
            text: "",
            streaming: true,
          } satisfies LiveAgentReply)
        return { ...prev, [key]: applyThinkingChunk(cur, data) }
      })
      setActiveAgent(agentId)
    }
    if (event === "agent_done") {
      const agentId = String(data.agent_id || "")
      const replyTo =
        String(data.reply_to || "") || activeTurnRef.current.userMsgId
      if (agentId) {
        setReadReceipt((prev) => {
          if (!prev) return prev
          const seen = prev.seen.includes(agentId)
            ? prev.seen
            : [...prev.seen, agentId]
          return {
            ...prev,
            seen,
            active: prev.active === agentId ? undefined : prev.active,
          }
        })
      }
      reload()
      invalidateResources("groups")
      if (replyTo && agentId) {
        const key = liveReplyKey(replyTo, agentId)
        setLiveReplies((prev) => {
          if (!prev[key]) return prev
          const next = { ...prev }
          delete next[key]
          return next
        })
      }
      if (notifyBgRef.current) {
        notifyBgRef.current = false
        roundtableActiveRef.current = false
        setRoundtableBackground(false)
        setSending(false)
        setActiveAgent("")
      }
    }
    if (event === "roundtable_done" || event === "done") {
      roundtableActiveRef.current = false
      notifyBgRef.current = false
      setRoundtableBackground(false)
      setSending(false)
      setActiveAgent("")
      setRoundtableProgress(null)
      setLiveReplies((prev) => {
        if (Object.keys(prev).length) {
          setMessages((msgs) => flushLiveRepliesToMessages(msgs, prev))
        }
        return {}
      })
      reload()
      invalidateResources("groups")
      setReadReceipt(null)
      activeTurnRef.current = { userMsgId: "", targets: [] }
    }
  }, [reload, nameFor])

  useEffect(() => {
    return subscribeGroupEvents(groupId, (payload) => {
      applyStreamEvent(payload as Record<string, unknown>)
    })
  }, [groupId, applyStreamEvent])

  const members = group?.members ?? []
  const mentionCandidates = filterMentions(members, nameLookup, mentionFilter)

  const moveMember = async (agentId: string, direction: -1 | 1) => {
    const idx = members.indexOf(agentId)
    if (idx < 0) return
    const target = idx + direction
    if (target < 0 || target >= members.length) return
    const next = [...members]
    ;[next[idx], next[target]] = [next[target], next[idx]]
    try {
      const updated = await reorderGroupMembers(groupId, next)
      setGroup(updated)
      toast.success("发言顺序已更新")
    } catch (err) {
      toast.error("调整顺序失败", {
        description: err instanceof Error ? err.message : "",
      })
    }
  }

  function resizeInput() {
    const el = inputRef.current
    if (!el) return
    el.style.height = "auto"
    const next = Math.max(el.scrollHeight, GROUP_CHAT_INPUT_MIN)
    el.style.height = `${Math.min(next, GROUP_CHAT_INPUT_MAX)}px`
  }

  useEffect(() => {
    requestAnimationFrame(resizeInput)
  }, [])

  function updateDraft(value: string) {
    setDraft(value)
    requestAnimationFrame(resizeInput)
    const at = value.lastIndexOf("@")
    if (at >= 0 && (at === 0 || /\s/.test(value[at - 1] ?? ""))) {
      const tail = value.slice(at + 1)
      if (!tail.includes(" ")) {
        setMentionFilter(tail.toLowerCase())
        setMentionOpen(true)
        return
      }
    }
    setMentionOpen(false)
  }

  function insertMention(name: string) {
    const el = inputRef.current
    const at = draft.lastIndexOf("@")
    if (at < 0) return
    const token = name === "all" ? "all" : name
    const next = `${draft.slice(0, at)}@${token} ${draft.slice(at + 1 + mentionFilter.length)}`
    setDraft(next)
    setMentionOpen(false)
    el?.focus()
  }

  function rollbackGroupSend(text: string) {
    setDraft(pendingTextRef.current)
    requestAnimationFrame(resizeInput)
    setMessages((prev) => {
      const next = [...prev]
      const lastUserIdx = next.map((m, i) => ({ m, i })).reverse().find(({ m }) => m.sender === "user")?.i
      if (lastUserIdx != null && next[lastUserIdx]?.text === text) next.splice(lastUserIdx, 1)
      return [
        ...next,
        {
          id: `sys_${Date.now()}`,
          sender: "system",
          text: "已中断",
          timestamp: Date.now() / 1000,
        },
      ]
    })
  }

  function handleCancel() {
    if (!sending && !abortRef.current && !roundtableActiveRef.current) return
    userCancelledRef.current = true
    void cancelGroupChat(groupId).catch(() => {})
    abortRef.current?.abort()
    if (pendingTextRef.current) rollbackGroupSend(pendingTextRef.current)
    roundtableActiveRef.current = false
    notifyBgRef.current = false
    setRoundtableBackground(false)
    setSending(false)
    setActiveAgent("")
    setRoundtableProgress(null)
    setError("")
  }

  async function handleTerminateDiscussion() {
    if (!sending && !roundtableActiveRef.current) return
    const text = primaryTerminateCommand(gdSettings)
    userCancelledRef.current = false
    stickToBottomRef.current = true
    setAtBottom(true)
    setMessages((prev) => [
      ...prev,
      {
        id: `u_term_${Date.now()}`,
        sender: "user",
        text,
        timestamp: Date.now() / 1000,
        mentions: [],
      },
    ])
    try {
      await sendGroupChat(groupId, text, (evt) => applyStreamEvent(evt))
    } catch (err) {
      if (!isAbortError(err)) {
        toast.error("终止失败", {
          description: err instanceof Error ? err.message : "",
        })
      }
    } finally {
      roundtableActiveRef.current = false
      notifyBgRef.current = false
      setRoundtableBackground(false)
      setSending(false)
      setActiveAgent("")
      setRoundtableProgress(null)
      abortRef.current?.abort()
      abortRef.current = null
      reload()
    }
  }

  const sendModeHint = draft.trim() ? detectGroupChatMode(draft) : null

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (sending || roundtableActiveRef.current) return
    const text = draft.trim()
    if (!text) return
    stickToBottomRef.current = true
    setAtBottom(true)
    const mode = detectGroupChatMode(text)
    pendingTextRef.current = text
    userCancelledRef.current = false
    roundtableActiveRef.current = false
    notifyBgRef.current = false
    const ac = new AbortController()
    abortRef.current = ac
    setSending(true)
    setActiveAgent("")
    setRoundtableProgress(null)
    setLiveReplies({})
    setDraft("")
    setMentionOpen(false)
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (el) el.style.height = "auto"
    })
    try {
      await sendGroupChat(
        groupId,
        text,
        (evt) => {
          if (ac.signal.aborted) return
          applyStreamEvent(evt)
        },
        ac.signal,
        mode,
        effectiveMaxRounds,
      )
      if (!roundtableActiveRef.current) reload()
    } catch (err) {
      if (isAbortError(err) && userCancelledRef.current) {
        /* UI 已在 handleCancel 中回滚 */
      } else if (isAbortError(err) && roundtableActiveRef.current) {
        /* 圆桌/派活已切后台，fetch 断开不影响 */
      } else {
        setError(err instanceof Error ? err.message : "发送失败")
      }
    } finally {
      if (!roundtableActiveRef.current) {
        setSending(false)
        setActiveAgent("")
        setRoundtableProgress(null)
      }
      abortRef.current = null
      if (!roundtableActiveRef.current) {
        userCancelledRef.current = false
      }
    }
  }

  async function handleClear() {
    if (!window.confirm("清空群组内所有消息？")) return
    try {
      await clearGroupChat(groupId)
      setMessages([])
      toast.success("消息已清空")
    } catch (e) {
      toast.error("清空失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleDissolve() {
    if (!window.confirm("解散该群组？可在搜索中恢复，不会删除项目数据。")) return
    try {
      await dissolveGroup(groupId)
      toast.success("群组已解散")
      navigate("/groups")
    } catch (e) {
      toast.error("解散失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <header className="chat-header-bar">
        <div className="min-w-0">
          <div className="font-semibold truncate">{group?.name || groupId}</div>
          <div className="text-xs text-[var(--color-muted-foreground)] truncate">
            成员：{formatMemberList(members, nameLookup) || "—"}
            {group?.roundtable_facilitator
              ? ` · 主持人 ${nameFor(group.roundtable_facilitator)}`
              : ""}
            {` · 圆桌 ${effectiveMaxRounds} 轮`}
            {group?.roundtable_uses_global_max_rounds
              ? `（全局默认 ${gdSettings.defaultMaxRounds}）`
              : ""}
            {group?.project_id ? ` · 项目 ${group.project_id}` : ""}
          </div>
        </div>
        <GroupMoreMenu
          onClear={handleClear}
          onDissolve={handleDissolve}
          onMembers={() => setMembersOpen(true)}
        />
      </header>
      <div className="chat-messages-wrap">
        <div
          className="chat-messages"
          ref={messagesScrollRef}
          onScroll={updateStickToBottom}
        >
        {error && (
          <div className="mb-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}
        {messages.map((m) => {
          const receipt =
            m.sender === "user" && (m.mentions?.length || seenAgentsForMessage(m.id, messages).length)
              ? mergeReadReceipt(m, messages, readReceipt)
              : null
          const liveOverlay = resolveLiveForMessage(m, liveReplies)
          return (
            <div key={m.id} className="group-msg-block">
              <GroupMessageBubble message={m} agentName={nameFor} live={liveOverlay} />
              {receipt ? (
                <GroupReadReceiptRow
                  targets={receipt.targets}
                  seen={receipt.seen}
                  active={receipt.active}
                  agentName={nameFor}
                />
              ) : null}
            </div>
          )
        })}
        {Object.values(liveReplies)
          .filter((live) => shouldShowLiveReply(live, messages))
          .map((live) => (
            <div key={liveReplyKey(live.replyTo, live.agentId)} className="group-msg-block">
              <GroupLiveAgentBubble live={live} agentName={nameFor} />
            </div>
          ))}
        {sending && roundtableBackground && !roundtableProgress && !activeAgent && (
          <div className="group-msg-row system">
            <div className="group-msg-system-pill">
              群聊任务后台进行中（刷新可继续观看，进度会通过事件推送）
            </div>
          </div>
        )}
        {sending && roundtableProgress && !activeAgent && (
          <div className="group-msg-row system">
            <div className="group-msg-system-pill">
              圆桌 {roundtablePhaseLabel(roundtableProgress.phase)}
              {roundtableProgress.round ? ` · 第 ${roundtableProgress.round} 轮` : ""}
              {roundtableBackground ? " · 后台进行中（刷新可继续观看）" : ""}
            </div>
          </div>
        )}
        {sending && roundtableBackground && !roundtableProgress && activeAgent && (
          <div className="group-msg-row system">
            <div className="group-msg-system-pill">
              @{nameFor(activeAgent)} 执行中
              {roundtableBackground ? " · 后台进行中（刷新可继续观看）" : ""}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
        </div>
        {!atBottom && (
          <button
            type="button"
            className="chat-jump-bottom"
            onClick={scrollToBottom}
            aria-label="滚动到最新消息"
          >
            有新消息 ↓
          </button>
        )}
      </div>
      <form className="chat-input-bar group-chat-compose" onSubmit={handleSend}>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[var(--color-muted-foreground)]">
          {sendModeHint && (
            <span>
              {sendModeHint === "roundtable"
                ? `@all 圆桌讨论（全员 · 最多 ${effectiveMaxRounds} 轮${
                    group?.roundtable_uses_global_max_rounds ? " · 全局默认" : ""
                  }${
                    group?.roundtable_facilitator
                      ? ` · 主持 ${nameFor(group.roundtable_facilitator)}`
                      : members[0]
                        ? ` · 默认主持 ${nameFor(members[0])}`
                        : ""
                  }）`
                : "→ @Agent 群聊回复（同私聊，展示在群内）"}
            </span>
          )}
        </div>
        <div className="chat-input-wrap">
          {mentionOpen && mentionCandidates.length > 0 && (
            <div className="mention-dropdown">
              {mentionCandidates.map((m) => (
                <button key={m} type="button" className="mention-item" onClick={() => insertMention(m)}>
                  @{nameFor(m)}
                </button>
              ))}
            </div>
          )}
          <textarea
            ref={inputRef}
            rows={3}
            placeholder={inputPlaceholder}
            value={draft}
            onChange={(e) => updateDraft(e.target.value)}
            {...compositionProps}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !isImeComposing(e)) {
                e.preventDefault()
                if (sending || roundtableActiveRef.current) return
                void handleSend(e)
              }
            }}
          />
        </div>
        {sending ? (
          <div className="flex shrink-0 flex-col gap-1">
            {roundtableBackground && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="chat-send-stop"
                onClick={() => void handleTerminateDiscussion()}
              >
                {primaryTerminateCommand(gdSettings)}
              </Button>
            )}
            <Button type="button" className="chat-send-stop" onClick={handleCancel}>
              停止
            </Button>
          </div>
        ) : (
          <Button type="submit" disabled={!draft.trim()}>
            发送
          </Button>
        )}
      </form>

      <Dialog open={membersOpen} onOpenChange={setMembersOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>群成员与圆桌设置</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 border-b border-[var(--color-border)] pb-4">
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)]/30 px-3 py-2 text-xs text-[var(--color-muted-foreground)]">
              <div className="mb-1 font-medium text-[var(--color-foreground)]">全局群配置</div>
              <div>默认 {gdSettings.defaultMaxRounds} 轮 · 上限 {gdSettings.maxRoundsCap} 轮 · 单轮超时 {gdSettings.turnTimeoutSec}s</div>
              <div>参与率 ≥ {Math.round(gdSettings.quorumRatio * 100)}% · 终止命令：{gdSettings.terminateCommands.join("、")}</div>
              <Link to="/settings/group" className="mt-1 inline-block text-[var(--color-brand)] hover:underline">
                在设置 → 群配置 中修改
              </Link>
            </div>
            <Label>圆桌主持人</Label>
            <select
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm"
              value={group?.roundtable_facilitator || "main"}
              onChange={async (e) => {
                try {
                  const updated = await updateGroupRoundtableSettings(groupId, {
                    roundtable_facilitator: e.target.value,
                  })
                  setGroup(updated)
                  toast.success("主持人已更新")
                } catch (err) {
                  toast.error("更新失败", {
                    description: err instanceof Error ? err.message : "",
                  })
                }
              }}
            >
              {members
                .filter((m) => m !== "user")
                .map((m) => (
                  <option key={m} value={m}>
                    {nameFor(m)}
                  </option>
                ))}
            </select>
            <Label>本群最大讨论轮数（1–{gdSettings.maxRoundsCap}）</Label>
            <Input
              type="number"
              min={1}
              max={gdSettings.maxRoundsCap}
              value={group?.roundtable_max_rounds ?? gdSettings.defaultMaxRounds}
              onChange={async (e) => {
                const n = Number(e.target.value)
                if (!Number.isFinite(n) || n < 1 || n > gdSettings.maxRoundsCap) return
                try {
                  const updated = await updateGroupRoundtableSettings(groupId, {
                    roundtable_max_rounds: n,
                  })
                  setGroup(updated)
                } catch (err) {
                  toast.error("更新失败", {
                    description: err instanceof Error ? err.message : "",
                  })
                }
              }}
            />
            <p className="text-xs text-[var(--color-muted-foreground)]">
              未保存单群轮数时使用全局默认 {gdSettings.defaultMaxRounds} 轮。每轮含主持汇总；若有分歧会插入对齐轮。
            </p>
          </div>
          <div className="space-y-1 pb-2">
            <Label>成员与发言顺序</Label>
            <p className="text-xs text-[var(--color-muted-foreground)]">
              从上到下为圆桌立论/对齐轮发言顺序（主持人除外）。
            </p>
          </div>
          <div className="max-h-64 space-y-2 overflow-y-auto py-1">
            {members.map((m, index) => (
              <div key={m} className="flex items-center justify-between gap-2 text-sm">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="w-5 shrink-0 text-xs text-[var(--color-muted-foreground)]">
                    {m === "user" ? "—" : index + 1}
                  </span>
                  <span className="truncate">{nameFor(m)}</span>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {m !== "user" && (
                    <>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 px-0"
                        disabled={index === 0 || members[index - 1] === "user"}
                        aria-label={`${nameFor(m)} 上移`}
                        onClick={() => void moveMember(m, -1)}
                      >
                        <ChevronUp className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 px-0"
                        disabled={index >= members.length - 1}
                        aria-label={`${nameFor(m)} 下移`}
                        onClick={() => void moveMember(m, 1)}
                      >
                        <ChevronDown className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await removeGroupMember(groupId, m)
                            reload()
                            toast.success(`已移除 ${nameFor(m)}`)
                          } catch (e) {
                            toast.error("移除失败", { description: e instanceof Error ? e.message : "" })
                          }
                        }}
                      >
                        移除
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-2 border-t border-[var(--color-border)] pt-3">
            <Label>添加成员</Label>
            <div className="flex flex-wrap gap-2">
              {allAgents
                .filter((a) => !members.includes(a.id))
                .map((a) => (
                  <Button
                    key={a.id}
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      try {
                        await addGroupMember(groupId, a.id)
                        reload()
                        toast.success(`已添加 ${a.name || a.id}`)
                      } catch (e) {
                        toast.error("添加失败", { description: e instanceof Error ? e.message : "" })
                      }
                    }}
                  >
                    + {a.name || a.id}
                  </Button>
                ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function filterMentions(
  members: string[],
  lookup: Map<string, string>,
  filter: string,
) {
  const pool = ["all", ...members.filter((m) => m !== "user")]
  const f = filter.toLowerCase()
  return pool
    .filter((m) => {
      if (m === "all") return !f || "all".includes(f)
      const label = agentDisplayName(m, lookup)
      return m.toLowerCase().includes(f) || label.toLowerCase().includes(f)
    })
    .slice(0, 8)
}

export function GroupsSection() {
  const { groupId } = useParams()
  const navigate = useNavigate()
  const { data: groups } = useResourceQuery("groups", listGroups, [])
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const { data: agents } = useResourceQuery("agents", listAgents, [])
  const [selectedMembers, setSelectedMembers] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [searchHits, setSearchHits] = useState<GroupSummary[]>([])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setSearchHits([])
      return
    }
    const t = setTimeout(() => {
      searchGroups(q, true)
        .then(setSearchHits)
        .catch(() => setSearchHits([]))
    }, 200)
    return () => clearTimeout(t)
  }, [query])

  async function handleCreateGroup() {
    if (!newName.trim()) return
    try {
      const res = await createGroup({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        members: selectedMembers,
      })
      toast.success("群组已创建")
      setShowNew(false)
      setNewName("")
      setNewDesc("")
      setSelectedMembers([])
      navigate(`/groups/${encodeURIComponent(res.group_id)}`)
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  const active = groups
    .filter((g) => g.status !== "dissolved")
    .sort((a, b) => (b.last_message_at || 0) - (a.last_message_at || 0))
  const listSource = (query.trim() ? searchHits : active).slice().sort(
    (a, b) => (b.last_message_at || 0) - (a.last_message_at || 0),
  )

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="群组"
            action={
              <Button size="sm" onClick={() => setShowNew(true)}>
                新建
              </Button>
            }
            search={
              <input
                placeholder="搜索群组（含已解散）…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            }
          >
            {listSource.map((g) => (
              <ListItemRow
                key={g.id}
                name={g.name}
                sub={
                  g.status === "dissolved"
                    ? "已解散 · 点击恢复"
                    : g.last_message
                      ? `${g.last_message.slice(0, 48)}${g.last_message.length > 48 ? "…" : ""}${
                          g.last_message_at ? ` · ${formatRelativeTime(g.last_message_at)}` : ""
                        }`
                      : g.project_id
                        ? `项目 ${g.project_id}`
                        : `${g.members?.length ?? 0} 名成员`
                }
                avatar={g.name}
                active={g.id === groupId}
                onClick={async () => {
                  if (g.status === "dissolved") {
                    try {
                      await restoreGroup(g.id)
                      toast.success("群组已恢复")
                    } catch (e) {
                      toast.error("恢复失败", { description: e instanceof Error ? e.message : "" })
                      return
                    }
                  }
                  navigate(`/groups/${encodeURIComponent(g.id)}`)
                }}
              />
            ))}
          </ListColumn>
        }
      >
        {groupId ? (
          <GroupChatPanel groupId={groupId} />
        ) : (
          <WelcomePane
            title="选择一个群组"
            description="项目协作群与独立讨论组。支持 @Agent、成员管理、清空消息与解散/恢复。"
          />
        )}
      </DiscordShell>
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建群组</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>群名称</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>描述（可选）</Label>
              <Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>初始成员</Label>
              <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                {agents.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedMembers.includes(a.id)}
                      onChange={(e) =>
                        setSelectedMembers((prev) =>
                          e.target.checked ? [...prev, a.id] : prev.filter((x) => x !== a.id),
                        )
                      }
                    />
                    <span>{a.name || a.id}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>
              取消
            </Button>
            <Button onClick={handleCreateGroup}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
