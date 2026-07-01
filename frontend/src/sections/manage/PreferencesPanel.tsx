import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import {
  createPreferenceSection,
  deletePreferenceSection,
  listPreferenceSections,
  savePreferencesLibrary,
  type PreferenceSection,
} from "@/lib/api/preferences"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { PreferencesLibraryPanel } from "@/components/manage/PreferencesLibraryPanel"
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
import { WorkspaceHeader } from "./WorkspaceHeader"

// 按 order 升序排序；order 缺失视为 0
function sortByOrder(sections: PreferenceSection[]): PreferenceSection[] {
  return sections
    .slice()
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
}

// 将可见分节聚合成 USER.md markdown（## name / content），供 savePreferencesLibrary 写入并 sync
function aggregateSectionsToMarkdown(sections: PreferenceSection[]): string {
  const visible = sortByOrder(sections).filter((s) => s.visible !== false)
  const lines: string[] = ["# 团队偏好", ""]
  for (const s of visible) {
    const title = (s.name || s.id).trim()
    lines.push(`## ${title}`, "")
    if (s.content && s.content.trim()) {
      lines.push(s.content.trim(), "")
    }
  }
  return lines.join("\n")
}

export function PreferencesPanel() {
  const [loading, setLoading] = useState(true)
  const [sections, setSections] = useState<PreferenceSection[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createId, setCreateId] = useState("")
  const [createName, setCreateName] = useState("")
  const [createDesc, setCreateDesc] = useState("")
  const [creating, setCreating] = useState(false)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    listPreferenceSections()
      .then((res) => {
        if (cancelled) return
        const sorted = sortByOrder(res.sections || [])
        setSections(sorted)
        if (sorted.length && !selectedId) setSelectedId(sorted[0].id)
      })
      .catch((e) =>
        toast.error("加载偏好分节失败", { description: e instanceof Error ? e.message : "" }),
      )
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedSection = useMemo(
    () => sections.find((s) => s.id === selectedId) ?? null,
    [sections, selectedId],
  )

  function resetCreateForm() {
    setCreateId("")
    setCreateName("")
    setCreateDesc("")
  }

  async function handleCreate() {
    const id = createId.trim()
    if (!id) {
      toast.error("分节 ID 必填")
      return
    }
    const nextOrder = sections.reduce((mx, s) => Math.max(mx, s.order ?? 0), -1) + 1
    setCreating(true)
    try {
      const res = await createPreferenceSection({
        id,
        name: createName.trim() || id,
        description: createDesc.trim(),
        order: nextOrder,
        visible: true,
      })
      const row = { ...res.section, id: res.section.id || id }
      setSections((prev) => sortByOrder([...prev, row]))
      setSelectedId(row.id)
      setCreateOpen(false)
      resetCreateForm()
      toast.success("已新建偏好分节")
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setCreating(false)
    }
  }

  function handleUpdated(row: PreferenceSection) {
    setSections((prev) => sortByOrder(prev.map((s) => (s.id === row.id ? { ...s, ...row } : s))))
  }

  function handleDeleted(id: string) {
    setSections((prev) => prev.filter((s) => s.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  // 后端 pref_router 不会自动聚合写入 USER.md，故在此客户端聚合可见分节 →
  // savePreferencesLibrary 写 config/USER.md 并 sync 全部 Agent workspace。
  async function handleSync() {
    if (!sections.length) {
      toast.error("暂无分节可同步")
      return
    }
    setSyncing(true)
    try {
      const markdown = aggregateSectionsToMarkdown(sections)
      const res = await savePreferencesLibrary(markdown)
      toast.success("已聚合并同步到全部 Agent", {
        description: res.synced_agents?.length
          ? `已刷新 ${res.synced_agents.length} 个 Agent workspace`
          : "无 Agent 需要刷新",
      })
    } catch (e) {
      toast.error("同步失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            tabs={<ManageSegmentNav />}
            action={
              <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}>
                新建
              </Button>
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {loading ? (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
            ) : sections.length ? (
              sections.map((s) => (
                <ListItemRow
                  key={s.id}
                  name={s.name || s.id}
                  sub={s.description || `#${s.id}`}
                  avatar={s.name || s.id}
                  tag={s.visible === false ? "隐藏" : undefined}
                  active={s.id === selectedId}
                  onClick={() => setSelectedId(s.id)}
                  onDelete={() => {
                    if (!window.confirm(`删除偏好分节「${s.name || s.id}」？\n\n此操作不可恢复。`)) return
                    deletePreferenceSection(s.id)
                      .then(() => {
                        handleDeleted(s.id)
                        toast.success("已删除")
                      })
                      .catch((err) =>
                        toast.error("删除失败", { description: err instanceof Error ? err.message : "" }),
                      )
                  }}
                />
              ))
            ) : (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">
                暂无偏好分节，点右上角「新建」开始。
              </p>
            )}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader
            title="偏好库"
            description="人类操作规则与交付标准；按分节维护，点「同步」聚合写入 USER.md 并注入全员 Agent。"
            action={
              <Button size="sm" variant="outline" disabled={syncing || !sections.length} onClick={() => void handleSync()}>
                {syncing ? "同步中…" : "同步到全部 Agent"}
              </Button>
            }
          />
          {selectedSection ? (
            <PreferencesLibraryPanel
              section={selectedSection}
              onUpdated={handleUpdated}
              onDeleted={() => handleDeleted(selectedSection.id)}
            />
          ) : (
            <WelcomePane title="选择偏好分节" description="左侧已列出全部分节，点选一项编辑内容、排序与可见性。" />
          )}
        </div>
      </DiscordShell>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新建偏好分节</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>ID *</Label>
              <Input
                value={createId}
                onChange={(e) => setCreateId(e.target.value)}
                placeholder="例如: style / avoid / delivery"
              />
              <p className="text-xs text-[var(--color-muted-foreground)]">唯一标识，仅字母/数字/下划线/连字符。</p>
            </div>
            <div className="grid gap-2">
              <Label>名称</Label>
              <Input value={createName} onChange={(e) => setCreateName(e.target.value)} placeholder="留空则用 ID" />
            </div>
            <div className="grid gap-2">
              <Label>描述</Label>
              <Input value={createDesc} onChange={(e) => setCreateDesc(e.target.value)} placeholder="一句话说明用途" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button disabled={creating} onClick={() => void handleCreate()}>
              {creating ? "创建中…" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
