import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useResourceQuery } from "./useResourceQuery"
import { invalidateResources } from "@/lib/dataRefresh"

describe("useResourceQuery", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("fetches data on mount and returns it", async () => {
    const fetcher = vi.fn().mockResolvedValue({ count: 42 })
    const { result } = renderHook(() => useResourceQuery("agents", fetcher, { count: 0 }))

    // 初始 loading=true
    expect(result.current.loading).toBe(true)
    expect(result.current.data).toEqual({ count: 0 })

    // 等待 fetcher 完成
    await vi.waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.data).toEqual({ count: 42 })
    expect(result.current.error).toBe("")
  })

  it("sets error message when fetcher throws", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network failed"))
    const { result } = renderHook(() =>
      useResourceQuery("projects", fetcher, { count: 0 }),
    )

    await vi.waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.error).toBe("network failed")
    expect(result.current.data).toEqual({ count: 0 })
  })

  it("uses generic error for non-Error throws", async () => {
    const fetcher = vi.fn().mockRejectedValue("string error")
    const { result } = renderHook(() =>
      useResourceQuery("projects", fetcher, { count: 0 }),
    )

    await vi.waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.error).toBe("加载失败")
  })

  it("reload() triggers a new fetch", async () => {
    let callCount = 0
    const fetcher = vi.fn(() => {
      callCount++
      return Promise.resolve({ n: callCount })
    })
    const { result } = renderHook(() => useResourceQuery("agents", fetcher, { n: 0 }))

    await vi.waitFor(() => expect(result.current.data).toEqual({ n: 1 }))

    act(() => {
      result.current.reload()
    })

    await vi.waitFor(() => expect(result.current.data).toEqual({ n: 2 }))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("invalidateResources triggers silent reload (no loading flicker)", async () => {
    let callCount = 0
    const fetcher = vi.fn(() => {
      callCount++
      return Promise.resolve({ n: callCount })
    })
    const { result } = renderHook(() => useResourceQuery("agents", fetcher, { n: 0 }))

    await vi.waitFor(() => expect(result.current.data).toEqual({ n: 1 }))
    expect(result.current.loading).toBe(false)

    // trigger silent reload via invalidation
    invalidateResources("agents")

    await vi.waitFor(() => expect(result.current.data).toEqual({ n: 2 }))
    // silent reload should NOT set loading to true
    expect(result.current.loading).toBe(false)
  })

  it("invalidateResources of different key does NOT trigger reload", async () => {
    const fetcher = vi.fn().mockResolvedValue({ count: 1 })
    const { result } = renderHook(() => useResourceQuery("agents", fetcher, { count: 0 }))

    await vi.waitFor(() => expect(result.current.data).toEqual({ count: 1 }))
    const initialCallCount = fetcher.mock.calls.length

    // invalidate a different resource key
    invalidateResources("projects")

    // wait a bit to ensure no fetch happens
    await new Promise((r) => setTimeout(r, 50))
    expect(fetcher.mock.calls.length).toBe(initialCallCount)
  })

  it("dashboard cascade triggers agents subscriber via projects invalidation", async () => {
    // agents subscriber should NOT be triggered by projects invalidation
    // (cascade only goes to "dashboard", not to "agents")
    const fetcher = vi.fn().mockResolvedValue({ count: 1 })
    const { result } = renderHook(() => useResourceQuery("agents", fetcher, { count: 0 }))

    await vi.waitFor(() => expect(result.current.data).toEqual({ count: 1 }))
    const initialCallCount = fetcher.mock.calls.length

    // invalidating "projects" cascades to "dashboard" but NOT to "agents"
    invalidateResources("projects")

    await new Promise((r) => setTimeout(r, 50))
    expect(fetcher.mock.calls.length).toBe(initialCallCount)
  })

  it("unmounting unsubscribes from resource invalidation", async () => {
    const fetcher = vi.fn().mockResolvedValue({ count: 1 })
    const { result, unmount } = renderHook(() =>
      useResourceQuery("agents", fetcher, { count: 0 }),
    )

    await vi.waitFor(() => expect(result.current.data).toEqual({ count: 1 }))
    const initialCallCount = fetcher.mock.calls.length

    unmount()

    // after unmount, invalidation should not trigger fetcher
    invalidateResources("agents")
    await new Promise((r) => setTimeout(r, 50))
    expect(fetcher.mock.calls.length).toBe(initialCallCount)
  })
})
