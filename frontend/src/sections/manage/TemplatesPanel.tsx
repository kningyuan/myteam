import { useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  deleteDeliveryTemplate,
  getDeliveryTemplate,
  saveDeliveryTemplate,
  type DeliveryTemplateSummary,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { matchQuery } from "@/components/manage/ManageSearchBar"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { WorkspaceHeader } from "./WorkspaceHeader"
import { TemplateDetailPanel } from "./TemplateDetailPanel"

export function TemplatesPanel({
  templates,
  types,
}: {
  templates: DeliveryTemplateSummary[]
  types: TaskTypeSummary[]
}) {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [templateFormOpen, setTemplateFormOpen] = useState(false)
  const [templateFormMode, setTemplateFormMode] = useState<"create" | "edit">("create")
  const [templateFormId, setTemplateFormId] = useState("")
  const [templateFormName, setTemplateFormName] = useState("")
  const [templateFormDesc, setTemplateFormDesc] = useState("")
  const [templateFormTaskTypes, setTemplateFormTaskTypes] = useState<string[]>([])
  const [templateFormDefaultFor, setTemplateFormDefaultFor] = useState("")
  const [templateFormSections, setTemplateFormSections] = useState("")
  const [templateFormYaml, setTemplateFormYaml] = useState("")
  const templateImportRef = useRef<HTMLInputElement>(null)

  const filteredTemplates = useMemo(
    () =>
      sortByModifiedDesc(
        templates.filter((t) =>
          matchQuery(search, t.id, t.display_name, t.description, ...(t.task_types || [])),
        ),
      ),
    [templates, search],
  )

  const selectedTemplate = templates.find((t) => t.id === itemId) ?? null

  function openTemplateForm(row: DeliveryTemplateSummary | null) {
    const isNew = !row
    setTemplateFormMode(isNew ? "create" : "edit")
    setTemplateFormId(row?.id || "")
    setTemplateFormName(row?.display_name || "")
    setTemplateFormDesc(row?.description || "")
    setTemplateFormTaskTypes(row?.task_types || [])
    setTemplateFormDefaultFor(row?.default_for || "")
    setTemplateFormSections(
      (row?.sections || [])
        .map((s) => (typeof s === "string" ? s : (s as { name?: string }).name || ""))
        .filter(Boolean)
        .join(", "),
    )
    setTemplateFormYaml("")
    setTemplateFormOpen(true)
    if (!isNew && row?.id) {
      getDeliveryTemplate(row.id)
        .then((detail) => {
          setTemplateFormYaml(detail.yaml || "")
          if (detail.template) {
            setTemplateFormTaskTypes(detail.template.task_types || row.task_types || [])
            setTemplateFormDefaultFor(detail.template.default_for || row.default_for || "")
          }
        })
        .catch(() => {})
    }
  }

  async function handleSaveTemplateForm() {
    const id = templateFormId.trim()
    if (!id) {
      toast.error("模板 ID 不能为空")
      return
    }
    if (!templateFormTaskTypes.length) {
      toast.error("请至少绑定一个任务类型")
      return
    }
    const body = {
      id,
      display_name: templateFormName.trim() || id,
      description: templateFormDesc.trim(),
      task_types: templateFormTaskTypes,
      default_for: templateFormDefaultFor.trim(),
      required_sections: templateFormSections
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
      yaml: templateFormYaml.trim(),
    }
    try {
      await saveDeliveryTemplate(templateFormMode === "edit" ? id : null, body)
      toast.success("模板已保存")
      setTemplateFormOpen(false)
      navigate(`/manage/templates/${encodeURIComponent(id)}`)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleTemplateYamlImport(file: File | null) {
    if (!file) return
    try {
      const text = await file.text()
      await saveDeliveryTemplate(null, { yaml: text })
      toast.success("模板已导入")
      if (templateImportRef.current) templateImportRef.current.value = ""
    } catch (e) {
      toast.error("导入失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleDeleteTemplate(id: string) {
    if (!window.confirm(`删除模板「${id}」？`)) return
    try {
      await deleteDeliveryTemplate(id)
      toast.success("已删除")
      navigate("/manage/templates")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            action={
              <div className="flex gap-1">
                <Button size="sm" variant="outline" onClick={() => templateImportRef.current?.click()}>
                  导入
                </Button>
                <Button size="sm" onClick={() => openTemplateForm(null)}>
                  新建
                </Button>
                <input
                  ref={templateImportRef}
                  type="file"
                  accept=".yaml,.yml,.txt"
                  className="hidden"
                  onChange={(e) => void handleTemplateYamlImport(e.target.files?.[0] ?? null)}
                />
              </div>
            }
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder="搜索模板…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {filteredTemplates.map((t) => (
              <ListItemRow
                key={t.id}
                name={t.display_name || t.id}
                sub={(t.task_types || []).join(", ") || "通用"}
                avatar={t.display_name || t.id}
                active={t.id === itemId}
                onClick={() => navigate(`/manage/templates/${encodeURIComponent(t.id)}`)}
              />
            ))}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader title="交付模板" description="结构化交付契约（YAML）。" />
          {selectedTemplate ? (
            <TemplateDetailPanel
              template={selectedTemplate}
              onEdit={() => openTemplateForm(selectedTemplate)}
              onDelete={() => handleDeleteTemplate(selectedTemplate.id)}
            />
          ) : (
            <WelcomePane title="选择模板" description="左侧已列出全部模板，点选一项查看或编辑。" />
          )}
        </div>
      </DiscordShell>

      <Dialog open={templateFormOpen} onOpenChange={setTemplateFormOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{templateFormMode === "create" ? "新建交付模板" : "编辑交付模板"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>模板 ID</Label>
                <Input
                  value={templateFormId}
                  readOnly={templateFormMode === "edit"}
                  onChange={(e) => setTemplateFormId(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label>显示名称</Label>
                <Input value={templateFormName} onChange={(e) => setTemplateFormName(e.target.value)} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label>描述</Label>
              <Textarea rows={2} value={templateFormDesc} onChange={(e) => setTemplateFormDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>绑定任务类型（多选）</Label>
              <select
                multiple
                className="min-h-[88px] rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                value={templateFormTaskTypes}
                onChange={(e) => {
                  const picked = Array.from(e.target.selectedOptions).map((o) => o.value)
                  setTemplateFormTaskTypes(picked)
                  if (templateFormDefaultFor && !picked.includes(templateFormDefaultFor)) {
                    setTemplateFormDefaultFor("")
                  }
                }}
              >
                {types.map((t) => (
                  <option key={t.task_type} value={t.task_type}>
                    {t.display_name || t.task_type}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>默认任务类型</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={templateFormDefaultFor}
                onChange={(e) => setTemplateFormDefaultFor(e.target.value)}
              >
                <option value="">（不设置）</option>
                {templateFormTaskTypes.map((id) => (
                  <option key={id} value={id}>
                    {types.find((t) => t.task_type === id)?.display_name || id}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>章节（逗号分隔）</Label>
              <Input value={templateFormSections} onChange={(e) => setTemplateFormSections(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>YAML（可选）</Label>
              <Textarea
                rows={8}
                value={templateFormYaml}
                onChange={(e) => setTemplateFormYaml(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTemplateFormOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSaveTemplateForm()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
