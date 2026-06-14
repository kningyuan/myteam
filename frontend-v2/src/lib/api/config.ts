import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type BackendSummary = { id: string; name?: string }
export type BackendModel = { id: string; name?: string; default?: boolean }

export type ObsSummary = {
  totals?: {
    projects?: number
    running?: number
    completed?: number
    tokens?: number
  }
  projects?: {
    id: string
    title?: string
    status?: string
    progress?: number
    task_count?: number
  }[]
}

export async function getObsSummary(): Promise<ObsSummary> {
  return hubFetch<ObsSummary>("/api/obs/summary")
}

export async function getSkillConfig(): Promise<Record<string, unknown>> {
  const data = await hubFetch<{ config?: Record<string, unknown> }>("/api/skill-config")
  return data.config ?? {}
}

export async function getConfig(): Promise<Record<string, unknown>> {
  const data = await hubFetch<{ config?: Record<string, unknown> }>("/api/config")
  return data.config ?? {}
}

export async function updateConfig(config: Record<string, unknown>): Promise<void> {
  await hubFetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
  invalidateResources("config")
}

export async function updateSkillConfig(config: Record<string, unknown>): Promise<void> {
  await hubFetch("/api/skill-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
  invalidateResources("config")
}

export async function listBackends(): Promise<BackendSummary[]> {
  const data = await hubFetch<{ backends?: BackendSummary[] }>("/api/backends")
  return data.backends ?? []
}

export async function listBackendModels(backendId: string): Promise<BackendModel[]> {
  const data = await hubFetch<{ models?: BackendModel[] }>(
    `/api/backends/${encodeURIComponent(backendId)}/models`,
  )
  return data.models ?? []
}
