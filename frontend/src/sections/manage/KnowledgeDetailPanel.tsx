import { useEffect, useState } from "react"
import { toast } from "sonner"
import { deleteMemory, getMemory, updateMemory, type MemoryEntry } from "@/lib/api/projects"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"

export function KnowledgeDetailPanel({
  entry,
  onDelete,
  onUpdated,
}: {
  entry: MemoryEntry
  onDelete: () => void
  onUpdated: (row: MemoryEntry) => void
}) {
  const [detail, setDetail] = useState<MemoryEntry | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [titleDraft, setTitleDraft] = useState("")
  const [contentDraft, setContentDraft] = useState("")
  const [tagsDraft, setTagsDraft] = useState("")
  const [projectDraft, setProjectDraft] = useState("")
  const [taskDraft, setTaskDraft] = useState("")

  useEffect(() => {
    if (!entry.id) {
      setDetail(entry)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    getMemory(entry.id)
      .then((row) => {
        if (!cancelled) setDetail(row)
      })
      .catch(() => {
        if (!cancelled) setDetail(entry)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entry.id, entry])

  const shown = detail ?? entry
  const body = shown.content ?? shown.preview ?? ""

  useEffect(() => {
    setTitleDraft(shown.title || "")
    setContentDraft(body)
    setTagsDraft((shown.tags || []).join(", "))
    setProjectDraft(shown.project_id || "")
    setTaskDraft(shown.task_id || "")
  }, [shown.id, shown.title, shown.project_id, shown.task_id, shown.tags, body])

  async function handleSave() {
    if (!entry.id) return
    setSaving(true)
    try {
      const tags = tagsDraft
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean)
      const row = await updateMemory(entry.id, {
        title: titleDraft.trim(),
        content: contentDraft,
        project_id: projectDraft.trim(),
        task_id: taskDraft.trim(),
        tags,
      })
      setDetail(row)
      setEditing(false)
      onUpdated(row)
      toast.success("知识条目已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!entry.id) return
    if (!window.confirm(`删除知识条目「${shown.title || entry.id}」？\n\n此操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deleteMemory(entry.id)
      toast.success("已删除")
      onDelete()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{shown.title || "（无标题）"}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">#{shown.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!entry.id || loading} onClick={() => setEditing((v) => !v)}>
            {editing ? "取消编辑" : "编辑"}
          </Button>
          {editing && (
            <Button size="sm" disabled={!entry.id || saving} onClick={() => void handleSave()}>
              {saving ? "保存中…" : "保存"}
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
            disabled={!entry.id || deleting}
            onClick={() => void handleDelete()}
          >
            {deleting ? "删除中…" : "删除"}
          </Button>
        </div>
      </div>
      <Separator className="my-5" />
      <dl className="detail-dl">
        <div>
          <dt>项目</dt>
          <dd className="font-mono text-xs">{shown.project_id || "—"}</dd>
        </div>
        <div>
          <dt>任务</dt>
          <dd className="font-mono text-xs">{shown.task_id || "—"}</dd>
        </div>
        <div>
          <dt>时间</dt>
          <dd>{shown.created_at || "—"}</dd>
        </div>
        <div>
          <dt>标签</dt>
          <dd>{(shown.tags || []).join("、 ") || "—"}</dd>
        </div>
      </dl>
      <Separator className="my-5" />
      {editing ? (
        <div className="grid gap-3">
          <div className="grid gap-2">
            <Label>标题</Label>
            <Input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>项目 ID</Label>
              <Input value={projectDraft} onChange={(e) => setProjectDraft(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>任务 ID</Label>
              <Input value={taskDraft} onChange={(e) => setTaskDraft(e.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>标签（逗号分隔）</Label>
            <Input value={tagsDraft} onChange={(e) => setTagsDraft(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label>正文</Label>
            <Textarea rows={14} value={contentDraft} onChange={(e) => setContentDraft(e.target.value)} className="font-mono text-xs" />
          </div>
        </div>
      ) : loading ? (
        <p className="text-sm text-[var(--color-muted-foreground)]">加载正文…</p>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-muted-foreground)]">
          {body || "（无内容）"}
        </p>
      )}
    </div>
  )
}
