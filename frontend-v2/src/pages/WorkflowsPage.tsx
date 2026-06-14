import { useEffect, useState } from "react"
import { listWorkflows, type WorkflowSummary } from "@/lib/api/workflows"
import { EmptyState, PageHeader, Pill } from "@/components/ui/page"

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [error, setError] = useState("")

  useEffect(() => {
    listWorkflows()
      .then(setWorkflows)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="工作流"
        description="已注册的业务流程模板。编辑 YAML 请使用经典版「流程」页。"
      />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>
      )}

      {!workflows.length ? (
        <EmptyState title="暂无工作流" />
      ) : (
        <div className="space-y-3">
          {workflows.map((w) => (
            <article
              key={w.id}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="font-semibold">{w.id}</h2>
                <Pill>v{w.version || "?"}</Pill>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                {w.description || "（无描述）"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-muted-foreground)]">
                <span>{w.task_count ?? "—"} 个任务</span>
                {(w.roster?.length ?? 0) > 0 && <span>成员：{w.roster?.join("、")}</span>}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
