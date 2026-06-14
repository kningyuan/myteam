import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type ProjectLaunchConfig = {
  goal?: string
  workflow?: string
  workflow_label?: string
  mode?: string
  mode_label?: string
  token_budget?: number
  template_id?: string
  backend?: string
  review?: boolean
  split?: boolean
  max_cycles?: number
}

export type ProjectOverview = {
  project_id: string
  title?: string
  status?: string
  mode?: string
  workflow?: string
  goal?: string
  launch_error?: string
  created_at?: string
  updated_at?: string
  progress?: number
  tokens?: number
  budget?: number
  budget_ratio?: number
  budget_state?: string
  launch?: ProjectLaunchConfig
  tasks?: {
    id: string
    name?: string
    status?: string
    agent?: string
    dependencies?: string[]
    summary?: string
    loop?: string
  }[]
  iterations?: {
    loop_id?: string
    placeholder_task_id?: string
    state?: string
    current_round?: number
    max_rounds?: number
    body_key?: string
    last_assess_marker?: string
    last_assess_action?: string
    last_assess_matched_rule?: number
    rounds_used?: number
    placeholder_status?: string
  }[]
}

export type ProjectCost = {
  project?: number
  by_task?: Record<string, number>
  by_agent?: Record<string, number>
}

export type ProjectEvent = {
  ts?: string
  kind?: string
  category?: "interaction" | "event"
  task_id?: string
  agent_id?: string
  interaction_id?: string
  status?: string
  attempt?: number
  tokens?: number
  payload?: Record<string, unknown>
}

export type TimelineEvent = {
  seq?: number
  kind?: string
  payload?: Record<string, unknown>
  ts?: string
}

export type MemoryEntry = {
  id?: number
  project_id?: string
  task_id?: string
  title?: string
  tags?: string[]
  created_at?: string
  preview?: string
}

export type ProjectSummary = {
  id: string
  name?: string
  status?: string
  goal?: string
  mode?: string
  progress?: number
  task_count?: number
  updated_at?: string
  meta?: {
    workflow?: string
    hub_kernel_run?: { running?: boolean; error?: string }
  }
}

export type ProjectTask = {
  id: string
  name?: string
  status?: string
  agent?: string
  task_type?: string
  dependencies?: string[]
}

export type ProjectDetail = ProjectSummary & {
  tasks?: ProjectTask[]
}

export type DeliverableFile = {
  path: string
  name?: string
  kind?: string
  location?: string
}

export type DeliverableBundle = {
  exists?: boolean
  content?: string
  base?: string
  project_dir?: string
  files?: DeliverableFile[]
  primary?: { exists?: boolean; content?: string }
}

export type GateFailure = {
  rule?: string
  expected?: string
  actual?: string
}

export type TaskInteractionDetail = {
  interaction_id: string
  kind?: string
  attempt?: number
  status?: string
  liveness?: string
  tokens?: number
  response_ref?: string
  gate_failures?: GateFailure[]
  review?: { passed?: boolean; feedback?: string }
  quality?: { score?: number; known_gaps?: string[]; notes?: string }
}

export type TaskDetail = {
  task: {
    id: string
    name?: string
    status?: string
    agent?: string
    reviewer?: string
    task_type?: string
    meta?: Record<string, unknown>
    fail_reason?: string
    fail_detail?: string
    summary?: string
    ref?: string
  }
  latest_quality?: { score?: number; known_gaps?: string[]; notes?: string }
  interactions: TaskInteractionDetail[]
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const data = await hubFetch<{
    projects: {
      id: string
      title?: string
      status?: string
      mode?: string
      progress?: number
      task_count?: number
      updated_at?: string
    }[]
  }>("/api/obs/projects")
  return (data.projects ?? []).map((p) => ({
    id: p.id,
    name: p.title || p.id,
    status: p.status,
    mode: p.mode,
    progress: p.progress,
    task_count: p.task_count,
    updated_at: p.updated_at,
  }))
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  const ov = await hubFetch<ProjectOverview>(
    `/api/obs/projects/${encodeURIComponent(projectId)}/overview`,
  )
  return {
    id: ov.project_id,
    name: ov.title || ov.project_id,
    status: ov.status,
    goal: ov.goal || ov.launch?.goal,
    meta: { workflow: ov.workflow || ov.launch?.workflow },
    tasks: (ov.tasks ?? []).map((t) => ({
      id: t.id,
      name: t.name,
      status: t.status,
      agent: t.agent,
      dependencies: t.dependencies,
    })),
  }
}

