import { useEffect, useState } from "react"
import {
  listOutcomeKinds,
  listTaskTypes,
  type OutcomeKind,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { EmptyState, gateLabel, PageHeader, Pill } from "@/components/ui/page"

export function TaskTypesPage() {
  const [kinds, setKinds] = useState<OutcomeKind[]>([])
  const [types, setTypes] = useState<TaskTypeSummary[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([listOutcomeKinds(), listTaskTypes()])
      .then(([k, t]) => {
        setKinds(k)
        setTypes(t)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const kindMap = Object.fromEntries(kinds.map((k) => [k.id, k]))

  if (loading) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载任务类型…</p>
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="任务类型"
        description="每种任务对应一种产出形态与交付规范。新建或编辑类型请使用经典版「管理 → 任务类型」。"
      />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-[var(--color-sidebar-fg)]">三种产出形态</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {kinds.map((k) => (
            <div key={k.id} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
              <Pill tone="brand">{k.form_label_zh || k.label}</Pill>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted-foreground)]">{k.summary}</p>
              {(k.covers?.length ?? 0) > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-[var(--color-muted-foreground)]">
                  {k.covers?.slice(0, 4).map((c) => (
                    <li key={c}>· {c}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-[var(--color-sidebar-fg)]">已注册类型</h2>
        {!types.length ? (
          <EmptyState title="暂无任务类型" />
        ) : (
          <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-accent)] text-left text-xs text-[var(--color-muted-foreground)]">
                <tr>
                  <th className="px-4 py-3 font-medium">名称</th>
                  <th className="px-4 py-3 font-medium">产出形态</th>
                  <th className="px-4 py-3 font-medium">交付要求</th>
                  <th className="px-4 py-3 font-medium">执行优先级</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)] bg-[var(--color-card)]">
                {types.map((t) => {
                  const meta = kindMap[t.outcome_kind]
                  const gates = (t.gate_checks || []).slice(0, 3)
                  return (
                    <tr key={t.task_type} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3">
                        <div className="font-medium">{t.display_name || t.task_type}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Pill>{t.outcome_form_label || meta?.form_label_zh || "—"}</Pill>
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--color-muted-foreground)]">
                        {gates.length > 0 ? gates.join(" · ") : gateLabel(t.gate_algorithm || meta?.gate_algorithm)}
                      </td>
                      <td className="px-4 py-3">
                        <ExecutionPriorityCell taskType={t} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function ExecutionPriorityCell({ taskType }: { taskType: TaskTypeSummary }) {
  // Execution priority is derived from:
  // 1. outcome_kind order (artifact=1, discussion=2, decision=3)
  // 2. presence of gate_checks (more checks = higher priority in DAG)
  const kindOrder: Record<string, number> = { artifact: 1, discussion: 2, decision: 3 }
  const basePriority = kindOrder[taskType.outcome_kind] || 99

  const hasChecks = (taskType.gate_checks?.length ?? 0) > 0
  const hasSections = (taskType.sections?.length ?? 0) > 0

  let label = "标准"
  let tone: "default" | "secondary" | "destructive" = "default"

  if (basePriority <= 1 && hasChecks) {
    label = "高（产出物驱动）"
    tone = "destructive"
  } else if (basePriority >= 3) {
    label = "低（决策/讨论）"
    tone = "secondary"
  } else if (hasSections) {
    label = "中（结构化交付）"
    tone = "default"
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        tone === "destructive"
          ? "bg-red-500/10 text-red-300"
          : tone === "secondary"
            ? "bg-gray-500/10 text-gray-300"
            : "bg-blue-500/10 text-blue-300"
      }`}
    >
      {label}
    </span>
  )
}
