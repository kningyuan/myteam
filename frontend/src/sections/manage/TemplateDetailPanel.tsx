import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import type { DeliveryTemplateSummary } from "@/lib/api/workflows"

export function TemplateDetailPanel({
  template,
  onEdit,
  onDelete,
}: {
  template: DeliveryTemplateSummary
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{template.display_name || template.id}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{template.id}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onEdit}>
            编辑 YAML
          </Button>
          <Button size="sm" variant="outline" onClick={onDelete}>
            删除
          </Button>
        </div>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
        {template.description || "（无描述）"}
      </p>
      <Separator className="my-5" />
      <p className="text-sm">绑定任务类型：{(template.task_types || []).join("、 ") || "未限定"}</p>
    </div>
  )
}
