import { useEffect, useState } from "react"
import { listAgents, type AgentSummary } from "@/lib/api/agents"
import { EmptyState, PageHeader, StatusBadge } from "@/components/ui/page"

export function AgentsPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-[var(--color-muted-foreground)]">加载 Agent…</p>

  return (
    <div className="space-y-6">
      <PageHeader title="Agent" description="团队中的 AI 成员。详细配置与后端绑定请在经典版「管理」中操作。" />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>
      )}

      {!agents.length ? (
        <EmptyState title="暂无 Agent" description="请先在经典版界面初始化 Agent 团队。" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <article
              key={a.id}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="font-semibold">{a.name || a.id}</h2>
                  <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">角色标识：{a.id}</p>
                </div>
                <StatusBadge
                  status={a.status === "online" || a.status === "ready" ? "online" : "offline"}
                  label={a.status || "未知"}
                />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
