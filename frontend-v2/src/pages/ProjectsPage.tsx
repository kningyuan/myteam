import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { listProjects, type ProjectSummary } from "@/lib/api/projects"
import { EmptyState, PageHeader, statusLabel, StatusBadge } from "@/components/ui/page"

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载项目…</p>
  }

  return (
    <div className="space-y-6">
      <PageHeader title="项目" description="查看每个项目的目标、进度、任务编排与交付物。" />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          无法加载项目：{error}
        </div>
      )}

      {!projects.length ? (
        <EmptyState title="暂无项目" description="请先在经典版界面创建或导入项目。" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {projects.map((p) => (
            <Link key={p.id} to={`/projects/${encodeURIComponent(p.id)}`}>
              <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 transition hover:border-[var(--color-brand)]/40 hover:bg-[var(--color-accent)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold">{p.name || p.id}</h2>
                    {p.meta?.workflow && (
                      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">流程：{p.meta.workflow}</p>
                    )}
                  </div>
                  <StatusBadge status={p.status} label={statusLabel(p.status)} />
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                  {p.goal || "暂无目标描述"}
                </p>
              </article>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
