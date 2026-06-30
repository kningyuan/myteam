import { describe, it, expect } from "vitest"
import {
  normalizeToolName,
  formatToolOutput,
  resolveToolResultContent,
  isToolStepComplete,
  countThinkingChainItems,
  thinkingSectionLabel,
  formatToolInputJson,
  describeToolAction,
  describeStepFinishReason,
  toolIconAbbr,
  mergeToolUseEvent,
  applyThinkingEvent,
  formatRelativeTime,
  type ThinkingEvent,
} from "./thinking"

// ─── normalizeToolName ──────────────────────────────────────

describe("normalizeToolName", () => {
  it("maps lowercase to canonical names", () => {
    expect(normalizeToolName("read")).toBe("Read")
    expect(normalizeToolName("bash")).toBe("Bash")
    expect(normalizeToolName("websearch")).toBe("WebSearch")
    expect(normalizeToolName("think")).toBe("Think")
  })

  it("returns original for unknown names", () => {
    expect(normalizeToolName("custom_tool")).toBe("custom_tool")
    expect(normalizeToolName("CustomTool")).toBe("CustomTool")
  })

  it("handles empty/null", () => {
    expect(normalizeToolName("")).toBe("tool")
    expect(normalizeToolName(null as unknown as string)).toBe("tool")
  })
})

// ─── formatToolOutput ───────────────────────────────────────

describe("formatToolOutput", () => {
  it("returns empty string for null/empty", () => {
    expect(formatToolOutput(null)).toBe("")
    expect(formatToolOutput("")).toBe("")
  })

  it("returns string as-is", () => {
    expect(formatToolOutput("hello")).toBe("hello")
  })

  it("stringifies objects", () => {
    expect(formatToolOutput({ a: 1 })).toBe('{\n  "a": 1\n}')
  })

  it("falls back to String() for circular", () => {
    const obj: Record<string, unknown> = {}
    obj.self = obj
    // JSON.stringify throws on circular → falls back to String
    expect(formatToolOutput(obj)).toBe("[object Object]")
  })
})

// ─── resolveToolResultContent ───────────────────────────────

describe("resolveToolResultContent", () => {
  it("prefers toolResult.content when available", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Read", output: "fallback" }
    const toolResult: ThinkingEvent = { type: "tool_result", content: "actual result" }
    expect(resolveToolResultContent(toolUse, toolResult)).toBe("actual result")
  })

  it("falls back to toolUse.output", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Read", output: "from output" }
    expect(resolveToolResultContent(toolUse)).toBe("from output")
  })

  it("returns empty when no result available", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Read" }
    expect(resolveToolResultContent(toolUse)).toBe("")
  })
})

// ─── isToolStepComplete ─────────────────────────────────────

describe("isToolStepComplete", () => {
  it("returns true when toolResult has content", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Bash" }
    const toolResult: ThinkingEvent = { type: "tool_result", content: "done" }
    expect(isToolStepComplete(toolUse, toolResult)).toBe(true)
  })

  it("returns true when toolUse has output", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Bash", output: "result" }
    expect(isToolStepComplete(toolUse)).toBe(true)
  })

  it("returns false when no result", () => {
    const toolUse: ThinkingEvent = { type: "tool_use", name: "Bash" }
    expect(isToolStepComplete(toolUse)).toBe(false)
  })
})

// ─── countThinkingChainItems ────────────────────────────────

describe("countThinkingChainItems", () => {
  it("counts zero for empty", () => {
    expect(countThinkingChainItems([])).toBe(0)
  })

  it("counts tool_use events (paired with result counts as 1)", () => {
    const events: ThinkingEvent[] = [
      { type: "tool_use", name: "Read" },
      { type: "tool_result", content: "data" },
    ]
    expect(countThinkingChainItems(events)).toBe(1)
  })

  it("counts unpaired tool_use as 1", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    expect(countThinkingChainItems(events)).toBe(1)
  })

  it("counts stream_text and reasoning with content", () => {
    const events: ThinkingEvent[] = [
      { type: "stream_text", content: "hello" },
      { type: "reasoning", content: "thinking..." },
    ]
    expect(countThinkingChainItems(events)).toBe(2)
  })

  it("does not count stream_text without content", () => {
    const events: ThinkingEvent[] = [{ type: "stream_text" }]
    expect(countThinkingChainItems(events)).toBe(0)
  })

  it("counts step_finish with reasoning tokens", () => {
    const events: ThinkingEvent[] = [
      { type: "step_finish", tokens: { reasoning: 100 } },
    ]
    expect(countThinkingChainItems(events)).toBe(1)
  })

  it("does not count step_finish without reasoning tokens", () => {
    const events: ThinkingEvent[] = [
      { type: "step_finish", tokens: { input: 10, output: 5 } },
    ]
    expect(countThinkingChainItems(events)).toBe(0)
  })
})

