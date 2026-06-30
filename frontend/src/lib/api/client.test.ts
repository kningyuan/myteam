import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  hubFetch,
  isAbortError,
  readStreamWithAbort,
  parseSseDataLines,
  parseSseLineBuffer,
} from "./client"

// ─── hubFetch ───────────────────────────────────────────────

describe("hubFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("returns parsed JSON on 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ hello: "world" }),
      }),
    )
    const data = await hubFetch("/api/test")
    expect(data).toEqual({ hello: "world" })
    expect(fetch).toHaveBeenCalledWith("/api/test", undefined)
  })

  it("passes init options to fetch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    )
    await hubFetch("/api/test", { method: "POST", body: "{}" })
    expect(fetch).toHaveBeenCalledWith("/api/test", { method: "POST", body: "{}" })
  })

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
      }),
    )
    await expect(hubFetch("/api/missing")).rejects.toThrow("404 Not Found")
  })

  it("throws on 500 with status text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      }),
    )
    await expect(hubFetch("/api/err")).rejects.toThrow("500 Internal Server Error")
  })
})

// ─── isAbortError ───────────────────────────────────────────

describe("isAbortError", () => {
  it("returns true for DOMException AbortError", () => {
    const err = new DOMException("aborted", "AbortError")
    expect(isAbortError(err)).toBe(true)
  })

  it("returns true for Error with name AbortError", () => {
    const err = new Error("aborted")
    err.name = "AbortError"
    expect(isAbortError(err)).toBe(true)
  })

  it("returns false for generic Error", () => {
    expect(isAbortError(new Error("network"))).toBe(false)
  })

  it("returns false for non-Error values", () => {
    expect(isAbortError(null)).toBe(false)
    expect(isAbortError("string")).toBe(false)
    expect(isAbortError(undefined)).toBe(false)
  })
})

// ─── readStreamWithAbort ────────────────────────────────────

describe("readStreamWithAbort", () => {
  function makeStream(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
    return new ReadableStream({
      start(controller) {
        for (const c of chunks) controller.enqueue(c)
        controller.close()
      },
    })
  }

  it("reads all chunks and calls onChunk", async () => {
    const data = [new Uint8Array([1, 2]), new Uint8Array([3, 4])]
    const received: number[] = []
    await readStreamWithAbort(makeStream(data), undefined, (chunk) => {
      for (const b of chunk) received.push(b)
    })
    expect(received).toEqual([1, 2, 3, 4])
  })

  it("handles empty stream", async () => {
    const received: Uint8Array[] = []
    await readStreamWithAbort(makeStream([]), undefined, (c) => received.push(c))
    expect(received).toEqual([])
  })

  it("throws AbortError when signal already aborted", async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(
      readStreamWithAbort(makeStream([new Uint8Array([1])]), controller.signal, () => {}),
    ).rejects.toThrow()
  })
})

// ─── parseSseDataLines ──────────────────────────────────────

describe("parseSseDataLines", () => {
  it("parses single complete event", () => {
    const events: string[] = []
    const remainder = parseSseDataLines("data: hello\n\n", (raw) => events.push(raw))
    expect(events).toEqual(["hello"])
    expect(remainder).toBe("")
  })

  it("parses multiple events", () => {
    const events: string[] = []
    const remainder = parseSseDataLines(
      "data: a\n\ndata: b\n\n",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["a", "b"])
    expect(remainder).toBe("")
  })

  it("returns incomplete trailing chunk as remainder", () => {
    const events: string[] = []
    const remainder = parseSseDataLines(
      "data: a\n\ndata: incomplete",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["a"])
    expect(remainder).toBe("data: incomplete")
  })

  it("skips non-data lines", () => {
    const events: string[] = []
    parseSseDataLines(
      "event: thinking\ndata: payload\n\n",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["payload"])
  })

  it("returns empty string on [DONE]", () => {
    const events: string[] = []
    const remainder = parseSseDataLines("data: [DONE]\n\n", (raw) => events.push(raw))
    expect(events).toEqual([])
    expect(remainder).toBe("")
  })

  it("trims whitespace in data payload", () => {
    const events: string[] = []
    parseSseDataLines("data:   spaced  \n\n", (raw) => events.push(raw))
    expect(events).toEqual(["spaced"])
  })
})

// ─── parseSseLineBuffer ─────────────────────────────────────

describe("parseSseLineBuffer", () => {
  it("parses complete lines", () => {
    const events: string[] = []
    const remainder = parseSseLineBuffer(
      "data: alpha\ndata: beta\n",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["alpha", "beta"])
    expect(remainder).toBe("")
  })

  it("returns incomplete trailing line as remainder", () => {
    const events: string[] = []
    const remainder = parseSseLineBuffer(
      "data: full\ndata: partial",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["full"])
    expect(remainder).toBe("data: partial")
  })

  it("skips empty lines and [DONE]", () => {
    const events: string[] = []
    parseSseLineBuffer(
      "data: ok\n\ndata: [DONE]\ndata: more\n",
      (raw) => events.push(raw),
    )
    expect(events).toEqual(["ok", "more"])
  })

  it("skips lines without data: prefix", () => {
    const events: string[] = []
    parseSseLineBuffer("event: x\ndata: y\nid: 1\n", (raw) => events.push(raw))
    expect(events).toEqual(["y"])
  })

  it("handles empty buffer", () => {
    const events: string[] = []
    const remainder = parseSseLineBuffer("", (raw) => events.push(raw))
    expect(events).toEqual([])
    expect(remainder).toBe("")
  })
})
