import { hubFetch } from "./client"

export type PreferencesLibrary = {
  content: string
  path?: string
  scope?: string
  legacy_per_agent_files?: { agent_id: string; path: string }[]
  legacy_warning?: string | null
}

export async function getPreferencesLibrary(): Promise<PreferencesLibrary> {
  return hubFetch("/api/preferences/library")
}

export async function savePreferencesLibrary(content: string): Promise<{
  success: boolean
  synced_agents?: string[]
}> {
  return hubFetch("/api/preferences/library", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  })
}

export async function syncPreferencesToAgents(): Promise<{ success: boolean; synced_agents?: string[] }> {
  return hubFetch("/api/preferences/library/sync", { method: "POST" })
}