// ─── thinkingSectionLabel ───────────────────────────────────

describe("thinkingSectionLabel", () => {
  it("returns '思考过程' for empty non-streaming", () => {
    expect(thinkingSectionLabel([], false)).toEqual({ title: "思考过程", live: false })
  })

  it("returns live label for empty streaming", () => {
    const result = thinkingSectionLabel([], true)
    expect(result.live).toBe(true)
    expect(result.title).toBe("思考过程")
    expect(result.hint).toBeTruthy()
  })

  it("includes step count when events exist", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    const result = thinkingSectionLabel(events, false)
    expect(result.title).toContain("1")
    expect(result.title).toContain("思考过程")
  })

  it("includes hint from last activity", () => {
    const events: ThinkingEvent[] = [
      { type: "tool_use", name: "Bash", input: { command: "ls" } },
    ]
    const result = thinkingSectionLabel(events, false)
    expect(result.hint).toBeTruthy()
    expect(result.hint).toContain("运行命令")
  })
})

// ─── formatToolInputJson ────────────────────────────────────

describe("formatToolInputJson", () => {
  it("stringifies object input", () => {
    expect(formatToolInputJson({ a: 1 })).toBe('{\n  "a": 1\n}')
  })

  it("parses JSON string input", () => {
    expect(formatToolInputJson('{"b":2}')).toBe('{\n  "b": 2\n}')
  })

  it("returns raw string for non-JSON", () => {
    expect(formatToolInputJson("not json")).toBe("not json")
  })

  it("handles null/undefined", () => {
    // parseToolInputObj(null) returns {} → JSON.stringify({}) = "{}"
    expect(formatToolInputJson(null)).toBe("{}")
    expect(formatToolInputJson(undefined)).toBe("{}")
  })
})

// ─── describeToolAction ─────────────────────────────────────

describe("describeToolAction", () => {
  it("describes Read tool", () => {
    const result = describeToolAction("read", { filePath: "/tmp/test.txt" })
    expect(result.verb).toBe("读取")
    expect(result.target).toBe("/tmp/test.txt")
    expect(result.mono).toBe(true)
  })

  it("describes Bash tool with command", () => {
    const result = describeToolAction("bash", { command: "npm test" })
    expect(result.verb).toBe("运行命令")
    expect(result.target).toBe("npm test")
    expect(result.mono).toBe(true)
  })

  it("describes Grep tool", () => {
    const result = describeToolAction("grep", { pattern: "TODO", path: "src" })
    expect(result.verb).toBe("搜索")
    expect(result.target).toContain("TODO")
    expect(result.mono).toBe(false)
  })

  it("describes Think tool", () => {
    const result = describeToolAction("think", { thought: "analyzing..." })
    expect(result.verb).toBe("推理")
    expect(result.target).toContain("analyzing")
  })

  it("describes unknown tool", () => {
    const result = describeToolAction("CustomTool", { x: 1 })
    expect(result.verb).toBe("CustomTool")
    expect(result.mono).toBe(true)
  })

  it("truncates long commands", () => {
    const longCmd = "a".repeat(200)
    const result = describeToolAction("bash", { command: longCmd })
    expect(result.target.length).toBeLessThanOrEqual(83) // 80 + "…"
  })
})

// ─── describeStepFinishReason ───────────────────────────────

describe("describeStepFinishReason", () => {
  it("maps tool-calls", () => {
    expect(describeStepFinishReason("tool-calls")).toBe("准备继续调用工具")
    expect(describeStepFinishReason("tool_calls")).toBe("准备继续调用工具")
  })

  it("maps stop/completed", () => {
    expect(describeStepFinishReason("stop")).toBe("本步完成")
    expect(describeStepFinishReason("completed")).toBe("本步完成")
  })

  it("maps length", () => {
    expect(describeStepFinishReason("length")).toBe("达到长度上限")
  })

  it("returns reason as-is for unknown", () => {
    expect(describeStepFinishReason("custom")).toBe("custom")
  })

  it("returns default for empty", () => {
    expect(describeStepFinishReason("")).toBe("步骤结束")
    expect(describeStepFinishReason(null as unknown as string)).toBe("步骤结束")
  })
})

// ─── toolIconAbbr ───────────────────────────────────────────

describe("toolIconAbbr", () => {
  it("returns 子 for Task", () => {
    expect(toolIconAbbr("task")).toBe("子")
  })

  it("returns 思 for Think", () => {
    expect(toolIconAbbr("think")).toBe("思")
  })

  it("returns uppercase for short names", () => {
    expect(toolIconAbbr("ls")).toBe("LS")
  })

  it("returns first 2 consonants for long names", () => {
    expect(toolIconAbbr("CustomTool")).toBe("CT")
  })
})

