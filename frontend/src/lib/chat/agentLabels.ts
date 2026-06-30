import type { AgentSummary } from "@/lib/api/agents"

export const ROUNDTABLE_PHASE_LABELS: Record<string, string> = {
  thinking: "独立思考",
  opening: "立论",
  facilitator: "主持汇总",
  consensus: "最佳实践终稿",
  consensus_draft: "最佳实践草案",
  consensus_confirm: "最佳实践确认",
  alignment: "对齐回应",
  objection: "分歧交锋",
  turn_failed: "发言失败",
}

export function buildAgentNameLookup(
  catalog: AgentSummary[],
  registry?: Record<string, { name?: string }>,
  overrides?: Record<string, string>,
): Map<string, string> {
  const map = new Map<string, string>()
  for (const [id, info] of Object.entries(registry || {})) {
    const name = info?.name?.trim()
    if (name) map.set(id, name)
  }
  for (const agent of catalog) {
    const name = agent.name?.trim()
    if (name) map.set(agent.id, name)
  }
  for (const [id, name] of Object.entries(overrides || {})) {
    if (name?.trim()) map.set(id, name.trim())
  }
  return map
}

export function agentDisplayName(
  id: string,
  lookup: Map<string, string>,
): string {
  if (id === "user") return "你"
  if (id === "system") return "系统"
  if (id === "all") return "ALL"
  return lookup.get(id) || id
}

export function formatMemberList(
  members: string[],
  lookup: Map<string, string>,
): string {
  return members.map((m) => agentDisplayName(m, lookup)).join("、 ")
}

export function roundtablePhaseLabel(phase?: string): string {
  if (!phase) return "准备中"
  return ROUNDTABLE_PHASE_LABELS[phase] || phase
}
