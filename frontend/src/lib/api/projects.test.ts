import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  listProjects,
  getProject,
  runProject,
  cancelProject,
  deleteProject,
  getProjectOverview,
  getProjectCost,
  getTaskDetail,
  projectWorkflowLabel,
  listMemory,
  createMemory,
} from "./projects"
import { subscribeResource } from "@/lib/dataRefresh"

function mockFetchResponse(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? "OK" : "Error",
    json: async () => data,
  })
}

describe("projects API", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  // ─── listProjects (field mapping) ───────────────────────

  it("listProjects maps backend title→name and returns array", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse({
        projects: [
          { id: "p1", title: "项目一", status: "completed", progress: 100 },
        ],
      }),
    )
    const result = await listProjects()
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe("p1")
    expect(result[0].name).toBe("项目一")
    expect(result[0].status).toBe("completed")
  })

  it("listProjects falls back to id when title missing", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse({
        projects: [{ id: "p2", status: "running" }],
      }),
    )
    const result = await listProjects()
    expect(result[0].name).toBe("p2")
  })

  it("listProjects maps workflow_label into meta", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse({
        projects: [{ id: "p3", workflow_label: "research" }],
      }),
    )
    const result = await listProjects()
    expect(result[0].meta?.workflow).toBe("research")
    expect(result[0].meta?.workflow_label).toBe("research")
  })

  it("listProjects returns empty array when projects is null", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ projects: null }))
    const result = await listProjects()
    expect(result).toEqual([])
  })

  // ─── getProject (overview→detail mapping) ───────────────

  it("getProject maps overview to ProjectDetail", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse({
        project_id: "p1",
        title: "测试项目",
        status: "running",
        goal: "build something",
        tasks: [{ id: "t1", name: "task 1", status: "in_progress" }],
      }),
    )
    const result = await getProject("p1")
    expect(result.id).toBe("p1")
    expect(result.name).toBe("测试项目")
    expect(result.goal).toBe("build something")
    expect(result.tasks).toHaveLength(1)
    expect(result.tasks![0].id).toBe("t1")
  })

  it("getProject falls back to launch.goal when goal missing", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse({
        project_id: "p2",
        launch: { goal: "from launch" },
      }),
    )
    const result = await getProject("p2")
    expect(result.goal).toBe("from launch")
  })

  // ─── runProject ─────────────────────────────────────────

  it("runProject sends POST with goal and invalidates projects", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ project_id: "new-p" }))
    const fn = vi.fn()
    const u = subscribeResource("projects", fn)
    const result = await runProject({ goal: "write tests" })
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/projects/run")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ goal: "write tests" })
    expect(result).toEqual({ project_id: "new-p" })
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── cancelProject ──────────────────────────────────────

  it("cancelProject sends POST and invalidates", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ success: true }))
    const fn = vi.fn()
    const u = subscribeResource("projects", fn)
    await cancelProject("p1")
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/projects/p1/cancel")
    expect(init.method).toBe("POST")
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── deleteProject ──────────────────────────────────────

  it("deleteProject sends DELETE and invalidates", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({}))
    const fn = vi.fn()
    const u = subscribeResource("projects", fn)
    await deleteProject("p1")
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/projects/p1")
    expect(init.method).toBe("DELETE")
    expect(fn).toHaveBeenCalledTimes(1)
    u()
  })

  // ─── getProjectOverview / getProjectCost ────────────────

  it("getProjectOverview calls obs overview path", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ project_id: "p1" }))
    await getProjectOverview("p1")
    expect(fetch).toHaveBeenCalledWith(
      "/api/obs/projects/p1/overview",
      undefined,
    )
  })

  it("getProjectCost calls obs cost path", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ project: 1000 }))
    await getProjectCost("p1")
    expect(fetch).toHaveBeenCalledWith("/api/obs/projects/p1/cost", undefined)
  })

  // ─── getTaskDetail ──────────────────────────────────────

  it("getTaskDetail calls correct obs path with encoded ids", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ task: { id: "t1" }, interactions: [] }))
    await getTaskDetail("p1", "t1")
    expect(fetch).toHaveBeenCalledWith(
      "/api/obs/projects/p1/tasks/t1",
      undefined,
    )
  })

  // ─── projectWorkflowLabel (pure function) ───────────────

  it("projectWorkflowLabel returns label when present", () => {
    expect(projectWorkflowLabel({ workflow_label: "research" })).toBe("research")
  })

  it("projectWorkflowLabel falls back to launch.workflow_label", () => {
    expect(
      projectWorkflowLabel({ workflow_label: "", launch: { workflow_label: "dev" } }),
    ).toBe("dev")
  })

  it("projectWorkflowLabel returns 自由规划 when both empty", () => {
    expect(projectWorkflowLabel({ workflow_label: "" })).toBe("自由规划")
  })

  // ─── listMemory ─────────────────────────────────────────

  it("listMemory builds query params correctly", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ memory: [{ id: 1 }] }))
    await listMemory({ limit: 50, text: "keyword", projectId: "p1", kind: "kb" })
    const [path] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toContain("/api/obs/memory?")
    expect(path).toContain("limit=50")
    expect(path).toContain("text=keyword")
    expect(path).toContain("project_id=p1")
    expect(path).toContain("kind=kb")
  })

  it("listMemory returns empty array when memory is null", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ memory: null }))
    const result = await listMemory()
    expect(result).toEqual([])
  })

  // ─── createMemory ───────────────────────────────────────

  it("createMemory sends POST with correct body", async () => {
    vi.stubGlobal("fetch", mockFetchResponse({ memory: { id: 1, title: "test" } }))
    const result = await createMemory({
      project_id: "p1",
      title: "test",
    })
    const [path, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(path).toBe("/api/obs/memory")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ project_id: "p1", title: "test" })
    expect(result.id).toBe(1)
  })
})
