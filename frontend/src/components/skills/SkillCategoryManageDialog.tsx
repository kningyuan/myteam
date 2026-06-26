import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Pencil, Plus } from "lucide-react"
import { toast } from "sonner"
import {
  createSkillCategory,
  listSkillCategories,
  updateSkillCategory,
  type SkillLibraryItem,
} from "@/lib/api/workflows"
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

type EditState = {
  id: string
  name: string
  description: string
}

export function SkillCategoryManageDialog({
  open,
  onOpenChange,
  onChanged,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged?: () => void
}) {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<SkillLibraryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newId, setNewId] = useState("")
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")

  async function reload() {
    setLoading(true)
    try {
      const rows = await listSkillCategories()
      setCategories(rows)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载分类失败")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!open) return
    void reload()
    setEditing(null)
    setCreating(false)
    setNewId("")
    setNewName("")
    setNewDesc("")
  }, [open])

  async function saveEdit() {
    if (!editing) return
    const name = editing.name.trim()
    if (!name) {
      toast.error("名称不能为空")
      return
    }
    setSaving(true)
    try {
      await updateSkillCategory(editing.id, {
        name,
        description: editing.description.trim(),
      })
      toast.success("分类已更新")
      setEditing(null)
      await reload()
      onChanged?.()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  async function handleCreate() {
    const id = newId.trim().toLowerCase()
    const name = newName.trim()
    if (!id || !name) {
      toast.error("请填写分类 id 与名称")
      return
    }
    setSaving(true)
    try {
      const cat = await createSkillCategory({ id, name, description: newDesc.trim() })
      toast.success("分类已创建")
      setCreating(false)
      setNewId("")
      setNewName("")
      setNewDesc("")
      await reload()
      onChanged?.()
      onOpenChange(false)
      navigate(`/skills/${encodeURIComponent(cat.id)}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "创建失败")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>分类标签管理</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-[var(--color-muted-foreground)]">
          分类即 business/skills 下的目录；Skill 只能挂一个标签，变更标签会移动目录，id 不变。
        </p>

        {loading ? (
          <p className="py-4 text-sm text-[var(--color-muted-foreground)]">加载中…</p>
        ) : categories.length ? (
          <ul className="skill-category-manage-list">
            {categories.map((c) => (
              <li key={c.id} className="skill-category-manage-item">
                {editing?.id === c.id ? (
                  <div className="grid gap-2">
                    <div className="grid gap-1">
                      <Label className="text-xs">显示名称</Label>
                      <Input
                        value={editing.name}
                        onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                      />
                    </div>
                    <div className="grid gap-1">
                      <Label className="text-xs">简介</Label>
                      <Textarea
                        value={editing.description}
                        onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                        rows={2}
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" disabled={saving} onClick={() => void saveEdit()}>
                        {saving ? "保存中…" : "保存"}
                      </Button>
                      <Button size="sm" variant="ghost" disabled={saving} onClick={() => setEditing(null)}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="skill-category-tag skill-category-tag--static">{c.name || c.id}</span>
                        <span className="font-mono text-[10px] text-[var(--color-muted-foreground)]">{c.id}</span>
                        <span className="text-[10px] text-[var(--color-muted-foreground)]">
                          {c.member_count ?? 0} 个成员
                        </span>
                      </div>
                      {c.description ? (
                        <p className="mt-1 text-xs text-[var(--color-muted-foreground)] line-clamp-2">{c.description}</p>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2"
                        onClick={() =>
                          setEditing({
                            id: c.id,
                            name: c.name || c.id,
                            description: c.description || "",
                          })
                        }
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                          onOpenChange(false)
                          navigate(`/skills/${encodeURIComponent(c.id)}`)
                        }}
                      >
                        打开
                      </Button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-4 text-sm text-[var(--color-muted-foreground)]">暂无分类，可新建一个。</p>
        )}

        {creating ? (
          <div className="grid gap-2 border-t border-[var(--color-border)] pt-3">
            <div className="grid gap-1">
              <Label className="text-xs">分类 id（目录名）</Label>
              <Input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="officecli" />
            </div>
            <div className="grid gap-1">
              <Label className="text-xs">显示名称</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Office 文档套件" />
            </div>
            <div className="grid gap-1">
              <Label className="text-xs">简介</Label>
              <Textarea value={newDesc} onChange={(e) => setNewDesc(e.target.value)} rows={2} />
            </div>
            <div className="flex gap-2">
              <Button size="sm" disabled={saving} onClick={() => void handleCreate()}>
                {saving ? "创建中…" : "创建"}
              </Button>
              <Button size="sm" variant="ghost" disabled={saving} onClick={() => setCreating(false)}>
                取消
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" className="w-full" onClick={() => setCreating(true)}>
            <Plus className="h-3.5 w-3.5" />
            新建分类标签
          </Button>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
