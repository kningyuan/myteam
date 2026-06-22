import { hubFetch } from "./client"

export type SingleExecuteTask = {
  task_id: string
  agent_id?: string
  task_type?: string
  intent?: string
  prepared_at?: string
  finished?: boolean
}

export type SingleExecuteProject = {
  project_id: string
  title?: string
  mode?: string
  task_count?: number
  tasks?: SingleExecuteTask[]
}

export type SingleExecuteTaskDetail = SingleExecuteTask & {
  project_id: string
  prompt?: string
  harness_blocks?: string
  deliverable_content?: string
  ledger_content?: string
  deliverable?: string
  ledger?: string
  finish_summary?: {
    finished_at?: string
    kb_ref?: string
    deliverable_bytes?: number
    ledger_bytes?: number
  } | null
}

export async function listSingleExecuteProjects(): Promise<SingleExecuteProject[]> {
  const data = await hubFetch<{ projects?: SingleExecuteProject[] }>("/api/single-execute")
  return data.projects ?? []
}

export async function getSingleExecuteTask(
  projectId: string,
  taskId: string,
): Promise<SingleExecuteTaskDetail> {
  return hubFetch(`/api/single-execute/${encodeURIComponent(projectId)}/${encodeURIComponent(taskId)}`)
}

export async function prepareSingleExecute(body: {
  project_id: string
  task_id: string
  agent_id?: string
  task_type?: string
  intent?: string
}): Promise<{ success: boolean; harness_block_count?: number; harness_blocks?: string[] }> {
  return hubFetch("/api/single-execute/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export async function finishSingleExecute(body: {
  project_id: string
  task_id: string
  agent_id?: string
  task_type?: string
}): Promise<{ success: boolean; kb_ref?: string; finished_at?: string }> {
  return hubFetch("/api/single-execute/finish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
