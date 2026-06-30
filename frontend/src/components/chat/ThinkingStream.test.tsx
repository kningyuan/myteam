import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ThinkingStream } from "./ThinkingStream"
import type { ThinkingEvent } from "@/lib/thinking"

describe("ThinkingStream", () => {
  it("returns null when no events and not streaming", () => {
    const { container } = render(<ThinkingStream events={[]} streaming={false} />)
    expect(container.firstChild).toBeNull()
  })

  it("renders waiting message when streaming with no events", () => {
    render(<ThinkingStream events={[]} streaming={true} />)
    expect(screen.getByText("等待 CLI 返回思考事件…")).toBeInTheDocument()
  })

  it("renders title with step count", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    render(<ThinkingStream events={events} />)
    expect(screen.getByText(/思考过程/)).toBeInTheDocument()
    expect(screen.getByText(/1/)).toBeInTheDocument()
  })

  it("renders live indicator when streaming", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    const { container } = render(<ThinkingStream events={events} streaming={true} />)
    const section = container.querySelector(".thinking-section")
    expect(section?.className).toContain("thinking-live")
  })

  it("toggles collapsed state on header click", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    render(<ThinkingStream events={events} />)
    const header = screen.getByRole("button")
    // defaultOpen=false → collapsed=true → aria-expanded=false
    expect(header.getAttribute("aria-expanded")).toBe("false")

    fireEvent.click(header)
    expect(header.getAttribute("aria-expanded")).toBe("true")
  })

  it("starts expanded when defaultOpen=true", () => {
    const events: ThinkingEvent[] = [{ type: "tool_use", name: "Read" }]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    const header = screen.getByRole("button")
    // defaultOpen=true → collapsed=false → aria-expanded=true
    expect(header.getAttribute("aria-expanded")).toBe("true")

    fireEvent.click(header)
    expect(header.getAttribute("aria-expanded")).toBe("false")
  })

  it("renders step labels for step_start events", () => {
    const events: ThinkingEvent[] = [
      { type: "step_start" },
      { type: "tool_use", name: "Read" },
      { type: "step_start" },
      { type: "tool_use", name: "Write" },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText("步骤 1")).toBeInTheDocument()
    expect(screen.getByText("步骤 2")).toBeInTheDocument()
  })

  it("renders tool activity with verb and status", () => {
    const events: ThinkingEvent[] = [
      { type: "tool_use", name: "Read", input: { filePath: "/tmp/test.ts" } },
      { type: "tool_result", content: "file content" },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText("读取")).toBeInTheDocument()
    expect(screen.getByText("/tmp/test.ts")).toBeInTheDocument()
    expect(screen.getByText("✓")).toBeInTheDocument()
  })

  it("shows pending status for incomplete tool use", () => {
    const events: ThinkingEvent[] = [
      { type: "tool_use", name: "Bash", input: { command: "npm test" } },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText("…")).toBeInTheDocument()
  })

  it("renders step_finish with token info", () => {
    const events: ThinkingEvent[] = [
      {
        type: "step_finish",
        reason: "stop",
        tokens: { input: 100, output: 50, reasoning: 20 },
      },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText("本步完成")).toBeInTheDocument()
    expect(screen.getByText(/↑100/)).toBeInTheDocument()
    expect(screen.getByText(/↓50/)).toBeInTheDocument()
    expect(screen.getByText(/≈20/)).toBeInTheDocument()
  })

  it("renders stream_text content in details", () => {
    const events: ThinkingEvent[] = [
      { type: "stream_text", content: "generating..." },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText(/中间输出/)).toBeInTheDocument()
  })

  it("renders reasoning content with label", () => {
    const events: ThinkingEvent[] = [
      { type: "reasoning", content: "deep thought" },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText(/内部推理/)).toBeInTheDocument()
  })

  it("renders tool result content in details", () => {
    const events: ThinkingEvent[] = [
      { type: "tool_use", name: "Bash", output: "command output" },
    ]
    render(<ThinkingStream events={events} defaultOpen={true} />)
    expect(screen.getByText(/返回/)).toBeInTheDocument()
  })
})
