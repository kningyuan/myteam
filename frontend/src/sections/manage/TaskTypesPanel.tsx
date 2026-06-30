import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  createTaskType,
  deleteTaskType,
  listOutcomeKinds,
  suggestTaskType,
  updateTaskType,
  type OutcomeKind,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { matchQuery } from "@/components/manage/ManageSearchBar"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Badge } from "@/components/ui/badge"
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
import { TaskTypeDetailPanel } from "./TaskTypeDetailPanel"

export function TaskTypesPanel({ types }: { types: TaskTypeSummary[] }) {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [kinds, setKinds] = useState<OutcomeKind[]>([])
  const [typeEditOpen, setTypeEditOpen] = useState(false)
  const [typeEditMode, setTypeEditMode] = useState<"create" | "edit">("create")
  const [typeEditDesc, setTypeEditDesc] = useState("")
  const [typeEditId, setTypeEditId] = useState("")
  const [typeEditName, setTypeEditName] = useState("")
  const [typeEditKind, setTypeEditKind] = useState("artifact")
  const [typeEditSections, setTypeEditSections] = useState("")
  const [typeEditBusy, setTypeEditBusy] = useState(false)

  useEffect(() => {
    listOutcomeKinds()
      .then((k) => {
        setKinds(k)
        if (k[0]) setTypeEditKind(k[0].id)
      })
      .catch(() => {})
  }, [])

  const filteredTypes = useMemo(
    () =>
      sortByModifiedDesc(
        types.filter((t) =>
          matchQuery(
            search,
            t.task_type,
            t.display_name,
            t.outcome_kind,
            t.outcome_form_label,
            t.gate_algorithm,
            ...(t.gate_checks || []),
          ),
        ),
      ),
    [types, search],
  )

  const selectedType = types.find((t) => t.task_type === itemId) ?? null
  const kindMap = Object.fromEntries(kinds.map((k) => [k.id, k]))

  function openTaskTypeEdit(row: TaskTypeSummary | null) {
    const isNew = !row
    setTypeEditMode(isNew ? "create" : "edit")
    setTypeEditDesc(isNew ? "" : row?.display_name || row?.task_type || "")
    setTypeEditId(row?.task_type || "")
    setTypeEditName(row?.display_name || "")
    setTypeEditKind(row?.outcome_kind || kinds[0]?.id || "artifact")
    setTypeEditSections((row?.required_sections || row?.sections?.map((s) => s.name) || []).join(", "))
    setTypeEditOpen(true)
  }

  async function handleSuggestTaskTypeFields() {
    const desc = typeEditDesc.trim()
    if (!desc) {
      toast.error("请先填写任务描述")
      return
    }
    setTypeEditBusy(true)
    try {
      const res = await suggestTaskType(desc)
      if (typeEditMode === "create" && res.task_type) setTypeEditId(res.task_type)
      if (res.display_name) setTypeEditName(res.display_name)
      if (res.outcome_kind) setTypeEditKind(res.outcome_kind)
      if (res.outcome_catalog?.length) setKinds(res.outcome_catalog)
      if (res.required_sections?.length) setTypeEditSections(res.required_sections.join(", "))
      toast.success(res.pattern ? `已推导（${res.pattern}）` : "已推导，可继续编辑")
    } catch (e) {
      toast.error("推导失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setTypeEditBusy(false)
    }
  }

  async function handleSaveTaskType() {
    const taskType = typeEditId.trim()
    if (!taskType) {
      toast.error("类型 ID 不能为空")
      return
    }
    const sections = typeEditSections
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const body = {
      display_name: typeEditName.trim() || taskType,
      outcome_kind: typeEditKind,
      required_sections: sections.length ? sections : ["正文"],
    }
    try {
      if (typeEditMode === "create") {
        await createTaskType({ task_type: taskType, ...body })
      } else {
        await updateTaskType(taskType, body)
      }
      toast.success("任务类型已保存")
      setTypeEditOpen(false)
      navigate(`/manage/task-types/${encodeURIComponent(taskType)}`)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleDeleteType(id: string) {
    if (!window.confirm(`删除任务类型「${id}」？`)) return
    try {
      await deleteTaskType(id)
      toast.success("已删除")
      navigate("/manage/task-types")
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
              <Button size="sm" onClick={() => openTaskTypeEdit(null)}>
                新建
              </Button>
            }
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder="搜索任务类型…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {filteredTypes.map((t) => (
              <ListItemRow
                key={t.task_type}
                name={t.display_name || t.task_type}
                sub={t.outcome_form_label || kindMap[t.outcome_kind]?.form_label_zh}
                tag={t.outcome_kind}
                avatar={t.display_name || t.task_type}
                active={t.task_type === itemId}
                onClick={() => navigate(`/manage/task-types/${encodeURIComponent(t.task_type)}`)}
              />
            ))}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader title="任务类型" description="产出形态与 Gate 规则。" />
          {kinds.length > 0 && (
            <div className="mb-5 flex flex-wrap gap-2">
              {kinds.map((k) => (
                <Badge key={k.id} variant="secondary">
                  {k.form_label_zh}
                </Badge>
              ))}
            </div>
          )}
          {selectedType ? (
            <TaskTypeDetailPanel
              taskType={selectedType}
              kindMap={kindMap}
              onEdit={() => openTaskTypeEdit(selectedType)}
              onDelete={() => handleDeleteType(selectedType.task_type)}
            />
          ) : (
            <WelcomePane title="选择任务类型" description="左侧已列出全部类型，点选一项查看详情。" />
          )}
        </div>
      </DiscordShell>

      <Dialog open={typeEditOpen} onOpenChange={setTypeEditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{typeEditMode === "create" ? "新建任务类型" : "编辑任务类型"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>任务描述（用于推导）</Label>
              <div className="flex gap-2">
                <Textarea
                  rows={2}
                  value={typeEditDesc}
                  onChange={(e) => setTypeEditDesc(e.target.value)}
                  placeholder="例如：撰写产品调研报告"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  disabled={typeEditBusy}
                  onClick={() => void handleSuggestTaskTypeFields()}
                >
                  推导
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>task_type ID</Label>
              <Input
                value={typeEditId}
                readOnly={typeEditMode === "edit"}
                onChange={(e) => setTypeEditId(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={typeEditName} onChange={(e) => setTypeEditName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>产出形态</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={typeEditKind}
                onChange={(e) => setTypeEditKind(e.target.value)}
              >
                {kinds.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.form_label_zh || k.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>章节（逗号分隔）</Label>
              <Input value={typeEditSections} onChange={(e) => setTypeEditSections(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTypeEditOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSaveTaskType()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
