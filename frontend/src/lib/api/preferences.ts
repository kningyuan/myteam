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

// ──────────────────────────────────────────────────────────────────
// Preference sections — CRUD over config/preference_sections.json
// (pref_router: /api/preferences/sections)
// ──────────────────────────────────────────────────────────────────

export type PreferenceSection = {
  id: string
  name?: string
  description?: string
  content?: string
  order?: number
  visible?: boolean
}

export type PreferenceSectionInput = {
  id?: string
  name?: string
  description?: string
  content?: string
  order?: number
  visible?: boolean
}

export type PreferenceSectionResponse = { success: boolean; section: PreferenceSection }

export async function listPreferenceSections(): Promise<{
  sections: PreferenceSection[]
  count: number
}> {
  return hubFetch("/api/preferences/sections")
}

export async function createPreferenceSection(
  data: PreferenceSectionInput,
): Promise<PreferenceSectionResponse> {
  return hubFetch("/api/preferences/sections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export async function updatePreferenceSection(
  id: string,
  data: PreferenceSectionInput,
): Promise<PreferenceSectionResponse> {
  return hubFetch(`/api/preferences/sections/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export async function deletePreferenceSection(id: string): Promise<{ success: boolean; id: string }> {
  return hubFetch(`/api/preferences/sections/${encodeURIComponent(id)}`, { method: "DELETE" })
}
