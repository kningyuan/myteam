import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { gateLabel } from "@/components/ui/page"
import {
  saveDeliveryTemplate,
  type DeliveryTemplateSummary,
  type OutcomeKind,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { DeliveryTemplateEditor } from "./DeliveryTemplateEditor"

export function TaskTypeDetailPanel({
  taskType,
  kindMap,
  templates,
  onEdit,
  onDelete,
  onTemplateCreated,
  onDeleteTemplate,
}: {
  taskType: TaskTypeSummary
  kindMap: Record<string, OutcomeKind>
  templates: DeliveryTemplateSummary[]
  onEdit: () => void
  onDelete: () => void
  onTemplateCreated?: () => void
  onDeleteTemplate?: (id: string) => void
}) {
  const meta = kindMap[taskType.outcome_kind]
  const navigate = useNavigate()
  const [newTplOpen, setNewTplOpen] = useState(false)
  const [newTplId, setNewTplId] = useState("")
  const [newTplName, setNewTplName] = useState("")
  const [newTplDesc, setNewTplDesc] = useState("")
  const [newTplSections, setNewTplSections] = useState("")
  const [newTplDefault, setNewTplDefault] = useState(false)
  const [newTplBusy, setNewTplBusy] = useState(false)

  const taskTypeTemplates = useMemo(
    () =>
      templates.filter((t) => (t.task_types || []).includes(taskType.task_type)),
    [templates, taskType.task_type],
  )

  function openNewTpl() {
    setNewTplId("")
    setNewTplName("")
    setNewTplDesc("")
    setNewTplSections((taskType.required_sections || taskType.sections?.map((s) => s.name) || []).join(", "))
    setNewTplDefault(taskTypeTemplates.length === 0)
    setNewTplOpen(true)
  }

  async function handleCreateTpl() {
    const id = newTplId.trim()
    if (!id) {
      toast.error("模板 ID 不能为空")
      return
    }
    const sections = newTplSections
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    setNewTplBusy(true)
    try {
      await saveDeliveryTemplate(null, {
        id,
        display_name: newTplName.trim() || id,
        description: newTplDesc.trim(),
        task_types: [taskType.task_type],
        required_sections: sections.length ? sections : ["正文"],
        default_for: newTplDefault ? taskType.task_type : "",
      })
      toast.success("模板已创建")
      setNewTplOpen(false)
      onTemplateCreated?.()
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setNewTplBusy(false)
    }
  }

  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{taskType.display_name || taskType.task_type}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">
            {taskType.task_type}
          </p>
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

      <Separator className="my-5" />
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">交付模板（{taskTypeTemplates.length}）</h3>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            每个模板带独立的章节结构与质量约束（check_rules）。
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={openNewTpl}>
          新建模板
        </Button>
      </div>

      {taskTypeTemplates.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
          该任务类型暂无交付模板，点「新建模板」创建。
        </p>
      ) : (
        <div className="mt-3 grid gap-2">
          {taskTypeTemplates.map((t) => (
            <DeliveryTemplateEditor
              key={t.id}
              template={t}
              outcomeKind={taskType.outcome_kind}
              onSaved={() => {
                onTemplateCreated?.()
                navigate(`/manage/task-types/${encodeURIComponent(taskType.task_type)}`)
              }}
              onDelete={() => onDeleteTemplate?.(t.id)}
            />
          ))}
        </div>
      )}

      <Dialog open={newTplOpen} onOpenChange={setNewTplOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新建交付模板</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>模板 ID</Label>
              <Input value={newTplId} onChange={(e) => setNewTplId(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={newTplName} onChange={(e) => setNewTplName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>描述</Label>
              <Textarea rows={2} value={newTplDesc} onChange={(e) => setNewTplDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>章节（逗号分隔）</Label>
              <Input value={newTplSections} onChange={(e) => setNewTplSections(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--color-primary)]"
                checked={newTplDefault}
                onChange={(e) => setNewTplDefault(e.target.checked)}
              />
              设为该任务类型的默认模板（default_for）
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewTplOpen(false)}>
              取消
            </Button>
            <Button disabled={newTplBusy} onClick={() => void handleCreateTpl()}>
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
