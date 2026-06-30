import { useCallback, useEffect, useMemo, useState } from "react"
import { getAgentDetail, type AgentDetail, type AgentSkillRef, type AgentSummary } from "@/lib/api/agents"
import { listSkillLibrary, listSkillGroups } from "@/lib/api/workflows"
import { listMcpLibrary } from "@/lib/api/mcp"
import { useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { AgentConfigFilesEditor } from "./AgentConfigFilesEditor"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"

export function AgentDetailPanel({
  agent,
  onEdit,
  onDelete,
}: {
  agent: AgentSummary
  onEdit: () => void
  onDelete: () => void
}) {
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [skillNameById, setSkillNameById] = useState<Record<string, string>>({})
  const [mcpNameById, setMcpNameById] = useState<Record<string, string>>({})

  useEffect(() => {
    Promise.all([listSkillLibrary(), listSkillGroups(), listMcpLibrary(true)])
      .then(([skills, groups, mcps]) => {
        const map: Record<string, string> = {}
        for (const s of skills) map[s.id] = s.name || s.id
        for (const g of groups) {
          map[g.id] = g.name || g.id
          for (const m of g.members ?? []) map[m.id] = m.name || m.id
        }
        setSkillNameById(map)
        setMcpNameById(Object.fromEntries(mcps.map((m) => [m.id, m.name || m.id])))
      })
      .catch(() => {})
  }, [])

  const reloadDetail = useCallback(() => {
    setLoading(true)
    setLoadError("")
    getAgentDetail(agent.id)
      .then((d) => setDetail(d))
      .catch((e: Error) => {
        setDetail(null)
        setLoadError(e.message)
      })
      .finally(() => setLoading(false))
  }, [agent.id])

  useEffect(() => {
    reloadDetail()
  }, [reloadDetail])

  useOnResourceInvalidate("agents", reloadDetail)

  const backend = detail?.backend ?? agent.backend
  const model = detail?.model ?? agent.model
  const workspace = detail?.workspace
  const skills: AgentSkillRef[] = detail?.skills ?? []
  const mcps = detail?.mcp_servers ?? []

  function skillLabel(skill: AgentSkillRef): string {
    return skill.name || skillNameById[skill.skill_id] || skill.skill_id
  }

  function mcpLabel(serverId: string, name?: string): string {
    return name || mcpNameById[serverId] || serverId
  }

  const workspaceFiles = useMemo(() => detail?.files ?? {}, [detail])
  const sharedRules = useMemo(() => detail?.shared_rules ?? {}, [detail])
  const sharedRuleMeta = useMemo(
    () => detail?.shared_rule_files ?? [],
    [detail],
  )

  return (
    <div className="agent-detail-layout">
      <div className="workspace-panel agent-detail-meta">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{agent.name || agent.id}</h2>
            <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{agent.id}</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={onEdit}>
              编辑
            </Button>
            <Button size="sm" variant="outline" onClick={onDelete}>
              删除
            </Button>
          </div>
        </div>
        {agent.description && (
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">{agent.description}</p>
        )}
        <Separator className="my-5" />
        {loading ? (
          <p className="text-sm text-[var(--color-muted-foreground)]">加载配置…</p>
        ) : loadError ? (
          <p className="text-sm text-[var(--color-destructive)]">{loadError}</p>
        ) : (
          <dl className="detail-dl agent-detail-dl">
            <div>
              <dt>后端</dt>
              <dd>{backend || "—"}</dd>
            </div>
            <div>
              <dt>模型</dt>
              <dd>{model || "—"}</dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>工作目录</dt>
              <dd className="font-mono text-xs break-all">{workspace || "—"}</dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>挂载 Skill</dt>
              <dd>
                {skills.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((s) => (
                      <Badge
                        key={s.skill_id}
                        variant={s.available === false ? "outline" : "default"}
                        title={s.skill_id}
                        className={s.available === false ? "badge-skill-missing" : ""}
                      >
                        {skillLabel(s)}
                        {s.available === false ? " 源缺失" : ""}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未挂载（Agent 不可使用任何 Skill）"
                )}
              </dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>挂载 MCP</dt>
              <dd>
                {mcps.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {mcps.map((m) => (
                      <Badge
                        key={m.server_id}
                        variant={m.enabled === false ? "outline" : "default"}
                        title={m.server_id}
                      >
                        {mcpLabel(m.server_id, m.name)}
                        {m.enabled === false ? "（已停用）" : ""}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未挂载（点击「编辑」勾选 MCP；须先在 MCP 页启用服务）"
                )}
              </dd>
            </div>
          </dl>
        )}
      </div>

      <AgentConfigFilesEditor
        agentId={agent.id}
        workspaceFiles={workspaceFiles}
        sharedRules={sharedRules}
        sharedRuleMeta={sharedRuleMeta}
        loading={loading}
      />
    </div>
  )
}
