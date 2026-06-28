import { useEffect, useMemo, useState, useCallback } from "react"
import { useNavigate, useParams, NavLink } from "react-router-dom"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import {
  createSkillCategory,
  deleteSkillCategory,
  deleteSkillLibraryItem,
  getSkillLibraryItem,
  listSkillCategories,
  listSkillLibrary,
  listSkillPending,
  approveSkillPending,
  rejectSkillPending,
  type SkillLibraryItem,
  type SkillPendingItem,
} from "@/lib/api/workflows"
import { useResourceQuery, useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { SkillDetailPanel } from "@/components/skills/SkillDetailPanel"
import { SkillCategoryManageDialog } from "@/components/skills/SkillCategoryManageDialog"
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
import { cn } from "@/lib/utils"
import { sortByModifiedDesc } from "@/lib/sortByModified"

type SidebarEntry = {
  id: string
  kind: "category" | "skill"
  name: string
  sub: string
  isDraft?: boolean
  updated_at?: number
}

function SkillOverviewHome({
  entries,
  categories,
  loading,
  error,
  onSelect,
}: {
  entries: SidebarEntry[]
  categories: SkillLibraryItem[]
  loading: boolean
  error: string
  onSelect: (id: string) => void
}) {
  if (loading) return <div className="p-6 text-[var(--color-muted-foreground)]">加载 Skill…</div>
  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-[var(--color-destructive)]">Skill 加载失败：{error}</p>
      </div>
    )
  }
  if (!entries.length) {
    return (
      <WelcomePane
        title="暂无 Skill"
        description="左侧可新建展示分类（写入 categories.yaml）；每个 Skill 目录固定在 business/skills/<id>/。"
      />
    )
  }

  return (
    <div className="skill-home">
      <header className="skill-home-head">
        <div>
          <h1 className="text-lg font-semibold">Skill 总览</h1>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            分类与独立 Skill 同级展示；点分类可浏览其下全部成员目录与文件
          </p>
          {categories.length ? (
            <div className="skill-home-category-tags">
              {categories.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="skill-category-tag"
                  onClick={() => onSelect(c.id)}
                >
                  {c.name || c.id}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </header>
      <div className="skill-home-grid">
        {entries.map((e) => (
          <button key={`${e.kind}:${e.id}`} type="button" className="skill-home-card" onClick={() => onSelect(e.id)}>
            <div className="skill-home-card-top">
              <span className="skill-home-card-name">{e.name}</span>
              {e.kind === "category" ? (
                <span className="skill-home-card-tag skill-home-card-tag--ok">分类</span>
              ) : e.isDraft ? (
                <span className="skill-home-card-tag">抽提</span>
              ) : (
                <span className="skill-home-card-tag skill-home-card-tag--ok">Skill</span>
              )}
            </div>
            <span className="skill-home-card-id">{e.id}</span>
            <p className="skill-home-card-desc">{e.sub?.trim() || "暂无简介"}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

export function SkillsSection() {
  const { skillId } = useParams()
  const navigate = useNavigate()
  const {
    data: library,
    loading: loadingLibrary,
    error: libraryError,
    reload: reloadLibrary,
  } = useResourceQuery("skill-library", listSkillLibrary, [])
  const {
    data: categories,
    loading: loadingCategories,
    error: categoriesError,
    reload: reloadCategories,
  } = useResourceQuery("skill-categories", listSkillCategories, [])
  const [detail, setDetail] = useState<SkillLibraryItem | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)
  const [newCatId, setNewCatId] = useState("")
  const [newCatName, setNewCatName] = useState("")
  const [creating, setCreating] = useState(false)
  const [pendingItems, setPendingItems] = useState<SkillPendingItem[]>([])
  const [pendingOpen, setPendingOpen] = useState(false)
  const [pendingBusy, setPendingBusy] = useState<string | null>(null)

  const reloadPending = useCallback(() => {
    listSkillPending()
      .then(setPendingItems)
      .catch(() => setPendingItems([]))
  }, [])

  useEffect(() => {
    reloadPending()
  }, [reloadPending])

  const memberIdSet = useMemo(() => {
    const ids = new Set<string>()
    for (const s of library ?? []) {
      if (s.category_dir || s.group_id) ids.add(s.id)
    }
    return ids
  }, [library])

  const standaloneSkills = useMemo(
    () => (library ?? []).filter((s) => !memberIdSet.has(s.id)),
    [library, memberIdSet],
  )

  const categoryNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const c of categories ?? []) {
      map.set(c.id, c.name || c.id)
    }
    return map
  }, [categories])

  const sortedCategories = useMemo(
    () => sortByModifiedDesc(categories ?? []),
    [categories],
  )

  const sidebarEntries = useMemo((): SidebarEntry[] => {
    const cats: SidebarEntry[] = sortedCategories.map((c) => ({
      id: c.id,
      kind: "category" as const,
      name: c.name || c.id,
      sub: c.description || `${c.member_count ?? 0} 个成员`,
      updated_at: c.updated_at,
    }))
    const skills: SidebarEntry[] = standaloneSkills.map((s) => ({
      id: s.id,
      kind: "skill" as const,
      name: s.name || s.id,
      sub: s.description || s.id,
      isDraft: s.is_draft,
      updated_at: s.updated_at,
    }))
    return sortByModifiedDesc([...cats, ...skills])
  }, [sortedCategories, standaloneSkills])

  const reloadDetail = useCallback(() => {
    if (!skillId) {
      setDetail(null)
      return
    }
    setLoadingDetail(true)
    getSkillLibraryItem(skillId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false))
  }, [skillId])

  useEffect(() => {
    reloadDetail()
  }, [reloadDetail])

  useOnResourceInvalidate("skill-library", () => {
    reloadDetail()
    void reloadLibrary()
    void reloadCategories()
  })
  useOnResourceInvalidate("skill-categories", () => {
    void reloadCategories()
    void reloadLibrary()
  })

  const loading = loadingLibrary || loadingCategories
  const error = libraryError || categoriesError

  async function handleCreateCategory() {
    const id = newCatId.trim().toLowerCase()
    const name = newCatName.trim()
    if (!id || !name) {
      toast.error("请填写分类 id 与名称")
      return
    }
    setCreating(true)
    try {
      const cat = await createSkillCategory({ id, name })
      toast.success("分类已创建")
      setCreateOpen(false)
      setNewCatId("")
      setNewCatName("")
      void reloadCategories()
      navigate(`/skills/${encodeURIComponent(cat.id)}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "创建失败")
    } finally {
      setCreating(false)
    }
  }

  async function handleApprovePending(id: string) {
    setPendingBusy(id)
    try {
      await approveSkillPending(id)
      toast.success("已批准并写入 Skill")
      reloadPending()
      void reloadLibrary()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "批准失败")
    } finally {
      setPendingBusy(null)
    }
  }

  async function handleRejectPending(id: string) {
    setPendingBusy(id)
    try {
      await rejectSkillPending(id)
      toast.success("已拒绝")
      reloadPending()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "拒绝失败")
    } finally {
      setPendingBusy(null)
    }
  }

  async function handleDeleteSkill(sid: string, name?: string) {
    if (!confirm(`确定要删除 Skill「${name || sid}」吗？将同时从所有 Agent 卸载。`)) return
    try {
      await deleteSkillLibraryItem(sid)
      toast.success(`已删除 Skill「${name || sid}」`)
      void reloadLibrary()
      void reloadCategories()
      if (skillId === sid) navigate("/skills")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败")
    }
  }

  async function handleDeleteCategory(cid: string, name?: string) {
    if (!confirm(`确定要删除分类「${name || cid}」吗？\n分类下的 Skill 不会被删除，仅移除分类标签。`)) return
    try {
      await deleteSkillCategory(cid)
      toast.success(`已删除分类「${name || cid}」`)
      void reloadLibrary()
      void reloadCategories()
      if (skillId === cid) navigate("/skills")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败")
    }
  }

  return (
    <DiscordShell
      list={
        <ListColumn title="Skill">
          <div className="skill-list-toolbar">
            <NavLink
              to="/skills"
              end
              className={({ isActive }) => cn("skill-list-overview-btn", isActive && !skillId && "active")}
            >
              总览
            </NavLink>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-[11px]"
              onClick={() => setManageOpen(true)}
              title="管理分类标签"
            >
              标签
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-[11px]"
              onClick={() => setPendingOpen(true)}
              title="Skill review 待审批"
            >
              待审批{pendingItems.length ? ` (${pendingItems.length})` : ""}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="ml-auto h-6 w-6 p-0"
              onClick={() => setCreateOpen(true)}
              title="新建 Skill 分类"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          {(sortedCategories ?? []).length ? (
            <div className="skill-category-tags">
              {sortedCategories.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={cn("skill-category-tag", skillId === c.id && "active")}
                  onClick={() => navigate(`/skills/${encodeURIComponent(c.id)}`)}
                  title={c.description || c.id}
                >
                  {c.name || c.id}
                </button>
              ))}
            </div>
          ) : null}
          {loading ? (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
          ) : error ? (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-destructive)]">加载失败</p>
          ) : sidebarEntries.length ? (
            sidebarEntries.map((e) => (
              <ListItemRow
                key={`${e.kind}:${e.id}`}
                name={e.name}
                sub={e.sub}
                tag={e.kind === "category" ? "分类" : undefined}
                avatar={e.kind === "category" ? "类" : e.isDraft ? "↑" : "SK"}
                active={e.id === skillId}
                onClick={() => navigate(`/skills/${encodeURIComponent(e.id)}`)}
                onDelete={
                  e.kind === "skill"
                    ? () => handleDeleteSkill(e.id, e.name)
                    : () => handleDeleteCategory(e.id, e.name)
                }
              />
            ))
          ) : (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">暂无 Skill</p>
          )}
        </ListColumn>
      }
    >
      <div className={cn("discord-main-scroll workspace-scroll", !skillId && "skill-home-main")}>
        {skillId ? (
          <SkillDetailPanel
            item={detail}
            loading={loadingDetail}
            categories={categories ?? []}
            categoryNameById={categoryNameById}
            onDeleted={() => {
              void reloadLibrary()
              void reloadCategories()
              navigate("/skills")
            }}
            onUpdated={(entry) => {
              setDetail(entry)
              void reloadLibrary()
              void reloadCategories()
            }}
          />
        ) : (
          <SkillOverviewHome
            entries={sidebarEntries}
            categories={sortedCategories}
            loading={loading}
            error={error}
            onSelect={(id) => navigate(`/skills/${encodeURIComponent(id)}`)}
          />
        )}
      </div>

      <Dialog open={pendingOpen} onOpenChange={setPendingOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Skill review 待审批（_pending/）</DialogTitle>
          </DialogHeader>
          {pendingItems.length ? (
            <div className="max-h-[60vh] space-y-3 overflow-y-auto py-2">
              {pendingItems.map((p) => (
                <div key={p.pending_id} className="rounded-md border border-[var(--color-border)] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium">{p.skill_id || "（无 skill_id）"}</p>
                      <p className="font-mono text-xs text-[var(--color-muted-foreground)]">
                        {p.pending_id} · {p.action || "patch"} · {p.task_id}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={pendingBusy === p.pending_id}
                        onClick={() => void handleApprovePending(p.pending_id)}
                      >
                        批准
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={pendingBusy === p.pending_id}
                        onClick={() => void handleRejectPending(p.pending_id)}
                      >
                        拒绝
                      </Button>
                    </div>
                  </div>
                  {p.patch_preview ? (
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-[var(--color-muted)]/30 p-2 font-mono text-xs">
                      {p.patch_preview}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="py-4 text-sm text-[var(--color-muted-foreground)]">暂无待审批包</p>
          )}
        </DialogContent>
      </Dialog>

      <SkillCategoryManageDialog
        open={manageOpen}
        onOpenChange={setManageOpen}
        onChanged={() => {
          void reloadCategories()
          void reloadLibrary()
        }}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建 Skill 分类</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>分类 id（英文目录名）</Label>
              <Input
                value={newCatId}
                onChange={(e) => setNewCatId(e.target.value)}
                placeholder="例如 design-tools"
              />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={newCatName} onChange={(e) => setNewCatName(e.target.value)} placeholder="例如 设计工具" />
            </div>
            <p className="hint text-xs">写入 business/skills/categories.yaml，不会创建物理子目录。</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button disabled={creating} onClick={() => void handleCreateCategory()}>
              {creating ? "创建中…" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DiscordShell>
  )
}