export async function runProject(body: {
  goal: string
  title?: string
  workflow?: string
  mode?: string
  budget?: number
  review?: boolean
  split?: boolean
  max_cycles?: number
}): Promise<{ project_id: string }> {
  const res = await hubFetch<{ project_id: string }>("/api/projects/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("projects")
  return res
}

export async function resumeProject(projectId: string): Promise<{ success?: boolean }> {
  const res = await hubFetch<{ success?: boolean }>(
    `/api/projects/${encodeURIComponent(projectId)}/resume`,
    { method: "POST" },
  )
  invalidateResources("projects")
  return res
}

export async function getProjectRunStatus(
  projectId: string,
): Promise<{ running?: boolean; error?: string }> {
  return hubFetch(`/api/projects/run-status/${encodeURIComponent(projectId)}`)
}

export async function cancelProject(
  projectId: string,
): Promise<{ success?: boolean; message?: string }> {
  const res = await hubFetch<{ success?: boolean; message?: string }>(
    `/api/projects/${encodeURIComponent(projectId)}/cancel`,
    { method: "POST" },
  )
  invalidateResources("projects")
  return res
}

export async function deleteProject(projectId: string): Promise<void> {
  await hubFetch(`/api/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" })
  invalidateResources("projects")
}

export async function getDeliverableMarkdown(projectId: string, taskId: string): Promise<string> {
  const bundle = await getDeliverableBundle(projectId, taskId)
  return bundle.content ?? bundle.primary?.content ?? ""
}

export async function getDeliverableBundle(
  projectId: string,
  taskId: string,
): Promise<DeliverableBundle> {
  return hubFetch(
    `/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}`,
  )
}

export async function getDeliverableFile(
  projectId: string,
  taskId: string,
  path: string,
): Promise<{ exists?: boolean; content?: string; kind?: string }> {
  const q = new URLSearchParams({ path })
  return hubFetch(
    `/api/projects/${encodeURIComponent(projectId)}/deliverable/${encodeURIComponent(taskId)}/file?${q}`,
  )
}

export async function getProjectOverview(projectId: string): Promise<ProjectOverview> {
  return hubFetch(`/api/obs/projects/${encodeURIComponent(projectId)}/overview`)
}

export async function getProjectCost(projectId: string): Promise<ProjectCost> {
  return hubFetch(`/api/obs/projects/${encodeURIComponent(projectId)}/cost`)
}

export async function getProjectFleet(
  projectId: string,
): Promise<{ fleet?: Record<string, string> }> {
  return hubFetch(`/api/obs/projects/${encodeURIComponent(projectId)}/fleet`)
}

export async function getProjectEvents(
  projectId: string,
): Promise<{ events?: ProjectEvent[] }> {
  return hubFetch(`/api/obs/projects/${encodeURIComponent(projectId)}/events`)
}

export async function getInteractionTimeline(
  interactionId: string,
): Promise<{ timeline?: TimelineEvent[] }> {
  return hubFetch(`/api/obs/interactions/${encodeURIComponent(interactionId)}/timeline`)
}

export async function getTaskDetail(projectId: string, taskId: string): Promise<TaskDetail> {
  return hubFetch(
    `/api/obs/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}`,
  )
}

export function subscribeProjectStream(projectId: string, onTick: () => void): () => void {
  const es = new EventSource(`/api/obs/projects/${encodeURIComponent(projectId)}/stream`)
  es.onmessage = (ev) => {
    if (ev.data === "[DONE]") {
      es.close()
      invalidateResources("projects")
      onTick()
      return
    }
    try {
      JSON.parse(ev.data)
      invalidateResources("projects")
      onTick()
    } catch {
      /* ignore */
    }
  }
  es.onerror = () => es.close()
  return () => es.close()
}

export function subscribeInteractionEvents(
  interactionId: string,
  onTick: () => void,
): () => void {
  const es = new EventSource(
    `/api/obs/interactions/${encodeURIComponent(interactionId)}/events`,
  )
  es.onmessage = (ev) => {
    if (ev.data === "[DONE]") {
      es.close()
      onTick()
      return
    }
    onTick()
  }
  es.onerror = () => es.close()
  return () => es.close()
}

export async function listMemory(opts?: {
  limit?: number
  text?: string
  projectId?: string
}): Promise<MemoryEntry[]> {
  const limit = opts?.limit ?? 200
  const params = new URLSearchParams({ limit: String(limit) })
  if (opts?.text?.trim()) params.set("text", opts.text.trim())
  if (opts?.projectId?.trim()) params.set("project_id", opts.projectId.trim())
  const data = await hubFetch<{ memory?: MemoryEntry[] }>(`/api/obs/memory?${params}`)
  return data.memory ?? []
}
