import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  deletePreferenceSection,
  updatePreferenceSection,
  type PreferenceSection,
} from "@/lib/api/preferences"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"

export function PreferencesLibraryPanel({
  section,
  onUpdated,
  onDeleted,
}: {
  section: PreferenceSection
  onUpdated: (row: PreferenceSection) => void
  onDeleted: () => void
}) {
  const [nameDraft, setNameDraft] = useState("")
  const [descDraft, setDescDraft] = useState("")
  const [contentDraft, setContentDraft] = useState("")
  const [orderDraft, setOrderDraft] = useState("0")
  const [visibleDraft, setVisibleDraft] = useState(true)
  const [saved, setSaved] = useState({ name: "", description: "", content: "", order: 0, visible: true })
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const name = section.name || ""
    const description = section.description || ""
    const content = section.content || ""
    const order = typeof section.order === "number" ? section.order : 0
    const visible = section.visible !== false
    setNameDraft(name)
    setDescDraft(description)
    setContentDraft(content)
    setOrderDraft(String(order))
    setVisibleDraft(visible)
    setSaved({ name, description, content, order, visible })
  }, [section.id, section.name, section.description, section.content, section.order, section.visible])

  const orderNum = Number(orderDraft)
  const isDirty =
    nameDraft !== saved.name ||
    descDraft !== saved.description ||
    contentDraft !== saved.content ||
    (Number.isFinite(orderNum) ? orderNum : 0) !== saved.order ||
    visibleDraft !== saved.visible

  async function handleSave() {
    setSaving(true)
    try {
      const res = await updatePreferenceSection(section.id, {
        name: nameDraft.trim(),
        description: descDraft.trim(),
        content: contentDraft,
        order: Number.isFinite(orderNum) ? orderNum : 0,
        visible: visibleDraft,
      })
      const row = { ...section, ...res.section }
      onUpdated(row)
      toast.success("偏好分节已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`删除偏好分节「${section.name || section.id}」？\n\n此操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deletePreferenceSection(section.id)
      toast.success("已删除")
      onDeleted()
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
          <h2 className="text-lg font-semibold">{section.name || "（未命名）"}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">#{section.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={!isDirty || saving} onClick={() => void handleSave()}>
            {saving ? "保存中…" : "保存"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
            disabled={deleting}
            onClick={() => void handleDelete()}
          >
            {deleting ? "删除中…" : "删除"}
          </Button>
        </div>
      </div>

      <Separator className="my-5" />

      <div className="grid gap-3">
        <div className="grid gap-2">
          <Label>名称</Label>
          <Input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} placeholder="例如: 风格偏好" />
        </div>
        <div className="grid gap-2">
          <Label>描述</Label>
          <Input value={descDraft} onChange={(e) => setDescDraft(e.target.value)} placeholder="一句话说明此分节用途" />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label>排序 (order)</Label>
            <Input
              type="number"
              value={orderDraft}
              onChange={(e) => setOrderDraft(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label>是否启用</Label>
            <Button
              size="sm"
              variant={visibleDraft ? "default" : "outline"}
              className="justify-start"
              onClick={() => setVisibleDraft((v) => !v)}
            >
              {visibleDraft ? "启用（注入）" : "隐藏（不注入）"}
            </Button>
          </div>
        </div>
        <div className="grid gap-2">
          <Label>正文（Markdown）</Label>
          <Textarea
            rows={18}
            value={contentDraft}
            onChange={(e) => setContentDraft(e.target.value)}
            className="font-mono text-xs leading-relaxed"
            placeholder="- 交付物须含可验证证据&#10;- 调研报告须列扫描路径≥5"
          />
        </div>
      </div>
    </div>
  )
}
