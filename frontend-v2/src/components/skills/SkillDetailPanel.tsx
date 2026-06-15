import { useEffect, useState } from "react"
import { Copy, Pencil, Save, X } from "lucide-react"
import { toast } from "sonner"
import {
  deleteSkillLibraryItem,
  getSkillFile,
  updateSkillName,
  type SkillLibraryItem,
  type SkillSection,
} from "@/lib/api/workflows"
import { MarkdownBody } from "@/components/MarkdownBody"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

const KIND_LABEL: Record<string, string> = {
  doc: "文档",
  script: "脚本",
  config: "配置",
  file: "文件",
}

export function SkillDetailPanel({
  item,
  loading,
  onDeleted,
  onUpdated,
}: {
  item: SkillLibraryItem | null
  loading: boolean
  onDeleted: () => void
  onUpdated: (skill: SkillLibraryItem) => void
}) {
  const [content, setContent] = useState("")
  const [activeSectionId, setActiveSectionId] = useState("")
  const [activePath, setActivePath] = useState("")
  const [meta, setMeta] = useState("")
  const [fileLoading, setFileLoading] = useState(false)
  const [editingName, setEditingName] = useState(false)
  const [nameDraft, setNameDraft] = useState("")
  const [savingName, setSavingName] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const sections = item?.sections ?? []
  const files = item?.files ?? []

  useEffect(() => {
    if (!item) return
    setNameDraft(item.name || item.id)
    setEditingName(false)
    const primary = item.body || ""
    setContent(primary)
    setActivePath("")
    setActiveSectionId("")
    setMeta(
      primary
        ? sections.length
          ? `${sections.length} 个章节 · 全文预览`
          : `${files.length} 个文件`
        : "暂无正文",
    )
  }, [item?.id, item?.body, item?.name, sections.length, files.length])

  function showFullBody() {
    if (!item?.body) return
    setContent(item.body)
    setActiveSectionId("__full__")
    setActivePath("")
    setMeta("全文")
  }

  function showSection(section: SkillSection) {
    setContent(section.content || "")
    setActiveSectionId(section.id)
    setActivePath("")
    setMeta(`章节 · ${section.title}`)
  }

  async function loadFile(path: string) {
    if (!item?.id) return
    setFileLoading(true)
    try {
      const f = await getSkillFile(item.id, path)
      if (!f.exists) {
        toast.error("文件不存在")
        return
      }
      setContent(f.content || "")
      setActivePath(path)
      setActiveSectionId("")
      setMeta(`${KIND_LABEL[f.kind || ""] || "文件"} · ${path}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载失败")
    } finally {
      setFileLoading(false)
    }
  }

  async function saveName() {
    if (!item?.id) return
    const next = nameDraft.trim()
    if (!next) {
      toast.error("名称不能为空")
      return
    }
    setSavingName(true)
    try {
      const res = await updateSkillName(item.id, next)
      if (res.skill) onUpdated(res.skill)
      setEditingName(false)
      toast.success("名称已更新")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败")
    } finally {
      setSavingName(false)
    }
  }

  async function handleDelete() {
    if (!item?.id) return
    const kind = item.is_draft ? "抽提条目" : "Skill"
    if (
      !window.confirm(
        `确定删除${kind}「${item.name || item.id}」？\n\n将删除磁盘目录${
          item.is_mountable ? "，并从所有 Agent 挂载列表中移除" : ""
        }。`,
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

  if (loading) {
    return <div className="p-6 text-[var(--color-muted-foreground)]">加载 Skill…</div>
  }

  if (!item) {
    return null
  }

  const busy = loading || fileLoading

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
            {item.is_draft ? <Badge variant="secondary">项目抽提</Badge> : null}
            {!item.is_mountable ? null : (
              <Badge variant="outline" className="text-[10px]">
                可挂载
              </Badge>
            )}
          </div>
          <p className="deliverable-title-id mt-1">{item.id}</p>
          {item.description ? (
            <p className="deliverable-meta mt-2 text-sm leading-relaxed">{item.description}</p>
          ) : (
            <p className="deliverable-meta mt-2">暂无简介</p>
          )}
          <p className="deliverable-meta">{busy ? "加载中…" : meta}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!content} onClick={copyContent}>
            <Copy className="h-3.5 w-3.5" />
            复制
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
            disabled={deleting}
            onClick={() => void handleDelete()}
          >
            {deleting ? "删除中…" : "删除 Skill"}
          </Button>
        </div>
      </div>

      <div className="deliverable-layout">
        <aside className="deliverable-files skill-detail-nav">
          {(sections.length > 0 || item.body) && (
            <div className="skill-detail-nav-block">
              <div className="deliverable-files-title">目录</div>
              <ScrollArea className="max-h-[40vh]">
                <div className="space-y-0.5 p-2">
                  {item.body ? (
                    <button
                      type="button"
                      className={cn(
                        "deliverable-file skill-section-link",
                        activeSectionId === "__full__" && "active",
                      )}
                      onClick={showFullBody}
                    >
                      <span className="deliverable-file-name">全文</span>
                    </button>
                  ) : null}
                  {sections.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={cn(
                        "deliverable-file skill-section-link",
                        activeSectionId === s.id && "active",
                        s.level === 3 && "skill-section-link--l3",
                      )}
                      onClick={() => showSection(s)}
                    >
                      <span className="deliverable-file-name">{s.title}</span>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
          {files.length > 0 && (
            <div className="skill-detail-nav-block">
              <div className="deliverable-files-title">文件</div>
              <ScrollArea className="flex-1 min-h-0">
                <div className="space-y-0.5 p-2">
                  {files.map((f) => (
                    <button
                      key={f.path}
                      type="button"
                      className={cn("deliverable-file", activePath === f.path && "active")}
                      onClick={() => void loadFile(f.path)}
                    >
                      <span className="deliverable-file-kind">{KIND_LABEL[f.kind || ""] || "文件"}</span>
                      <span className="deliverable-file-name">{f.name || f.path}</span>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
        </aside>
        <ScrollArea className="deliverable-body-wrap flex-1 min-h-0">
          <div className="deliverable-body markdown-body">
            {content ? <MarkdownBody content={content} /> : <p className="hint">（无内容）</p>}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
