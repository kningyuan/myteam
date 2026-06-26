export const DAG_COLORS: Record<string, string> = {
  completed: "#22c55e",
  needs_review: "#eab308",
  running: "#3b82f6",
  in_progress: "#3b82f6",
  failed: "#ef4444",
  blocked: "#6b7280",
  pending: "#93c5fd",
  cancelled: "#a1a1aa",
  awaiting_gate: "#a855f7",
}

export const DAG_LABELS: Record<string, string> = {
  completed: "已完成",
  needs_review: "待评审",
  running: "运行中",
  in_progress: "运行中",
  failed: "失败",
  blocked: "阻塞",
  pending: "等待中",
  cancelled: "已取消",
  awaiting_gate: "等待门禁",
}

export const INTERACTION_LABELS: Record<string, string> = {
  team_config: "组队配置",
  task_plan: "任务拆分",
  evaluate: "派发前评估",
  dispatch_evaluate: "派发前评估",
  execute: "执行",
  review: "评审",
  triage: "分诊",
}

export const INTERACTION_STATUS_LABEL: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  timed_out: "超时",
  blocked: "阻塞",
  pending: "等待",
}

export const EVENT_LABELS: Record<string, string> = {
  gate_passed: "门禁通过",
  gate_failed: "门禁未过",
  review_done: "评审完成",
  review_unreachable: "评审不可达",
  plan_rejected: "计划被拒",
  blocked: "任务阻塞",
  budget_alert: "预算告警",
  budget_over: "预算超限",
  budget_degrade: "预算降级",
  budget_exceeded: "交互超预算",
  budget_exceeded_pause: "超预算暂停",
  cycle_done: "周期完成",
  loop_round_done: "循环轮次完成",
  loop_round_assess: "循环评估",
  loop_transition: "循环分支切换",
  branch_selected: "循环分支选定",
  loop_finished: "循环结束",
  watchdog_soft_idle: "疑似卡住",
  watchdog_hard_kill: "看门狗中止",
  transport_error: "传输错误",
  reconcile_timed_out: "重启对账超时",
  reconcile_adopted: "对账回收",
  tool_use: "skill 调用",
  tool_result: "工具返回",
  prompt_sent: "发送 prompt",
  request_snapshot: "请求快照",
  response_snapshot: "响应快照",
  message: "消息",
  parallel_wave: "并行波次",
  task_split: "子任务拆分",
  text: "模型输出",
  step_finish: "Token 计量",
  error: "错误",
  skill_review_started: "Skill 复盘开始",
  skill_review_completed: "Skill 复盘完成",
  skill_review_failed: "Skill 复盘失败",
  skill_review_pending: "Skill 待审核",
}

export const EXEC_CHILD_LABELS: Record<string, string> = {
  tool_use: "skill 调用",
  tool_result: "工具返回",
  text: "模型输出",
  step_finish: "Token 计量",
  prompt_sent: "发送 prompt",
  request_snapshot: "请求快照",
  response_snapshot: "响应快照",
  error: "错误",
  transport_error: "传输错误",
}

/** run_event 中属于「思考过程」、由 ThinkingStream 聚合展示的种类 */
export const EXEC_THINKING_KINDS = new Set([
  "step_start",
  "tool_use",
  "tool_result",
  "text",
  "step_finish",
  "reasoning",
])

export function isExecThinkingKind(kind?: string): boolean {
  return EXEC_THINKING_KINDS.has(kind || "")
}

/** 任务级执行过程：跳过项目级交互 */
export const TASK_EXEC_SKIP_INTERACTIONS = new Set(["team_config", "task_plan"])

export function execContentTag(kind?: string): { label: string; tone: string } {
  const k = kind || ""
  if (k === "tool_use" || k === "tool_result") return { label: "Skill", tone: "skill" }
  if (k === "text" || k === "reasoning") return { label: "输出", tone: "text" }
  if (k.startsWith("step_")) return { label: "思考", tone: "think" }
  if (k.startsWith("gate_")) return { label: "门禁", tone: "gate" }
  if (k.startsWith("review_")) return { label: "评审", tone: "review" }
  if (k.startsWith("skill_review_")) return { label: "复盘", tone: "review" }
  if (k.startsWith("loop_") || k === "branch_selected") return { label: "循环", tone: "loop" }
  if (k === "task_split") return { label: "拆分", tone: "split" }
  if (k === "error" || k === "transport_error" || k === "watchdog_hard_kill") {
    return { label: "错误", tone: "error" }
  }
  if (k === "prompt_sent" || k === "request_snapshot" || k === "response_snapshot") {
    return { label: "请求", tone: "meta" }
  }
  return { label: EVENT_LABELS[k] || EXEC_CHILD_LABELS[k] || k || "事件", tone: "meta" }
}

export function execPhaseTag(kind?: string): { label: string; tone: string } {
  const k = kind || ""
  if (k === "evaluate" || k === "dispatch_evaluate") return { label: "评估", tone: "evaluate" }
  if (k === "execute") return { label: "执行", tone: "execute" }
  if (k === "review") return { label: "评审", tone: "review" }
  if (k === "triage") return { label: "分诊", tone: "meta" }
  return { label: INTERACTION_LABELS[k] || k || "步骤", tone: "meta" }
}

