import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  deletePromptTemplate,
  getPromptTemplate,
  listPromptTemplates,
  updatePromptTemplate,
  type PromptTemplateEntry,
  type PromptTemplateList,
} from "@/lib/api/prompts"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { WorkspaceHeader } from "./WorkspaceHeader"

export function PromptTemplatesPanel() {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [promptList, setPromptList] = useState<PromptTemplateList | null>(null)
  const [promptLoading, setPromptLoading] = useState(false)
  const [promptDetail, setPromptDetail] = useState<PromptTemplateEntry | null>(null)
  const [promptDetailLoading, setPromptDetailLoading] = useState(false)
  const [promptEditContent, setPromptEditContent] = useState("")
  const [promptEditing, setPromptEditing] = useState(false)
  const [promptSaving, setPromptSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    setPromptLoading(true)
    listPromptTemplates()
      .then((data) => {
        if (!cancelled) setPromptList(data)
      })
      .catch(() => {
        if (!cancelled) setPromptList(null)
      })
      .finally(() => {
        if (!cancelled) setPromptLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!itemId) {
      setPromptDetail(null)
      setPromptEditing(false)
      return
    }
    let cancelled = false
    setPromptDetailLoading(true)
    getPromptTemplate(itemId)
      .then((entry) => {
        if (!cancelled) {
          setPromptDetail(entry)
          setPromptEditContent(
            typeof entry.content === "string" ? entry.content : JSON.stringify(entry.content, null, 2),
          )
        }
      })
      .catch(() => {
        if (!cancelled) setPromptDetail(null)
      })
      .finally(() => {
        if (!cancelled) setPromptDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [itemId])

  const promptEntries = useMemo(() => {
    if (!promptList) return []
    const merged: { id: string; entry: PromptTemplateEntry }[] = []
    for (const [id, entry] of Object.entries(promptList.kinds || {})) {
      merged.push({ id, entry })
    }
    for (const [id, entry] of Object.entries(promptList.task_types || {})) {
      merged.push({ id, entry })
    }
    return merged
  }, [promptList])

  const filteredPromptEntries = useMemo(() => {
    if (!search.trim()) return promptEntries
    const q = search.trim().toLowerCase()
    return promptEntries.filter((e) => e.id.toLowerCase().includes(q))
  }, [promptEntries, search])

  async function handleSavePromptTemplate() {
    if (!itemId) return
    setPromptSaving(true)
    try {
      await updatePromptTemplate(itemId, { content: promptEditContent })
      toast.success("Prompt 模板已保存")
      setPromptEditing(false)
      // reload detail
      const entry = await getPromptTemplate(itemId)
      setPromptDetail(entry)
      setPromptEditContent(
        typeof entry.content === "string" ? entry.content : JSON.stringify(entry.content, null, 2),
      )
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败")
    } finally {
      setPromptSaving(false)
    }
  }

  async function handleDeletePromptTemplate(id: string) {
    if (!confirm(`确定要删除 Prompt 模板「${id}」吗？`)) return
    try {
      await deletePromptTemplate(id)
      toast.success("Prompt 模板已删除")
      setPromptList(null)
      navigate("/manage/prompt-templates", { replace: true })
      listPromptTemplates().then(setPromptList).catch(() => {})
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败")
    }
  }

  return (
    <DiscordShell
      list={
        <ListColumn
          title="管理"
          tabs={<ManageSegmentNav />}
          search={
            <input
              placeholder="搜索 Prompt 模板…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          }
          widthStorageKey="agentHub.manageListWidth"
        >
          {promptLoading ? (
            <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
          ) : filteredPromptEntries.length ? (
            filteredPromptEntries.map(({ id, entry }) => (
              <ListItemRow
                key={id}
                name={id}
                sub={entry.kind === "kind" ? "交互类型" : "任务类型"}
                tag={entry.kind === "kind" ? "kind" : "task_type"}
                avatar={id}
                active={id === itemId}
                onClick={() => navigate(`/manage/prompt-templates/${encodeURIComponent(id)}`)}
                onDelete={() => handleDeletePromptTemplate(id)}
              />
            ))
          ) : (
            <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">暂无 Prompt 模板</p>
          )}
        </ListColumn>
      }
    >
      <div className="discord-main-scroll workspace-scroll">
        <WorkspaceHeader
          title="Prompt 模板"
          description="框架与 Agent 交互的 Prompt 模板（kinds + task_types），结构在代码中，内容在此编辑。"
        />
        {promptDetailLoading ? (
          <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
        ) : promptDetail ? (
          <div className="workspace-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">{itemId}</h2>
                <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                  类型：{promptDetail.kind === "kind" ? "交互类型" : "任务类型"} · 路径：{promptDetail.path}
                </p>
              </div>
              <div className="flex gap-2">
                {promptEditing ? (
                  <>
                    <Button size="sm" disabled={promptSaving} onClick={() => void handleSavePromptTemplate()}>
                      {promptSaving ? "保存中…" : "保存"}
                    </Button>
                    <Button size="sm" variant="ghost" disabled={promptSaving} onClick={() => setPromptEditing(false)}>
                      取消
                    </Button>
                  </>
                ) : (
                  <>
                    <Button size="sm" variant="outline" onClick={() => setPromptEditing(true)}>
                      编辑
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleDeletePromptTemplate(itemId!)}>
                      删除
                    </Button>
                  </>
                )}
              </div>
            </div>
            <Separator className="my-5" />
            {promptEditing ? (
              <Textarea
                value={promptEditContent}
                onChange={(e) => setPromptEditContent(e.target.value)}
                className="min-h-[400px] font-mono text-xs"
              />
            ) : (
              <pre className="max-h-[60vh] overflow-auto rounded-md bg-[var(--color-muted)] p-4 text-xs leading-relaxed">
                {typeof promptDetail.content === "string"
                  ? promptDetail.content
                  : JSON.stringify(promptDetail.content, null, 2)}
              </pre>
            )}
          </div>
        ) : (
          <WelcomePane title="选择 Prompt 模板" description="左侧已列出全部模板，点选一项查看或编辑。" />
        )}
      </div>
    </DiscordShell>
  )
}
