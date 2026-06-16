import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type AgentSummary = {
  id: string
  name?: string
  status?: string
  workspace_ok?: number
  role?: string
  description?: string
  backend?: string
  model?: string
  task_types?: string[]
  skills?: string[]
  mcp_servers?: string[]
  last_message_at?: number
  last_message_preview?: string
  operated_at?: string
}

export type AgentSkillRef = {
  skill_id: string
  name?: string
  available?: boolean
  path?: string | null
}

export type AgentDetail = {
  agent_id: string
  workspace?: string
  backend?: string
  model?: string
  task_types?: string[]
  task_type_labels?: Record<string, string>
  skills?: AgentSkillRef[]
  registry_skills?: string[]
  registry_mcp_servers?: string[]
  deliverable_skills?: AgentSkillRef[]
  mcp_servers?: { server_id: string; name?: string; enabled?: boolean; type?: string }[]
  files?: Record<string, string>
}

export async function listAgents(): Promise<AgentSummary[]> {
  const data = await hubFetch<{ agents: AgentSummary[] }>("/api/agents")
  return data.agents ?? []
}

export async function getAgentRegistry(): Promise<{
  agents: Record<string, { name?: string; role?: string; description?: string }>
}> {
  return hubFetch("/api/agents/registry")
}

export async function getAgentBackendConfig(agentId: string): Promise<{
  backend?: string
  model?: string
}> {
  return hubFetch(`/api/agents/${encodeURIComponent(agentId)}/config`)
}

export async function getAgentDetail(agentId: string): Promise<AgentDetail> {
  return hubFetch(`/api/agents/${encodeURIComponent(agentId)}/detail`)
}

export async function saveAgentWorkspaceFile(
  agentId: string,
  filename: string,
  content: string,
): Promise<{ success?: boolean }> {
  const res = await hubFetch<{ success?: boolean }>(
    `/api/agents/${encodeURIComponent(agentId)}/files/${encodeURIComponent(filename)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
  )
  invalidateResources("agents")
  return res
}

export async function updateAgentManage(
  agentId: string,
  body: Record<string, unknown>,
): Promise<void> {
  await hubFetch(`/api/agents/${encodeURIComponent(agentId)}/manage`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("agents")
}

export async function createAgent(body: {
  description: string
  agent_id: string
  chinese_name: string
  backend?: string
  model?: string
}): Promise<{ agent: AgentSummary }> {
  const res = await hubFetch<{ agent: AgentSummary }>("/api/agents/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("agents")
  return res
}

export async function deleteAgent(agentId: string): Promise<void> {
  await hubFetch(`/api/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" })
  invalidateResources("agents")
}

export async function updateAgentConfig(
  agentId: string,
  body: { backend?: string; model?: string },
): Promise<void> {
  await hubFetch(`/api/agents/${encodeURIComponent(agentId)}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("agents")
}

export async function applyModelToAllAgents(model: string): Promise<void> {
  await hubFetch("/api/agents/apply-model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  })
  invalidateResources("agents")
}

export async function suggestAgentId(description: string): Promise<string> {
  const data = await hubFetch<{ suggested_id?: string }>(
    `/api/agents/suggest-id?description=${encodeURIComponent(description)}`,
  )
  return data.suggested_id ?? ""
}

export async function suggestAgentTaskTypes(body: {
  description: string
  name?: string
  agent_id?: string
}): Promise<{ task_types?: string[]; pattern?: string }> {
  return hubFetch("/api/agents/suggest-task-types", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export async function syncAgentTaskTypes(): Promise<{
  success?: boolean
  count?: number
  updated?: { agent_id: string; task_types: string[] }[]
}> {
  const data = await hubFetch<{
    success?: boolean
    count?: number
    updated?: { agent_id: string; task_types: string[] }[]
  }>("/api/agents/sync-task-types", { method: "POST" })
  invalidateResources("agents")
  return data
}

export async function syncAgentSkills(): Promise<{
  success?: boolean
  count?: number
  updated?: { agent_id: string; skills: string[] }[]
}> {
  const data = await hubFetch<{
    success?: boolean
    count?: number
    updated?: { agent_id: string; skills: string[] }[]
  }>("/api/agents/sync-skills", { method: "POST" })
  invalidateResources("agents")
  return data
}

export async function syncAgentMcp(): Promise<{
  success?: boolean
  agents_md_stripped?: string[]
  cli?: { success?: boolean; count?: number }
}> {
  const data = await hubFetch<{
    success?: boolean
    agents_md_stripped?: string[]
    cli?: { success?: boolean; count?: number }
  }>("/api/agents/sync-mcp", { method: "POST" })
  invalidateResources("agents")
  return data
}