export const EXEC_TIMELINE_KINDS = new Set([
  "step_start",
  "tool_use",
  "tool_result",
  "text",
  "reasoning",
  "gate_passed",
  "gate_failed",
  "review_done",
  "review_unreachable",
  "error",
  "transport_error",
  "watchdog_soft_idle",
  "watchdog_hard_kill",
  "step_finish",
  "prompt_sent",
  "request_snapshot",
  "response_snapshot",
  "plan_rejected",
])

export function fmtExecTs(ts?: string) {
  if (!ts) return "—"
  return ts.replace("T", " ").slice(5, 16)
}

export function truncateText(text: string, max = 120): string {
  const s = text.replace(/\s+/g, " ").trim()
  if (s.length <= max) return s
  return `${s.slice(0, max)}…`
}

export type GateFailureLike = { rule?: string; expected?: string; actual?: string }

export function formatGateFailure(f: GateFailureLike | string): string {
  if (typeof f === "string") return f
  const parts = [f.rule, f.expected, f.actual].filter(Boolean)
  if (parts.length >= 3) return `[${f.rule}] 期望：${f.expected}；实际：${f.actual}`
  if (parts.length === 2) return `${parts[0]}：${parts[1]}`
  return parts[0] || "门禁未通过"
}

export function formatGateFailures(failures: (GateFailureLike | string)[] | undefined): string[] {
  if (!failures?.length) return []
  return failures.map(formatGateFailure)
}

export function eventDetail(e: { kind?: string; payload?: Record<string, unknown> }) {
  const p = e.payload || {}
  const kind = e.kind || ""
  if (kind === "gate_failed" && Array.isArray(p.failures)) {
    return formatGateFailures(p.failures as (GateFailureLike | string)[]).join("；")
  }
  if (kind === "review_done") {
    return `${p.passed ? "通过" : "打回"}${p.feedback ? ` · ${p.feedback}` : ""}`
  }
  if (kind === "message") {
    const text = String(p.text || "").replace(/\s+/g, " ").trim()
    const sender = p.sender ? `${p.sender}：` : ""
    return truncateText(sender + text, 96)
  }
  if (kind === "tool_use") {
    const name = String(p.name || p.tool || "tool")
    return `${name} · ${String(p.input ?? "").slice(0, 80)}`
  }
  if (kind === "parallel_wave") {
    const tasks = Array.isArray(p.tasks) ? (p.tasks as string[]) : []
    const shown = tasks.slice(0, 3).join(", ")
    const more = tasks.length > 3 ? ` +${tasks.length - 3}` : ""
    return `共 ${p.count || tasks.length} 个任务${shown ? `：${shown}${more}` : ""}`
  }
  if (kind === "loop_round_done") {
    const round = p.round ?? "?"
    const passed = p.passed === true ? "通过" : p.passed === false ? "未通过" : ""
    const bodyKey = p.body_key ? ` · body=${p.body_key}` : ""
    return `第 ${round} 轮${passed ? ` · ${passed}` : ""}${bodyKey}`
  }
  if (kind === "loop_round_assess") {
    const round = p.round ?? "?"
    const action = p.action ? ` · ${p.action}` : ""
    return `第 ${round} 轮${action}`
  }
  if (kind === "loop_transition") {
    const from = p.from_body || "?"
    const to = p.to_body || "?"
    return `${from} → ${to}`
  }
  if (kind === "branch_selected") {
    const to = p.body_key || p.to_body || "?"
    return `→ ${to}`
  }
  if (kind === "loop_finished") {
    const state = String(p.state || "")
    const rounds = p.rounds_used != null ? ` · ${p.rounds_used} 轮` : ""
    return `${state || "结束"}${rounds}`
  }
  if (kind === "task_split") {
    const children = Array.isArray(p.children) ? (p.children as string[]) : []
    const reason = p.reason ? ` · ${p.reason}` : ""
    return `拆出 ${children.length} 个子任务${reason}`
  }
  if (kind === "blocked" || kind === "plan_rejected") {
    return String(p.reason || (Array.isArray(p.invalid_agents) ? p.invalid_agents.join(", ") : ""))
  }
  if (kind === "budget_alert" || kind === "budget_over") return JSON.stringify(p)
  if (kind === "text") return String(p.content || "").slice(0, 160)
  if (kind === "step_finish") {
    const t = p.tokens
    if (t && typeof t === "object") {
      const o = t as Record<string, number>
      return `${o.total || (o.input || 0) + (o.output || 0) || 0} tok`
    }
    return t ? `${t} tok` : ""
  }
  if (kind === "prompt_sent") return `${p.prompt_len || 0} 字 · ${p.model || p.agent_id || ""}`
  if (kind === "request_snapshot") return String(p.request_path || "InteractionRequest")
  if (kind === "response_snapshot") return String(p.response_path || "response")
  if (kind === "tool_result") return String(p.content || "").slice(0, 160)
  if (kind === "skill_review_completed") {
    const action = p.action || "noop"
    const skillId = p.skill_id || ""
    return `action=${action}${skillId ? ` · skill=${skillId}` : ""}`
  }
  if (kind === "skill_review_failed") {
    return `error: ${(p.error || "").slice(0, 120)}`
  }
  if (kind === "skill_review_started") {
    return `task=${p.task_id || ""} · type=${p.task_type || ""}`
  }
  if (kind === "skill_review_pending") {
    return `pending_id=${p.pending_id || ""}`
  }
  return Object.keys(p).length ? JSON.stringify(p).slice(0, 160) : ""
}

export function payloadPre(data: unknown) {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}