// ─── mergeToolUseEvent ──────────────────────────────────────

describe("mergeToolUseEvent", () => {
  it("appends when last event is different type", () => {
    const chain: ThinkingEvent[] = [{ type: "step_start" }]
    const incoming: ThinkingEvent = { type: "tool_use", name: "Read" }
    const result = mergeToolUseEvent(chain, incoming)
    expect(result).toHaveLength(2)
  })

  it("merges when last tool_use is same name and incoming has output", () => {
    const chain: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    const incoming: ThinkingEvent = { type: "tool_use", name: "Read", output: "data" }
    const result = mergeToolUseEvent(chain, incoming)
    expect(result).toHaveLength(1)
    expect(result[0].output).toBe("data")
  })

  it("merges when last is incomplete and incoming adds fields", () => {
    const chain: ThinkingEvent[] = [{ type: "tool_use", name: "Bash" }]
    const incoming: ThinkingEvent = { type: "tool_use", name: "Bash", input: { command: "ls" } }
    const result = mergeToolUseEvent(chain, incoming)
    expect(result).toHaveLength(1)
    expect(result[0].input).toEqual({ command: "ls" })
  })

  it("appends when names differ", () => {
    const chain: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    const incoming: ThinkingEvent = { type: "tool_use", name: "Write" }
    const result = mergeToolUseEvent(chain, incoming)
    expect(result).toHaveLength(2)
  })
})

// ─── applyThinkingEvent ─────────────────────────────────────

describe("applyThinkingEvent", () => {
  it("appends text to text field when no tool_use in chain", () => {
    const result = applyThinkingEvent([], "hello", { type: "text", content: " world" })
    expect(result.text).toBe("hello world")
    expect(result.thinking).toEqual([])
  })

  it("adds stream_text event when tool_use exists in chain", () => {
    const chain: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    const result = applyThinkingEvent(chain, "", { type: "text", content: "output" })
    expect(result.text).toBe("output")
    expect(result.thinking).toHaveLength(2)
    expect(result.thinking[1].type).toBe("stream_text")
  })

  it("handles stream_text type", () => {
    const result = applyThinkingEvent([], "", { type: "stream_text", content: "chunk" })
    expect(result.text).toBe("")
    expect(result.thinking).toHaveLength(1)
    expect(result.thinking[0].type).toBe("stream_text")
  })

  it("handles reasoning type", () => {
    const result = applyThinkingEvent([], "", { type: "reasoning", content: "thought" })
    expect(result.thinking).toHaveLength(1)
    expect(result.thinking[0].type).toBe("reasoning")
  })

  it("handles step_start/tool_result/step_finish types", () => {
    for (const t of ["step_start", "tool_result", "step_finish"]) {
      const result = applyThinkingEvent([], "", { type: t })
      expect(result.thinking).toHaveLength(1)
    }
  })

  it("ignores unknown event types", () => {
    const result = applyThinkingEvent([], "text", { type: "unknown" })
    expect(result.thinking).toEqual([])
    expect(result.text).toBe("text")
  })

  it("ignores text without content", () => {
    const result = applyThinkingEvent([], "text", { type: "text" })
    expect(result.thinking).toEqual([])
    expect(result.text).toBe("text")
  })
})

// ─── formatRelativeTime ─────────────────────────────────────

describe("formatRelativeTime", () => {
  it("returns empty for falsy", () => {
    expect(formatRelativeTime(0)).toBe("")
    expect(formatRelativeTime("")).toBe("")
  })

  it("returns '刚刚' for recent", () => {
    expect(formatRelativeTime(Date.now())).toBe("刚刚")
  })

  it("returns minutes for < 1 hour", () => {
    const fiveMinAgo = Date.now() - 5 * 60 * 1000
    expect(formatRelativeTime(fiveMinAgo)).toBe("5 分钟前")
  })

  it("returns hours for < 1 day", () => {
    const threeHoursAgo = Date.now() - 3 * 3600 * 1000
    expect(formatRelativeTime(threeHoursAgo)).toBe("3 小时前")
  })

  it("returns days for > 1 day", () => {
    const twoDaysAgo = Date.now() - 2 * 86400 * 1000
    expect(formatRelativeTime(twoDaysAgo)).toBe("2 天前")
  })

  it("handles ISO string", () => {
    const recent = new Date(Date.now() - 10000).toISOString()
    expect(formatRelativeTime(recent)).toBe("刚刚")
  })

  it("handles unix seconds (not ms)", () => {
    const recent = Math.floor((Date.now() - 5000) / 1000)
    expect(formatRelativeTime(recent)).toBe("刚刚")
  })

  it("returns empty for invalid string", () => {
    expect(formatRelativeTime("invalid")).toBe("")
  })
})
