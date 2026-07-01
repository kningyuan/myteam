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
    updated_at?: string
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

/** 递归合并：对象深合并，数组与标量整体替换。 */
function deepMerge(
  target: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...target }
  for (const [k, v] of Object.entries(patch)) {
    const tv = out[k]
    if (
      v !== null &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      tv !== null &&
      typeof tv === "object" &&
      !Array.isArray(tv)
    ) {
      out[k] = deepMerge(tv as Record<string, unknown>, v as Record<string, unknown>)
    } else {
      out[k] = v
    }
  }
  return out
}

/**
 * 读取最新 config → 合并 patch → 整体写回。
 * 多个设置 Panel 各自只编辑 system_config 的一个子集；直接 PUT 全量会互相覆盖，
 * 因此保存前先重新拉取最新值再做深合并。
 */
export async function patchConfig(patch: Record<string, unknown>): Promise<void> {
  const latest = await getConfig()
  await updateConfig(deepMerge(latest, patch))
}

export async function patchSkillConfig(patch: Record<string, unknown>): Promise<void> {
  const latest = await getSkillConfig()
  await updateSkillConfig(deepMerge(latest, patch))
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

export async function initHub(): Promise<{ message?: string }> {
  const data = await hubFetch<{ message?: string }>("/api/init", { method: "POST" })
  invalidateResources("dashboard", "agents", "projects")
  return data
}

export async function runDemo(): Promise<{ project_id?: string }> {
  const data = await hubFetch<{ project_id?: string }>("/api/demo", { method: "POST" })
  invalidateResources("dashboard", "projects")
  return data
}
