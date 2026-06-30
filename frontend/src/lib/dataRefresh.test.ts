import { describe, it, expect, vi } from "vitest"
import { subscribeResource, invalidateResources } from "./dataRefresh"


describe("subscribeResource / invalidateResources", () => {
  it("listener is called when matching key is invalidated", () => {
    const fn = vi.fn()
    const unsub = subscribeResource("agents", fn)
    invalidateResources("agents")
    expect(fn).toHaveBeenCalledTimes(1)
    unsub()
  })

  it("listener is NOT called for different key", () => {
    const fn = vi.fn()
    const unsub = subscribeResource("projects", fn)
    invalidateResources("agents")
    expect(fn).not.toHaveBeenCalled()
    unsub()
  })

  it("unsubscribe stops notifications", () => {
    const fn = vi.fn()
    const unsub = subscribeResource("agents", fn)
    unsub()
    invalidateResources("agents")
    expect(fn).not.toHaveBeenCalled()
  })

  it("multiple listeners on same key all called", () => {
    const fn1 = vi.fn()
    const fn2 = vi.fn()
    const u1 = subscribeResource("agents", fn1)
    const u2 = subscribeResource("agents", fn2)
    invalidateResources("agents")
    expect(fn1).toHaveBeenCalledTimes(1)
    expect(fn2).toHaveBeenCalledTimes(1)
    u1()
    u2()
  })

  it("invalidate with no keys is a no-op", () => {
    const fn = vi.fn()
    const unsub = subscribeResource("agents", fn)
    invalidateResources()
    expect(fn).not.toHaveBeenCalled()
    unsub()
  })

  it("invalidate with multiple keys notifies all", () => {
    const fnAgents = vi.fn()
    const fnProjects = vi.fn()
    const u1 = subscribeResource("agents", fnAgents)
    const u2 = subscribeResource("projects", fnProjects)
    invalidateResources("agents", "projects")
    expect(fnAgents).toHaveBeenCalledTimes(1)
    expect(fnProjects).toHaveBeenCalledTimes(1)
    u1()
    u2()
  })

  it("listener error does not block other listeners", () => {
    const fnErr = vi.fn(() => {
      throw new Error("boom")
    })
    const fnOk = vi.fn()
    const u1 = subscribeResource("agents", fnErr)
    const u2 = subscribeResource("agents", fnOk)
    invalidateResources("agents")
    expect(fnErr).toHaveBeenCalledTimes(1)
    expect(fnOk).toHaveBeenCalledTimes(1)
    u1()
    u2()
  })
})

// ─── Dashboard 级联失效 ──────────────────────────────────────

describe("dashboard cascade invalidation", () => {
  it("invalidating 'projects' also invalidates 'dashboard'", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("projects")
    expect(dashFn).toHaveBeenCalledTimes(1)
    u()
  })

  it("invalidating 'groups' also invalidates 'dashboard'", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("groups")
    expect(dashFn).toHaveBeenCalledTimes(1)
    u()
  })

  it("invalidating 'agents' also invalidates 'dashboard'", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("agents")
    expect(dashFn).toHaveBeenCalledTimes(1)
    u()
  })

  it("invalidating 'workflows' also invalidates 'dashboard'", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("workflows")
    expect(dashFn).toHaveBeenCalledTimes(1)
    u()
  })

  it("invalidating 'config' does NOT cascade to dashboard", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("config")
    expect(dashFn).not.toHaveBeenCalled()
    u()
  })

  it("invalidating multiple dashboard deps only triggers dashboard once", () => {
    const dashFn = vi.fn()
    const u = subscribeResource("dashboard", dashFn)
    invalidateResources("projects", "groups", "agents")
    // expandKeys uses Set dedup → dashboard listener called once
    expect(dashFn).toHaveBeenCalledTimes(1)
    u()
  })
})
