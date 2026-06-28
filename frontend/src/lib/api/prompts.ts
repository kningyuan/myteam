/** Prompt Templates & Injections API — Strategy Registry CRUD. */

import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

// ── Prompt Templates ──────────────────────────────────────────────

export type PromptTemplateEntry = {
  id: string
  content: string | Record<string, unknown>
  kind: "kind" | "task_type"
  path: string
}

export type PromptTemplateList = {
  kinds: Record<string, PromptTemplateEntry>
  task_types: Record<string, PromptTemplateEntry>
  count: number
}

export async function listPromptTemplates(kind?: string): Promise<PromptTemplateList> {
  const params = kind ? `?kind=${encodeURIComponent(kind)}` : ""
  const data = await hubFetch<PromptTemplateList>(`/api/prompt-templates/${params}`)
  return data
}

export async function getPromptTemplate(templateId: string): Promise<PromptTemplateEntry> {
  return hubFetch<PromptTemplateEntry>(
    `/api/prompt-templates/${encodeURIComponent(templateId)}`,
  )
}

export async function createPromptTemplate(body: {
  id: string
  content: string | Record<string, unknown>
  kind?: "kind" | "task_type"
}): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>("/api/prompt-templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("prompt-templates")
  return data
}

export async function updatePromptTemplate(
  templateId: string,
  body: { content?: string | Record<string, unknown>; kind?: string },
): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>(`/api/prompt-templates/${encodeURIComponent(templateId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("prompt-templates")
  return data
}

export async function deletePromptTemplate(templateId: string): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>(`/api/prompt-templates/${encodeURIComponent(templateId)}`, {
    method: "DELETE",
  })
  invalidateResources("prompt-templates")
  return data
}

// ── Prompt Injections ─────────────────────────────────────────────

export type InjectionBlock = {
  id: string
  content: Record<string, unknown>
}

export type InjectionList = {
  injections: Record<string, InjectionBlock>
  count: number
}

export async function listPromptInjections(): Promise<InjectionList> {
  const data = await hubFetch<InjectionList>("/api/prompt-injections")
  return data
}

export async function getPromptInjection(injectionId: string): Promise<InjectionBlock> {
  return hubFetch<InjectionBlock>(
    `/api/prompt-injections/${encodeURIComponent(injectionId)}`,
  )
}

export async function createPromptInjection(body: {
  id: string
  content: Record<string, unknown>
}): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>("/api/prompt-injections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("prompt-injections")
  return data
}

export async function updatePromptInjection(
  injectionId: string,
  body: { content?: Record<string, unknown> },
): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>(`/api/prompt-injections/${encodeURIComponent(injectionId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("prompt-injections")
  return data
}

export async function deletePromptInjection(injectionId: string): Promise<{ success: boolean; id: string }> {
  const data = await hubFetch<{ success: boolean; id: string }>(`/api/prompt-injections/${encodeURIComponent(injectionId)}`, {
    method: "DELETE",
  })
  invalidateResources("prompt-injections")
  return data
}
