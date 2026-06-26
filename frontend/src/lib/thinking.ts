import type { TimelineEvent } from "@/lib/api/projects"
import { isExecThinkingKind } from "@/lib/project-labels"

export type ThinkingEvent = {
  type: string
  content?: string
  name?: string
  input?: unknown
  output?: unknown
  status?: string
  reason?: string
  tokens?: { input?: number; output?: number; total?: number; reasoning?: number }
}

export function normalizeToolName(name: string): string {
  const n = String(name || "tool").trim()
  const lower = n.toLowerCase()
  const map: Record<string, string> = {
    read: "Read",
    write: "Write",
    edit: "Edit",
    grep: "Grep",
    glob: "Glob",
    bash: "Bash",
    run: "Run",
    task: "Task",
    websearch: "WebSearch",
    webfetch: "WebFetch",
    think: "Think",
  }
  return map[lower] || n
}

export function formatToolOutput(output: unknown): string {
  if (output == null || output === "") return ""
  if (typeof output === "string") return output
  try {
    return JSON.stringify(output, null, 2)
  } catch {
    return String(output)
  }
}

/** OpenCode 常把结果放在 tool_use.output；Claude 流用独立 tool_result。 */
export function resolveToolResultContent(
  toolUse: ThinkingEvent,
  toolResult?: ThinkingEvent,
): string {
  if (toolResult && typeof toolResult.content === "string" && toolResult.content) {
    return toolResult.content
  }
  return formatToolOutput(toolUse.output)
}

export function isToolStepComplete(toolUse: ThinkingEvent, toolResult?: ThinkingEvent): boolean {
  return Boolean(resolveToolResultContent(toolUse, toolResult))
}

export function countThinkingChainItems(events: ThinkingEvent[]): number {
  let n = 0
  for (let i = 0; i < events.length; i++) {
    const t = events[i]
    if (t.type === "tool_use") {
      n += 1
      const next = events[i + 1]
      if (next?.type === "tool_result") i += 1
    } else if ((t.type === "stream_text" || t.type === "reasoning") && t.content) {
      n += 1
    } else if (t.type === "step_finish" && (t.tokens?.reasoning || 0) > 0) {
      n += 1
    }
  }
  return n
}

/** @deprecated use countThinkingChainItems */
export function countThinkingActivities(events: ThinkingEvent[]): number {
  return countThinkingChainItems(events)
}

export function thinkingSectionLabel(
  events: ThinkingEvent[],
  streaming: boolean,
): { title: string; hint?: string; live: boolean } {
  const n = countThinkingChainItems(events)
  const hint = lastActivityHint(events, streaming)

  if (streaming) {
    if (!n) {
      return { title: "思考过程", hint: hint || "进行中…", live: true }
    }
    return { title: `思考过程 · ${n} 步`, hint, live: true }
  }
  if (!n) return { title: "思考过程", live: false }
  return { title: `思考过程 · ${n} 步`, hint, live: false }
}

/** @deprecated use thinkingSectionLabel */
export function thinkingSectionTitle(events: ThinkingEvent[], streaming: boolean): string {
  const { title, hint } = thinkingSectionLabel(events, streaming)
  return hint ? `${title} · ${hint}` : title
}

function lastActivityHint(events: ThinkingEvent[], streaming: boolean): string | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    const t = events[i]
    if (t.type === "stream_text" && t.content) {
      const preview = truncateText(String(t.content).replace(/\s+/g, " "), 48)
      return preview ? `草稿 · ${preview}` : undefined
    }
    if (t.type !== "tool_use") continue
    const next = events[i + 1]
    const paired = next?.type === "tool_result" ? next : undefined
    const pending = !isToolStepComplete(t, paired)
    const act = describeToolAction(t.name || "tool", t.input)
    const label = act.mono
      ? `${act.verb} ${act.target}`
      : `${act.verb} · ${act.target}`
    return pending ? `${label} …` : label
  }
  if (streaming && !events.length) return "等待 CLI 响应…"
  return undefined
}

