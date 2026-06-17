import { useEffect, useMemo, useState } from "react"
import { Copy, Pencil, Save, X } from "lucide-react"
import { toast } from "sonner"
import {
  deleteSkillLibraryItem,
  getSkillFile,
  moveSkillToCategory,
  updateSkillCategory,
  updateSkillName,
  type SkillLibraryItem,
  type SkillTreeNode,
} from "@/lib/api/workflows"
import { MarkdownBody } from "@/components/MarkdownBody"
import { SkillFileTree } from "@/components/skills/SkillFileTree"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function firstFilePath(nodes: SkillTreeNode[]): string | null {
  for (const node of nodes) {
    if (node.type === "file") return node.path
    if (node.children?.length) {
      const nested = firstFilePath(node.children)
      if (nested) return nested
    }
  }
  return null
}

function hasPath(nodes: SkillTreeNode[], target: string): boolean {
  for (const node of nodes) {
    if (node.type === "file" && node.path === target) return true
    if (node.type === "dir" && node.children?.length && hasPath(node.children, target)) return true
  }
  return false
}

export function SkillDetailPanel({
  item,
  loading,
  categories = [],
  categoryNameById,
  onDeleted,
  onUpdated,
}: {
  item: SkillLibraryItem | null
  loading: boolean
  categories?: SkillLibraryItem[]
  categoryNameById?: Map<string, string>
  onDeleted: () => void
  onUpdated: (skill: SkillLibraryItem) => void
}) {
  const [content, setContent] = useState("")
  const [activePath, setActivePath] = useState("SKILL.md")
  const [fileLoading, setFileLoading] = useState(false)
  const [editingName, setEditingName] = useState(false)
  const [nameDraft, setNameDraft] = useState("")
  const [savingName, setSavingName] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [movingCategory, setMovingCategory] = useState(false)
  const [editingDesc, setEditingDesc] = useState(false)
  const [descDraft, setDescDraft] = useState("")
  const [savingDesc, setSavingDesc] = useState(false)

  const isCategory = item?.kind === "category"
  const tree = item?.tree ?? []

  const defaultPath = useMemo(() => {
    if (isCategory) {
      for (const mid of item?.members ?? []) {
        const p = `${mid.id}/SKILL.md`
        if (hasPath(tree, p)) return p
      }
      return firstFilePath(tree) || ""
    }
    if (hasPath(tree, "SKILL.md")) return "SKILL.md"
    return firstFilePath(tree) || "SKILL.md"
  }, [tree, isCategory, item?.members])

  useEffect(() => {
    if (!item) return
    setNameDraft(item.name || item.id)
    setDescDraft(item.description || "")
    setEditingName(false)
    setEditingDesc(false)
    setActivePath(defaultPath)
  }, [item?.id, item?.name, item?.description, defaultPath])

  useEffect(() => {
    if (!item?.id || !activePath) return
    let cancelled = false
    setFileLoading(true)
    getSkillFile(item.id, activePath)
      .then((f) => {
        if (cancelled) return
        if (!f.exists) {
          setContent("")
          return
        }
        setContent(f.content || "")
      })
      .catch((e) => {
        if (!cancelled) toast.error(e instanceof Error ? e.message : "加载失败")
      })
      .finally(() => {
        if (!cancelled) setFileLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [item?.id, activePath])

  async function saveName() {
    if (!item?.id) return
    const next = nameDraft.trim()
    if (!next) {
      toast.error("名称不能为空")
      return
    }
    setSavingName(true)
    try {
      if (isCategory) {
        const cat = await updateSkillCategory(item.id, { name: next })
        onUpdated(cat)
      } else {
        const res = await updateSkillName(item.id, next)
        if (res.skill) onUpdated(res.skill)
      }
      setEditingName(false)
      toast.success("名称已更新")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败")
    } finally {
      setSavingName(false)
    }
  }

  async function saveDescription() {
    if (!item?.id || !isCategory) return
    setSavingDesc(true)
    try {
      const cat = await updateSkillCategory(item.id, { description: descDraft.trim() })
      onUpdated(cat)
      setEditingDesc(false)
      toast.success("简介已更新")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败")
    } finally {
      setSavingDesc(false)
    }
  }

  async function handleCategoryChange(value: string) {
    if (!item?.id || isCategory) return
    const next = value === "__none__" ? null : value
    setMovingCategory(true)
    try {
      const skill = await moveSkillToCategory(item.id, next)
      onUpdated(skill)
      toast.success(next ? "已移动到分类" : "已移出分类")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "移动失败")
    } finally {
      setMovingCategory(false)
    }
  }

  async function handleDelete() {
    if (!item?.id || isCategory) return
    const kind = item.is_draft ? "抽提条目" : "Skill"
    const symlinkNote = item.is_symlink ? "\n\n此外部 Skill 为软链，删除只会移除挂载，不会删除上游目录。" : ""
    if (
      !window.confirm(
        `确定删除${kind}「${item.name || item.id}」？\n\n将删除 business/skills 下的挂载${
          item.is_mountable ? "，并从所有 Agent 挂载列表中移除" : ""
        }。${symlinkNote}`,
      )
    ) {
      return
    }
    setDeleting(true)
    try {
      const res = await deleteSkillLibraryItem(item.id)
      const n = res.unmounted_count ?? 0
      if (n > 0) {
        toast.success(`已删除；已从 ${n} 个 Agent 取消挂载`)
      } else {
        toast.success("已删除")
      }
      onDeleted()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败")
    } finally {
      setDeleting(false)
    }
  }

  function copyContent() {
    if (!content) return
    navigator.clipboard.writeText(content).then(
      () => toast.success("已复制"),
      () => toast.error("复制失败"),
    )
  }

  const activeKind = useMemo(() => {
    function find(nodes: SkillTreeNode[]): string | undefined {
      for (const node of nodes) {
        if (node.type === "file" && node.path === activePath) return node.kind
        if (node.children?.length) {
          const k = find(node.children)
          if (k) return k
        }
      }
      return undefined
    }
    return find(tree)
  }, [tree, activePath])

  if (loading) {
    return <div className="p-6 text-[var(--color-muted-foreground)]">加载 Skill…</div>
  }

  if (!item) {
    return null
  }

  const busy = loading || fileLoading
  const isMarkdown = activePath.endsWith(".md") || activeKind === "doc"
  const currentCategory = item.category_dir || item.group_id || "__none__"
  const currentCategoryLabel =
    currentCategory !== "__none__"
      ? categoryNameById?.get(currentCategory) || categories.find((c) => c.id === currentCategory)?.name || currentCategory
      : null

  return (
    <div className="deliverable-workspace skill-detail-workspace">
      <div className="deliverable-head">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {editingName ? (
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={nameDraft}
                  onChange={(e) => setNameDraft(e.target.value)}
                  className="h-8 max-w-xs text-sm font-semibold"
                  autoFocus
                />
                <Button size="sm" variant="default" disabled={savingName} onClick={() => void saveName()}>
                  <Save className="h-3.5 w-3.5" />
                  保存
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={savingName}
                  onClick={() => {
                    setNameDraft(item.name || item.id)
                    setEditingName(false)
                  }}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ) : (
              <>
                <h1 className="deliverable-title m-0">{item.name || item.id}</h1>
                <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setEditingName(true)}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
            {isCategory ? (
              <Badge variant="secondary">Skill 分类 · {item.member_count ?? item.members?.length ?? 0} 个成员</Badge>
            ) : null}
            {!isCategory && currentCategoryLabel ? (
              <Badge variant="outline" className="text-[10px]">
                {currentCategoryLabel}
              </Badge>
            ) : null}
            {!isCategory && item.is_draft ? <Badge variant="secondary">项目抽提</Badge> : null}
            {!isCategory && item.is_symlink ? (
              <Badge variant="outline" className="text-[10px]" title={item.link_target}>
                外部软链
              </Badge>
            ) : null}
            {!isCategory && item.is_mountable ? (
              <Badge variant="outline" className="text-[10px]">
                可挂载
              </Badge>
            ) : null}
          </div>
          <p className="deliverable-title-id mt-1">{item.id}</p>
          {item.path ? <p className="deliverable-meta mt-1 font-mono text-xs opacity-80">{item.path}</p> : null}
          {!isCategory && item.is_symlink && item.link_target ? (
            <p className="deliverable-meta mt-1 font-mono text-xs opacity-80">→ {item.link_target}</p>
          ) : null}
          {!isCategory ? (
            item.description ? (
              <p className="deliverable-meta mt-2 text-sm leading-relaxed">{item.description}</p>
            ) : (
              <p className="deliverable-meta mt-2">暂无简介</p>
            )
          ) : null}
          {isCategory ? (
            <div className="mt-3 max-w-lg">
              {editingDesc ? (
                <div className="grid gap-2">
                  <Label className="text-xs text-[var(--color-muted-foreground)]">分类简介</Label>
                  <Textarea value={descDraft} onChange={(e) => setDescDraft(e.target.value)} rows={3} />
                  <div className="flex gap-2">
                    <Button size="sm" disabled={savingDesc} onClick={() => void saveDescription()}>
                      {savingDesc ? "保存中…" : "保存简介"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={savingDesc}
                      onClick={() => {
                        setDescDraft(item.description || "")
                        setEditingDesc(false)
                      }}
                    >
                      取消
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2">
                  <p className="deliverable-meta flex-1 text-sm leading-relaxed">
                    {item.description?.trim() || "暂无简介"}
                  </p>
                  <Button size="sm" variant="ghost" className="h-7 px-2 shrink-0" onClick={() => setEditingDesc(true)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </div>
          ) : null}
          {!isCategory ? (
            <div className="mt-3 max-w-xs">
              <Label className="text-xs text-[var(--color-muted-foreground)]">分类标签（唯一，变更会移动目录）</Label>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                {currentCategoryLabel ? (
                  <span className="skill-category-tag skill-category-tag--static">{currentCategoryLabel}</span>
                ) : (
                  <span className="text-xs text-[var(--color-muted-foreground)]">无（顶层独立 Skill）</span>
                )}
                <Select
                  value={currentCategory}
                  disabled={movingCategory}
                  onValueChange={(v) => void handleCategoryChange(v)}
                >
                  <SelectTrigger className="h-8 w-[140px]">
                    <SelectValue placeholder="选择分类" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">无（顶层独立 Skill）</SelectItem>
                    {categories.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name || c.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!content} onClick={copyContent}>
            <Copy className="h-3.5 w-3.5" />
            复制
          </Button>
          {!isCategory ? (
            <Button
              size="sm"
              variant="outline"
              className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
              disabled={deleting}
              onClick={() => void handleDelete()}
            >
              {deleting ? "删除中…" : "删除 Skill"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="deliverable-layout">
        <aside className="deliverable-files skill-detail-nav">
          <div className="skill-detail-nav-block">
            <div className="deliverable-files-title">{isCategory ? "成员目录" : "目录"}</div>
            <ScrollArea className="flex-1 min-h-0">
              <SkillFileTree
                tree={tree}
                activePath={activePath}
                defaultPath={defaultPath}
                onSelectFile={setActivePath}
              />
            </ScrollArea>
          </div>
        </aside>
        <ScrollArea className="deliverable-body-wrap flex-1 min-h-0">
          <div className="deliverable-body markdown-body">
            {busy ? (
              <p className="hint">加载中…</p>
            ) : content ? (
              isMarkdown ? (
                <MarkdownBody content={content} />
              ) : (
                <pre className="skill-file-raw overflow-x-auto text-sm leading-relaxed">{content}</pre>
              )
            ) : activePath ? (
              <p className="hint">（无内容）</p>
            ) : (
              <p className="hint">在左侧选择成员目录中的文件</p>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
