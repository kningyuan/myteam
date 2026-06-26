import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type McpServerSummary = {
  id: string
  name: string
  description?: string
  enabled: boolean
  type: "local" | "remote"
  command?: string[]
  url?: string
  environment?: Record<string, string>
  headers?: Record<string, string>
  timeout?: number
  is_mountable?: boolean
}

export async function listMcpLibrary(includeDisabled = true): Promise<McpServerSummary[]> {
  const path = includeDisabled
    ? "/api/mcp/library"
    : "/api/mcp/library?include_disabled=false"
  const data = await hubFetch<{ servers: McpServerSummary[] }>(path)
  return data.servers ?? []
}

export async function getMcpServer(serverId: string): Promise<McpServerSummary> {
  return hubFetch(`/api/mcp/library/${encodeURIComponent(serverId)}`)
}

export async function createMcpServer(body: {
  id: string
  name: string
  description?: string
  enabled?: boolean
  type?: "local" | "remote"
  command?: string[]
  url?: string
  environment?: Record<string, string>
  headers?: Record<string, string>
  timeout?: number
}): Promise<{ success?: boolean; server?: McpServerSummary }> {
  const res = await hubFetch<{ success?: boolean; server?: McpServerSummary }>("/api/mcp/library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("mcp-library", "agents")
  return res
}

export async function updateMcpServer(
  serverId: string,
  body: Partial<McpServerSummary>,
): Promise<{ success?: boolean; server?: McpServerSummary }> {
  const res = await hubFetch<{ success?: boolean; server?: McpServerSummary }>(
    `/api/mcp/library/${encodeURIComponent(serverId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  )
  invalidateResources("mcp-library", "agents")
  return res
}

export async function setMcpEnabled(serverId: string, enabled: boolean): Promise<void> {
  await hubFetch(`/api/mcp/library/${encodeURIComponent(serverId)}/enabled`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  })
  invalidateResources("mcp-library", "agents")
}

export async function deleteMcpServer(serverId: string): Promise<void> {
  await hubFetch(`/api/mcp/library/${encodeURIComponent(serverId)}`, { method: "DELETE" })
  invalidateResources("mcp-library", "agents")
}
