import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { listGroups, type GroupSummary } from "@/lib/api/groups"
import { EmptyState, PageHeader } from "@/components/ui/page"

export function GroupsPage() {
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listGroups()
      .then(setGroups)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-[var(--color-muted-foreground)]">加载群组…</p>

  const active = groups.filter((g) => g.status !== "dissolved")

  return (
    <div className="space-y-6">
      <PageHeader title="群组" description="项目协作群与独立讨论组，支持 @Agent 与实时消息。" />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          无法加载群组：{error}
        </div>
      )}

      {!active.length ? (
        <EmptyState title="暂无群组" description="项目启动后会自动建群，也可在经典版界面手动创建。" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {active.map((g) => (
            <Link key={g.id} to={`/groups/${encodeURIComponent(g.id)}`}>
              <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 transition hover:border-[var(--color-brand)]/40">
                <h2 className="font-semibold">{g.name}</h2>
                {g.description && (
                  <p className="mt-2 line-clamp-2 text-sm text-[var(--color-muted-foreground)]">{g.description}</p>
                )}
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-[var(--color-muted-foreground)]">
                  <span>{g.members?.length ?? g.member_count ?? 0} 名成员</span>
                  {g.project_id && <span>关联项目：{g.project_id}</span>}
                </div>
              </article>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
