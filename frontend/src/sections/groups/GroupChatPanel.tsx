import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { isAbortError } from "@/lib/api/client"
import { getAgentRegistry, listAgents } from "@/lib/api/agents"
import { getSkillConfig } from "@/lib/api/config"
import {
  cancelGroupChat,
  clearGroupChat,
  detectGroupChatMode,
  dissolveGroup,
  getGroup,
  getGroupChatStatus,
  reorderGroupMembers,
  sendGroupChat,
  subscribeGroupEvents,
  type GroupMessage,
  type GroupSummary,
} from "@/lib/api/groups"
import { useOnResourceInvalidate, useResourceQuery } from "@/hooks/useResourceQuery"
import { invalidateResources } from "@/lib/dataRefresh"
import {
  agentDisplayName,
  buildAgentNameLookup,
  formatMemberList,
  roundtablePhaseLabel,
} from "@/lib/chat/agentLabels"
import {
  GroupLiveAgentBubble,
  GroupMessageBubble,
  GroupReadReceiptRow,
} from "@/components/chat/GroupMessageBubble"
import {
  DEFAULT_GROUP_DISCUSSION_SETTINGS,
  effectiveGroupMaxRounds,
  groupChatInputPlaceholder,
  parseGroupDiscussionSettings,
  primaryTerminateCommand,
  type GroupDiscussionSettings,
} from "@/lib/chat/groupDiscussionSettings"
import {
  applyThinkingChunk,
  buildInflightGroupState,
  flushLiveRepliesToMessages,
  liveReplyKey,
  mergeGroupMessages,
  mergeReadReceipt,
  resolveLiveForMessage,
  seenAgentsForMessage,
  shouldShowLiveReply,
  type GroupReadReceipt,
  type LiveAgentReply,
} from "@/lib/chat/groupChatLive"
import { useImeCompositionGuard } from "@/hooks/ime"
import { Button } from "@/components/ui/button"
import { GroupMoreMenu } from "./GroupMoreMenu"
import { GroupMembersDialog } from "./GroupMembersDialog"
import { filterMentions, GROUP_CHAT_INPUT_MAX, GROUP_CHAT_INPUT_MIN } from "./utils"
import type { RoundtableProgress } from "./types"

export function GroupChatPanel({ groupId }: { groupId: string }) {
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
  const [roundtableProgress, setRoundtableProgress] = useState<RoundtableProgress | null>(null)
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
        const server = g.messages ?? []
        setMessages((prev) => (server.length ? mergeGroupMessages(prev, server) : []))
        return g
      })
      .catch((e: Error) => setError(e.message))
  }, [groupId])

  const restoreInflightIfActive = useCallback((msgs: GroupMessage[]) => {
    const inflight = buildInflightGroupState(msgs)
    if (!inflight) return
    activeTurnRef.current = inflight.activeTurn
    setLiveReplies(inflight.liveReplies)
    setReadReceipt(inflight.readReceipt)
    if (inflight.activeAgent) setActiveAgent(inflight.activeAgent)
  }, [])

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
        if (!s.active) return
        roundtableActiveRef.current = true
        setRoundtableBackground(true)
        setSending(true)
        getGroup(groupId)
          .then((g) => restoreInflightIfActive(g.messages ?? []))
          .catch(() => {})
      })
      .catch(() => {})
    getSkillConfig()
      .then((skill) => setGdSettings(parseGroupDiscussionSettings(skill)))
      .catch(() => {})
  }, [reload, groupId, restoreInflightIfActive])

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

  const nameLookupRef = useRef<Map<string, string>>(new Map())
  useEffect(() => {
    nameLookupRef.current = nameLookup
  }, [nameLookup])

  const nameForInternal = useCallback((id: string) => {
    const name = nameLookupRef.current.get(id)
    if (name) return name
    return id
  }, [])

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
      toast.error(`圆桌发言失败：${nameForInternal(agentId || "agent")}`, {
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
  }, [reload, nameForInternal])

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
      setLiveReplies({})
      setReadReceipt(null)
      setRoundtableProgress(null)
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

      <GroupMembersDialog
        open={membersOpen}
        onOpenChange={setMembersOpen}
        groupId={groupId}
        group={group}
        members={members}
        allAgents={allAgents}
        gdSettings={gdSettings}
        nameFor={nameFor}
        onGroupChange={setGroup}
        onReload={reload}
        onMoveMember={moveMember}
      />
    </>
  )
}
