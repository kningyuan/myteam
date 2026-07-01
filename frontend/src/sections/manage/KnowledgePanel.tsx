import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { createMemory, deleteMemory, listMemory, type MemoryEntry } from "@/lib/api/projects"
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
import { KnowledgeDetailPanel } from "./KnowledgeDetailPanel"

export function KnowledgePanel() {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [kbLoading, setKbLoading] = useState(false)
  const [kbKind, setKbKind] = useState<"kb" | "global" | "project" | "l1" | "all">("kb")
  const [kbCreateOpen, setKbCreateOpen] = useState(false)
  const [kbCreateTitle, setKbCreateTitle] = useState("")
  const [kbCreateProject, setKbCreateProject] = useState("")
  const [kbCreateContent, setKbCreateContent] = useState("")
  const [kbCreateTags, setKbCreateTags] = useState("")
  const [kbCreateKind, setKbCreateKind] = useState<"global" | "project" | "l1">("global")
  const [kbCreateBusy, setKbCreateBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setKbLoading(true)
    const timer = window.setTimeout(() => {
      listMemory({ limit: 200, text: search.trim() || undefined, kind: kbKind })
        .then((rows) => {
          if (!cancelled) setEntries(rows)
        })
        .catch(() => {
          if (!cancelled) setEntries([])
        })
        .finally(() => {
          if (!cancelled) setKbLoading(false)
        })
    }, search.trim() ? 250 : 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [search, kbKind])

  const filteredEntries = useMemo(
    () =>
      sortByModifiedDesc(
        entries.filter((e) =>
          matchQuery(search, e.title, e.project_id, e.task_id, e.preview, ...(e.tags || [])),
        ),
      ),
    [entries, search],
  )

  const selectedEntry = entries.find((e) => String(e.id) === itemId) ?? null

  async function handleCreateKnowledge() {
    const title = kbCreateTitle.trim()
    const project_id = kbCreateKind === "global" ? "__global__" : kbCreateProject.trim()
    if (!title) {
      toast.error("标题必填")
      return
    }
    if (kbCreateKind !== "global" && !project_id) {
      toast.error("按项目类型需要填写项目 ID")
      return
    }
    const tags = kbCreateTags
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    setKbCreateBusy(true)
    try {
      const row = await createMemory({ project_id, title, content: kbCreateContent, tags })
      setEntries((prev) => [row, ...prev])
      setKbCreateOpen(false)
      setKbCreateTitle("")
      setKbCreateProject("")
      setKbCreateContent("")
      setKbCreateTags("")
      setKbCreateKind("global")
      if (row.id) navigate(`/manage/knowledge/${row.id}`)
      toast.success("已创建知识条目")
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setKbCreateBusy(false)
    }
  }

  async function handleDeleteKnowledge(entry: MemoryEntry) {
    if (!entry.id) return
    setEntries((prev) => prev.filter((e) => e.id !== entry.id))
    navigate("/manage/knowledge")
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder="搜索标题 / 项目 / 标签…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            action={
              <Button size="sm" onClick={() => setKbCreateOpen(true)}>
                新建条目
              </Button>
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {kbLoading ? (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
            ) : filteredEntries.length ? (
              filteredEntries.map((e) => (
                <ListItemRow
                  key={e.id}
                  name={e.title || `条目 #${e.id}`}
                  sub={e.project_id || e.preview?.slice(0, 40)}
                  tag={e.project_id === "__global__" ? "global" : e.project_id ? "project" : "kb"}
                  avatar={e.title || "KB"}
                  active={String(e.id) === itemId}
                  onClick={() => navigate(`/manage/knowledge/${e.id}`)}
                  onDelete={() => {
                    if (!window.confirm(`删除知识条目「${e.title || e.id}」？\n\n此操作不可恢复。`)) return
                    deleteMemory(e.id ?? 0)
                      .then(() => {
                        setEntries((prev) => prev.filter((x) => x.id !== e.id))
                        toast.success("已删除")
                      })
                      .catch((err) =>
                        toast.error("删除失败", { description: err instanceof Error ? err.message : "" }),
                      )
                  }}
                />
              ))
            ) : (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">无匹配条目</p>
            )}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader
            title="知识库"
            description="任务沉淀与可检索经验。团队通用条目用 project_id=__global__；项目专属用具体 project_id。"
          />
          <div className="mb-4 flex flex-wrap items-center gap-2 px-4">
            {(
              [
                ["kb", "全部 KB"],
                ["global", "团队通用"],
                ["project", "按项目"],
                ["l1", "L1 工作记忆"],
                ["all", "全部"],
              ] as const
            ).map(([k, label]) => (
              <Button key={k} size="sm" variant={kbKind === k ? "default" : "outline"} onClick={() => setKbKind(k)}>
                {label}
              </Button>
            ))}
          </div>
          {selectedEntry ? (
            <KnowledgeDetailPanel
              entry={selectedEntry}
              onDelete={() => void handleDeleteKnowledge(selectedEntry)}
              onUpdated={(row) => setEntries((prev) => prev.map((e) => (e.id === row.id ? { ...e, ...row } : e)))}
            />
          ) : (
            <WelcomePane title="选择知识条目" description="左侧已列出全部条目，点选一项查看详情。" />
          )}
        </div>
      </DiscordShell>

      <Dialog open={kbCreateOpen} onOpenChange={setKbCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新建知识条目</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>类型</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={kbCreateKind}
                onChange={(e) => setKbCreateKind(e.target.value as "global" | "project" | "l1")}
              >
                <option value="global">团队通用</option>
                <option value="project">按项目</option>
                <option value="l1">L1 工作记忆</option>
              </select>
            </div>
            {kbCreateKind !== "global" && (
              <div className="grid gap-2">
                <Label>项目 ID *</Label>
                <Input value={kbCreateProject} onChange={(e) => setKbCreateProject(e.target.value)} placeholder="例如: sa-human" />
              </div>
            )}
            <div className="grid gap-2">
              <Label>标题 *</Label>
              <Input value={kbCreateTitle} onChange={(e) => setKbCreateTitle(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>标签（逗号分隔）</Label>
              <Input value={kbCreateTags} onChange={(e) => setKbCreateTags(e.target.value)} placeholder="例如: 方法论, 竞品, v2" />
            </div>
            <div className="grid gap-2">
              <Label>正文</Label>
              <Textarea rows={8} value={kbCreateContent} onChange={(e) => setKbCreateContent(e.target.value)} className="font-mono text-xs" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setKbCreateOpen(false)}>
              取消
            </Button>
            <Button disabled={kbCreateBusy} onClick={() => void handleCreateKnowledge()}>
              {kbCreateBusy ? "创建中…" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