function parseToolInputObj(input: unknown): Record<string, unknown> {
  if (!input) return {}
  if (typeof input === "object") return input as Record<string, unknown>
  const s = String(input).trim()
  try {
    return JSON.parse(s) as Record<string, unknown>
  } catch {
    try {
      return JSON.parse(s.replace(/^"(.*)"$/, "$1")) as Record<string, unknown>
    } catch {
      return { raw: s }
    }
  }
}

export function formatToolInputJson(input: unknown): string {
  const obj = parseToolInputObj(input)
  if (obj.raw != null) return String(obj.raw)
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(input ?? "")
  }
}

function truncateText(text: string, max: number): string {
  const s = String(text || "")
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

function shortPath(p: string): string {
  const parts = String(p || "").split(/[/\\]/)
  return parts.length <= 2 ? p : `…/${parts.slice(-2).join("/")}`
}

function filePathFromInput(inp: Record<string, unknown>): string {
  return String(inp.filePath || inp.file_path || inp.path || inp.file || "…")
}

export function describeToolAction(name: string, input: unknown): {
  verb: string
  target: string
  mono: boolean
} {
  const inp = parseToolInputObj(input)
  const n = normalizeToolName(name)
  switch (n) {
    case "Read":
      return { verb: "读取", target: filePathFromInput(inp), mono: true }
    case "Write":
      return { verb: "写入", target: filePathFromInput(inp), mono: true }
    case "Edit":
      return { verb: "编辑", target: filePathFromInput(inp), mono: true }
    case "Bash":
    case "Run":
      return {
        verb: "运行命令",
        target: truncateText(String(inp.command || inp.cmd || inp.script || inp.raw || ""), 80),
        mono: true,
      }
    case "Grep":
      return {
        verb: "搜索",
        target: `"${truncateText(String(inp.pattern || inp.query || ""), 36)}" · ${shortPath(String(inp.path || inp.glob || "."))}`,
        mono: false,
      }
    case "Glob":
      return { verb: "匹配文件", target: String(inp.pattern || inp.glob || "…"), mono: true }
    case "WebSearch":
      return {
        verb: "Web 搜索",
        target: truncateText(String(inp.query || inp.q || inp.search_term || ""), 60),
        mono: false,
      }
    case "WebFetch":
      return { verb: "抓取 URL", target: truncateText(String(inp.url || ""), 72), mono: true }
    case "Task":
      return {
        verb: "子任务",
        target: truncateText(
          String(
            inp.description ||
              inp.prompt ||
              (inp.subagent_type ? `[${inp.subagent_type}] ` : "") ||
              "",
          ),
          72,
        ),
        mono: false,
      }
    case "Think":
      return {
        verb: "推理",
        target: truncateText(
          String(inp.thought || inp.content || inp.text || formatToolInputJson(input)),
          120,
        ),
        mono: false,
      }
    default:
      return {
        verb: n,
        target: truncateText(formatToolInputJson(input).replace(/\s+/g, " "), 60),
        mono: true,
      }
  }
}

export function describeStepFinishReason(reason: string): string {
  const r = String(reason || "").trim()
  switch (r) {
    case "tool-calls":
    case "tool_calls":
      return "准备继续调用工具"
    case "stop":
    case "completed":
      return "本步完成"
    case "assistant_message":
      return "模型输出一段内容"
    case "length":
      return "达到长度上限"
    default:
      return r || "步骤结束"
  }
}

export function toolIconAbbr(name: string): string {
  const n = normalizeToolName(name)
  if (n === "Task") return "子"
  if (n === "Think") return "思"
  if (n.length <= 2) return n.toUpperCase()
  return n.replace(/[^A-Z]/g, "").slice(0, 2) || n.slice(0, 2).toUpperCase()
}

export function mergeToolUseEvent(
  thinking: ThinkingEvent[],
  incoming: ThinkingEvent,
): ThinkingEvent[] {
  const last = thinking[thinking.length - 1]
  if (
    last?.type === "tool_use" &&
    last.name === incoming.name &&
    !resolveToolResultContent(last) &&
    resolveToolResultContent(incoming)
  ) {
    return [...thinking.slice(0, -1), { ...last, ...incoming }]
  }
  if (
    last?.type === "tool_use" &&
    last.name === incoming.name &&
    !isToolStepComplete(last) &&
    !resolveToolResultContent(incoming)
  ) {
    return [...thinking.slice(0, -1), { ...last, ...incoming }]
  }
  return [...thinking, incoming]
}

/** 将 SSE thinking 事件合并进轨迹（群聊 / 私聊共用）。 */
export function applyThinkingEvent(
  thinking: ThinkingEvent[],
  text: string,
  data: Record<string, unknown>,
): { thinking: ThinkingEvent[]; text: string } {
  const type = String(data.type || "")
  if (type === "text" && data.content) {
    const chunk = String(data.content)
    const hasToolSteps = thinking.some((t) => t.type === "tool_use")
    return {
      text: text + chunk,
      thinking: hasToolSteps
        ? [...thinking, { type: "stream_text", content: chunk }]
        : thinking,
    }
  }
  if (type === "stream_text" && data.content) {
    return {
      text,
      thinking: [...thinking, { type: "stream_text", content: String(data.content) }],
    }
  }
  if (type === "tool_use") {
    return {
      text,
      thinking: mergeToolUseEvent(thinking, data as ThinkingEvent),
    }
  }
  if (type === "reasoning" && data.content) {
    return {
      text,
      thinking: [...thinking, { type: "reasoning", content: String(data.content) }],
    }
  }
  if (["step_start", "tool_result", "step_finish"].includes(type)) {
    return { text, thinking: [...thinking, data as ThinkingEvent] }
  }
  return { thinking, text }
}

/** 项目 execute timeline → ThinkingStream 事件（与 backend thinking_from_run_event 对齐） */
export function timelineToThinkingEvents(timeline: TimelineEvent[]): ThinkingEvent[] {
  let chain: ThinkingEvent[] = []
  for (const ev of timeline) {
    if (!isExecThinkingKind(ev.kind)) continue
    const p = ev.payload || {}
    const kind = ev.kind || ""
    if (kind === "text") {
      const content = String(p.content || "")
      if (content) chain = [...chain, { type: "stream_text", content }]
    } else if (kind === "reasoning") {
      const content = String(p.content || "")
      if (content) chain = [...chain, { type: "reasoning", content }]
    } else if (kind === "step_start") {
      chain = [...chain, { type: "step_start" }]
    } else if (kind === "tool_use") {
      const item: ThinkingEvent = {
        type: "tool_use",
        name: String(p.name || p.tool || ""),
        input: p.input,
      }
      if (p.output != null) item.output = p.output
      if (p.status) item.status = String(p.status)
      chain = mergeToolUseEvent(chain, item)
    } else if (kind === "tool_result") {
      const content = String(p.content || "")
      if (content) chain = [...chain, { type: "tool_result", content }]
    } else if (kind === "step_finish") {
      chain = [
        ...chain,
        {
          type: "step_finish",
          reason: String(p.reason || ""),
          tokens: p.tokens as ThinkingEvent["tokens"],
        },
      ]
    }
  }
  return chain
}

export function formatRelativeTime(ts: number | string): string {
  if (!ts) return ""
  let ms: number
  if (typeof ts === "string") {
    const parsed = Date.parse(ts)
    if (Number.isNaN(parsed)) return ""
    ms = parsed
  } else {
    ms = ts > 1e12 ? ts : ts * 1000
  }
  const sec = Math.floor((Date.now() - ms) / 1000)
  if (sec < 60) return "刚刚"
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return `${Math.floor(sec / 86400)} 天前`
}
