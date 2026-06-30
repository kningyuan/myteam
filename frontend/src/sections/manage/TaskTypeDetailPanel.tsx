import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { gateLabel } from "@/components/ui/page"
import type { OutcomeKind, TaskTypeSummary } from "@/lib/api/workflows"

export function TaskTypeDetailPanel({
  taskType,
  kindMap,
  onEdit,
  onDelete,
}: {
  taskType: TaskTypeSummary
  kindMap: Record<string, OutcomeKind>
  onEdit: () => void
  onDelete: () => void
}) {
  const meta = kindMap[taskType.outcome_kind]
  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{taskType.display_name || taskType.task_type}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{taskType.task_type}</p>
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
      <Separator className="my-5" />
      <dl className="detail-dl">
        <div>
          <dt>产出形态</dt>
          <dd>{taskType.outcome_form_label || meta?.form_label_zh || "—"}</dd>
        </div>
        <div>
          <dt>Gate 算法</dt>
          <dd>{gateLabel(taskType.gate_algorithm || meta?.gate_algorithm)}</dd>
        </div>
        <div>
          <dt>交付要求</dt>
          <dd>{(taskType.gate_checks || []).join(" · ") || "—"}</dd>
        </div>
      </dl>
      {(taskType.sections || []).length > 0 && (
        <>
          <Separator className="my-5" />
          <h3 className="mb-3 text-sm font-semibold">章节结构</h3>
          <ul className="space-y-2 text-sm text-[var(--color-muted-foreground)]">
            {taskType.sections!.map((s) => (
              <li key={s.name}>
                <span className="font-medium text-[var(--color-foreground)]">{s.name}</span>
                {s.description ? ` — ${s.description}` : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
