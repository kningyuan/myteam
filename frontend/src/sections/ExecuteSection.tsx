import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  deleteSingleExecuteTask,
  finishSingleExecute,
  getSingleExecuteTask,
  listSingleExecuteProjects,
  prepareSingleExecute,
  updateSingleExecute,
  type SingleExecuteProject,
  type SingleExecuteTaskDetail,
} from "@/lib/api/execute"
import { listAgents, type AgentSummary } from "@/lib/api/agents"
import { listTaskTypes, type TaskTypeSummary } from "@/lib/api/workflows"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { RunSegmentNav } from "@/components/RunSegmentNav"
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
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"

function TaskDetailView({
  detail,
  agents,
  taskTypes,
  onRefresh,
  onDeleted,
}: {
  detail: SingleExecuteTaskDetail
  agents: AgentSummary[]
  taskTypes: TaskTypeSummary[]
  onRefresh: () => void
  onDeleted: () => void
}) {
  const navigate = useNavigate()
  const [tab, setTab] = useState<"prompt" | "harness" | "deliverable" | "ledger">("harness")
  const [finishing, setFinishing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editIntent, setEditIntent] = useState(detail.intent || "")
  const [editAgent, setEditAgent] = useState(detail.agent_id || "product")
  const [editType, setEditType] = useState(detail.task_type || "research")
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    setEditIntent(detail.intent || "")
    setEditAgent(detail.agent_id || "product")
    setEditType(detail.task_type || "research")
  }, [detail.project_id, detail.task_id, detail.intent, detail.agent_id, detail.task_type])

  async function handleFinish() {
    setFinishing(true)
    try {
      const res = await finishSingleExecute({
        project_id: detail.project_id,
        task_id: detail.task_id,
        agent_id: detail.agent_id,
        task_type: detail.task_type,
      })
      toast.success("POST 完成", { description: res.kb_ref ? `KB ref: ${res.kb_ref}` : undefined })
      onRefresh()
    } catch (e) {
      toast.error("finish 失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setFinishing(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateSingleExecute(detail.project_id, detail.task_id, {
        intent: editIntent,
        agent_id: editAgent,
        task_type: editType,
      })
      toast.success("已保存")
      setEditing(false)
      onRefresh()
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`确定删除独立任务「${detail.task_id}」？该操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deleteSingleExecuteTask(detail.project_id, detail.task_id)
      toast.success("任务已删除")
      onDeleted()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setDeleting(false)
    }
  }

  const body =
    tab === "prompt"
      ? detail.prompt || ""
      : tab === "harness"
        ? detail.harness_blocks || ""
        : tab === "deliverable"
          ? detail.deliverable_content || ""
          : detail.ledger_content || ""

  const readOnly = detail.finished

  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">
            {detail.project_id} / {detail.task_id}
          </h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{detail.intent || "—"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {detail.finished ? (
            <Badge variant="secondary">已 finish</Badge>
          ) : (
            <Button size="sm" disabled={finishing} onClick={() => void handleFinish()}>
              {finishing ? "POST 中…" : "finish（POST promote）"}
            </Button>
          )}
          {editing ? (
            <>
              <Button size="sm" disabled={saving} onClick={() => void handleSave()}>
                {saving ? "保存中…" : "保存"}
              </Button>
              <Button size="sm" variant="ghost" disabled={saving} onClick={() => setEditing(false)}>
                取消
              </Button>
            </>
          ) : (
            !readOnly && (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                编辑
              </Button>
            )
          )}
          <Button
            size="sm"
            variant="outline"
            className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
            disabled={deleting}
            onClick={() => void handleDelete()}
          >
            {deleting ? "删除中…" : "删除任务"}
          </Button>
        </div>
      </div>
      <Separator className="my-4" />
      {editing ? (
        <div className="mb-4 grid gap-3 rounded-md border border-[var(--color-border)] p-3">
          <div className="grid gap-2">
            <Label>意图</Label>
            <Textarea rows={3} value={editIntent} onChange={(e) => setEditIntent(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>Agent</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={editAgent}
                onChange={(e) => setEditAgent(e.target.value)}
              >
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name || a.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>task_type</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={editType}
                onChange={(e) => setEditType(e.target.value)}
              >
                {taskTypes.map((t) => (
                  <option key={t.task_type} value={t.task_type}>
                    {t.display_name || t.task_type}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            保存后会重新生成 worker.prompt.txt 与 harness.blocks.txt。
          </p>
        </div>
      ) : null}
      <dl className="detail-dl">
        <div>
          <dt>Agent</dt>
          <dd>{detail.agent_id || "—"}</dd>
        </div>
        <div>
          <dt>task_type</dt>
          <dd>{detail.task_type || "—"}</dd>
        </div>
        <div>
          <dt>prepared</dt>
          <dd>{detail.prepared_at || "—"}</dd>
        </div>
        {detail.finish_summary?.kb_ref && (
          <div>
            <dt>KB ref</dt>
            <dd className="font-mono text-xs">{detail.finish_summary.kb_ref}</dd>
          </div>
        )}
      </dl>
      <div className="mb-3 flex flex-wrap gap-2">
        {(["harness", "prompt", "deliverable", "ledger"] as const).map((t) => (
          <Button key={t} size="sm" variant={tab === t ? "default" : "outline"} onClick={() => setTab(t)}>
            {t === "harness" ? "Harness 块" : t === "prompt" ? "完整 Prompt" : t === "deliverable" ? "交付物" : "Ledger"}
          </Button>
        ))}
      </div>
      <ScrollArea className="h-[min(60vh,520px)] rounded-md border border-[var(--color-border)] p-3">
        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">{body || "（空）"}</pre>
      </ScrollArea>
      <p className="mt-3 text-xs text-[var(--color-muted-foreground)]">
        流程：prepare → Agent 填写交付物与 ledger（文件系统）→ finish。Harness 块即 execute 实际注入内容预览。
      </p>
    </div>
  )
}

function ExecuteInfoCard() {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] p-3 text-sm">
      <h3 className="text-sm font-semibold">独立任务（单 Agent 调试）</h3>
      <ul className="mt-1.5 space-y-0.5 text-xs text-[var(--color-muted-foreground)]">
        <li>不走编排内核，手动 prepare → 执行 → finish</li>
        <li>调试单 Agent 的 harness 注入与交付质量</li>
      </ul>
      <details className="mt-1.5 text-xs text-[var(--color-muted-foreground)]">
        <summary className="cursor-pointer">与 Workflow Loop 的区别</summary>
        <p className="mt-1">
          Workflow Loop：自动 DAG 调度 + Gate 验收 + 重试；独立任务：手动单步，可视化 prompt 与 harness 注入。
        </p>
      </details>
    </div>
  )
}

export function ExecuteSection() {
  const { projectId, taskId } = useParams()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<SingleExecuteProject[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<SingleExecuteTaskDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [taskTypes, setTaskTypes] = useState<TaskTypeSummary[]>([])
  const [formProject, setFormProject] = useState("")
  const [formTask, setFormTask] = useState("")
  const [formAgent, setFormAgent] = useState("product")
  const [formType, setFormType] = useState("research")
  const [formIntent, setFormIntent] = useState("")
  const [formBusy, setFormBusy] = useState(false)

  const loadProjects = useCallback(() => {
    setLoading(true)
    listSingleExecuteProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadProjects()
    listAgents().then(setAgents).catch(() => {})
    listTaskTypes().then(setTaskTypes).catch(() => {})
  }, [loadProjects])

  useEffect(() => {
    if (!projectId || !taskId) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    getSingleExecuteTask(projectId, taskId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false))
  }, [projectId, taskId])

  const flatTasks = useMemo(() => {
    const rows: { project_id: string; task_id: string; label: string; finished?: boolean }[] = []
    for (const p of projects) {
      for (const t of p.tasks || []) {
        rows.push({
          project_id: p.project_id,
          task_id: t.task_id,
          label: `${p.project_id} · ${t.task_id}`,
          finished: t.finished,
        })
      }
    }
    return rows
  }, [projects])

  async function handlePrepare() {
    const project_id = formProject.trim()
    const task_id = formTask.trim()
    if (!project_id || !task_id) {
      toast.error("project_id 与 task_id 必填")
      return
    }
    setFormBusy(true)
    try {
      const res = await prepareSingleExecute({
        project_id,
        task_id,
        agent_id: formAgent,
        task_type: formType,
        intent: formIntent.trim() || "单 agent execute 质量验证任务",
      })
      toast.success("已 prepare", {
        description: `Harness 块 ${res.harness_block_count ?? 0} 个`,
      })
      setCreateOpen(false)
      loadProjects()
      navigate(`/run/single/${project_id}/${task_id}`)
    } catch (e) {
      toast.error("prepare 失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setFormBusy(false)
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="独立任务"
            widthStorageKey="agentHub.executeListWidth"
            tabs={<RunSegmentNav />}
            action={
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                新建任务
              </Button>
            }
          >
            <div className="px-3 pb-2">
              <ExecuteInfoCard />
            </div>
            {loading ? (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
            ) : flatTasks.length ? (
              flatTasks.map((row) => (
                <ListItemRow
                  key={`${row.project_id}:${row.task_id}`}
                  name={row.task_id}
                  sub={row.project_id}
                  avatar={row.finished ? "✓" : "EX"}
                  tag={row.finished ? "done" : undefined}
                  active={projectId === row.project_id && taskId === row.task_id}
                  onClick={() => navigate(`/run/single/${row.project_id}/${row.task_id}`)}
                />
              ))
            ) : (
              <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">暂无任务，点「新建」</p>
            )}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll p-4">
          {projectId && taskId ? (
            detailLoading ? (
              <p className="text-sm text-[var(--color-muted-foreground)]">加载任务…</p>
            ) : detail ? (
              <TaskDetailView
                detail={detail}
                agents={agents}
                taskTypes={taskTypes}
                onRefresh={() => void getSingleExecuteTask(projectId, taskId).then(setDetail)}
                onDeleted={() => navigate("/run/single")}
              />
            ) : (
              <WelcomePane title="任务不存在" description="请从左侧选择或新建 prepare。" />
            )
          ) : (
            <>
              <div className="mb-3">
                <ExecuteInfoCard />
              </div>
              <WelcomePane
                title="独立任务（Layer B）"
                description="无 Workflow：prepare 看 harness 注入 → Agent 写交付物/ledger → finish 沉淀 KB/references。"
              />
            </>
          )}
        </div>
      </DiscordShell>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>prepare 独立任务</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>project_id *</Label>
                <Input value={formProject} onChange={(e) => setFormProject(e.target.value)} placeholder="sa-human" />
              </div>
              <div className="grid gap-2">
                <Label>task_id *</Label>
                <Input value={formTask} onChange={(e) => setFormTask(e.target.value)} placeholder="t-eval-03" />
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Agent</Label>
                <select
                  className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                  value={formAgent}
                  onChange={(e) => setFormAgent(e.target.value)}
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name || a.id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label>task_type</Label>
                <select
                  className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                >
                  {taskTypes.map((t) => (
                    <option key={t.task_type} value={t.task_type}>
                      {t.display_name || t.task_type}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>意图</Label>
              <Textarea rows={3} value={formIntent} onChange={(e) => setFormIntent(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button disabled={formBusy} onClick={() => void handlePrepare()}>
              {formBusy ? "prepare 中…" : "prepare"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
