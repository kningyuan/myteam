import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  listAgents,
  getAgentDetail,
  getAgentBackendConfig,
  saveAgentWorkspaceFile,
  updateAgentManage,
  createAgent,
  deleteAgent,
  updateAgentConfig,
  applyModelToAllAgents,
  suggestAgentId,
} from "./agents"
import { subscribeResource } from "@/lib/dataRefresh"

function mockFetchResponse(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? "OK" : "Error",
    json: async () => data,
  })
}

describe("agents API", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  // ─── listAgents ─────────────────────────────────────────

  it("listAgents returns agents array", async () => {
    const mockAgents = [{ id: "main", name: "协调" }]
    vi.stubGlobal("fetch", mockFetchResponse({ agents: mockAgents }))
    const result = await listAgents()
    expect(result).toEqual(mockAgents)
    expect(fetch).toHaveBeenCalledWith("/api/agents", undefined)
  })

  it("listAgents returns empty array when agents is null", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ agents: null }))
    const result = await listAgents()
    expect(result).toEqual([])
  })

  it("listAgents returns empty array when agents is missing", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const result = await listAgents()
    expect(result).toEqual([])
  })

  // ─── getAgentDetail ─────────────────────────────────────

  it("getAgentDetail calls correct path with encoded id", async () => {
    const detail = { agent_id: "main", backend: "opencode" }
    vi.stubGlobal("fetch", mockFetchResponse(detail))
    const result = await getAgentDetail("main")
    expect(result).toEqual(detail)
    expect(fetch).toHaveBeenCalledWith("/api/agents/main/detail", undefined)
  })

  it("getAgentDetail encodes special characters in agent id", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ agent_id: "a/b" }))
    await getAgentDetail("a/b")
    expect(fetch).toHaveBeenCalledWith(
      "/api/agents/a%2Fb/detail",
      undefined,
    )
  })

  // ─── getAgentBackendConfig ──────────────────────────────

  it("getAgentBackendConfig calls correct path", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ backend: "opencode", model: "mimo" }))
    const result = await getAgentBackendConfig("dev-1")
    expect(result).toEqual({ backend: "opencode", model: "mimo" })
    expect(fetch).toHaveBeenCalledWith("/api/agents/dev-1/config", undefined)
  })

  // ─── saveAgentWorkspaceFile ─────────────────────────────

  it("saveAgentWorkspaceFile sends PUT with content body", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ success: true }))
    await saveAgentWorkspaceFile("main", "IDENTITY.md", "content here")
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/main/files/IDENTITY.md")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({ content: "content here" })
  })

  it("saveAgentWorkspaceFile invalidates agents resource", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ success: true }))
    const fn = vi.fn()
    const u = subscribeResource("agents", fn)
    await saveAgentWorkspaceFile("main", "AGENTS.md", "x")
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── updateAgentManage ──────────────────────────────────

  it("updateAgentManage sends PUT with body and invalidates", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const fn = vi.fn()
    const u = subscribeResource("agents", fn)
    await updateAgentManage("dev-1", { task_types: ["code"] })
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/dev-1/manage")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({ task_types: ["code"] })
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── createAgent ────────────────────────────────────────

  it("createAgent sends POST with correct body", async () => {
    const agent = { id: "new-agent", name: "新成员" }
    vi.stubGlobal("fetch", mockFetchResponse({ agent }))
    const result = await createAgent({
      description: "a developer",
      agent_id: "new-agent",
      chinese_name: "新成员",
    })
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/create")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({
      description: "a developer",
      agent_id: "new-agent",
      chinese_name: "新成员",
    })
    expect(result).toEqual({ agent })
  })

  // ─── deleteAgent ────────────────────────────────────────

  it("deleteAgent sends DELETE and invalidates", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const fn = vi.fn()
    const u = subscribeResource("agents", fn)
    await deleteAgent("old-agent")
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/old-agent")
    expect(init.method).toBe("DELETE")
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── updateAgentConfig ──────────────────────────────────

  it("updateAgentConfig sends POST with backend/model", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    await updateAgentConfig("main", { backend: "claude", model: "sonnet" })
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/main/config")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ backend: "claude", model: "sonnet" })
  })

  // ─── applyModelToAllAgents ──────────────────────────────

  it("applyModelToAllAgents sends POST with model and invalidates", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const fn = vi.fn()
    const u = subscribeResource("agents", fn)
    await applyModelToAllAgents("mimo-v2.5")
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/agents/apply-model")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ model: "mimo-v2.5" })
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── suggestAgentId ─────────────────────────────────────

  it("suggestAgentId returns suggested_id from response", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ suggested_id: "dev-001" }))
    const result = await suggestAgentId("a backend developer")
    expect(result).toBe("dev-001")
    const [path] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe(
      "/api/agents/suggest-id?description=a%20backend%20developer",
    )
  })

  it("suggestAgentId returns empty string when missing", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const result = await suggestAgentId("test")
    expect(result).toBe("")
  })
})
