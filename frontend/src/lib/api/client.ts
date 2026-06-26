/** Low-level HTTP helpers — no domain logic, only transport. */

export async function hubFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  )
}

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError")
}

/** Abort 时必须 reader.cancel()，否则 SSE 读循环不会结束。 */
export async function readStreamWithAbort(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal | undefined,
  onChunk: (value: Uint8Array) => void,
): Promise<void> {
  const reader = body.getReader()
  const onAbort = () => {
    void reader.cancel().catch(() => {})
  }
  signal?.addEventListener("abort", onAbort, { once: true })
  try {
    while (true) {
      if (signal?.aborted) throw abortError()
      let chunk: ReadableStreamReadResult<Uint8Array>
      try {
        chunk = await reader.read()
      } catch (e) {
        if (signal?.aborted) throw abortError()
        throw e
      }
      if (chunk.done) break
      if (signal?.aborted) throw abortError()
      if (chunk.value) onChunk(chunk.value)
    }
    if (signal?.aborted) throw abortError()
  } finally {
    signal?.removeEventListener("abort", onAbort)
    try {
      await reader.cancel()
    } catch {
      /* ignore */
    }
  }
}

export function parseSseDataLines(
  buffer: string,
  onEvent: (raw: string) => void,
): string {
  const parts = buffer.split("\n\n")
  const remainder = parts.pop() ?? ""
  for (const chunk of parts) {
    for (const line of chunk.split("\n")) {
      if (!line.startsWith("data: ")) continue
      const raw = line.slice(6).trim()
      if (raw === "[DONE]") return ""
      onEvent(raw)
    }
  }
  return remainder
}

export function parseSseLineBuffer(
  buffer: string,
  onEvent: (raw: string) => void,
): string {
  const lines = buffer.split("\n")
  const remainder = lines.pop() ?? ""
  for (const line of lines) {
    const t = line.trim()
    if (!t || t === "data: [DONE]") continue
    if (!t.startsWith("data: ")) continue
    onEvent(t.slice(6))
  }
  return remainder
}
