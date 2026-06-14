import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { getConfig, getSkillConfig } from "@/lib/api/config"
import { deleteProject, listProjects, runProject } from "@/lib/api/projects"
import { listWorkflows, type WorkflowSummary } from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { matchQuery } from "@/components/manage/ManageSearchBar"
import { ProjectDetailPanel } from "@/components/project/ProjectDetailPanel"
import { ProjectListItem } from "@/components/project/ProjectListItem"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function NewProjectDialog({
  open,
  onOpenChange,
  workflows,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workflows: WorkflowSummary[]
  onCreated: (id: string) => void
}) {
  const [title, setTitle] = useState("")
  const [goal, setGoal] = useState("")
  const [workflow, setWorkflow] = useState("")
  const [mode, setMode] = useState("one_shot")
  const [budget, setBudget] = useState("")
  const [review, setReview] = useState(false)
  const [split, setSplit] = useState(false)
  const [maxCycles, setMaxCycles] = useState("3")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    getSkillConfig()
      .then((skill) => {
        const pd = (skill.process_defaults || {}) as Record<string, unknown>
        setMaxCycles(String(pd.max_cycles ?? 3))
      })
      .catch(() => {})
  }, [open])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!goal.trim()) return
    setBusy(true)
    try {
      const budgetNum = parseInt(budget, 10)
      const cyclesNum = parseInt(maxCycles, 10)
      const res = await runProject({
        goal: goal.trim(),
        title: title.trim() || undefined,
        workflow: workflow || undefined,
        mode: mode || undefined,
        budget: !Number.isNaN(budgetNum) && budgetNum > 0 ? budgetNum : undefined,
        review: review || undefined,
        split: split || undefined,
        max_cycles:
          mode === "recurring" && !Number.isNaN(cyclesNum) && cyclesNum > 0 ? cyclesNum : undefined,
      })
      toast.success("项目已启动", { description: res.project_id })
      setTitle("")
      setGoal("")
      setWorkflow("")
      setBudget("")
      setReview(false)
      setSplit(false)
      onOpenChange(false)
      onCreated(res.project_id)
    } catch (ex) {
      toast.error("创建失败", {
        description: ex instanceof Error ? ex.message : "请稍后重试",
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>发起新项目</DialogTitle>
            <DialogDescription>填写目标与运行选项，Hub 将编排任务并跟踪交付。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="project-title">项目名称（可选）</Label>
              <Input
                id="project-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例如：Q2 产品文档"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-goal">项目目标 *</Label>
              <Textarea
                id="project-goal"
                required
                rows={4}
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="描述你希望团队完成什么…"
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>工作流</Label>
                <Select value={workflow || "__auto__"} onValueChange={(v) => setWorkflow(v === "__auto__" ? "" : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="自动 / 无" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__auto__">自动 / 无</SelectItem>
                    {workflows.map((w) => (
                      <SelectItem key={w.id} value={w.id}>
                        {w.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>模式</Label>
                <Select value={mode} onValueChange={setMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="one_shot">one_shot（跑一次）</SelectItem>
                    <SelectItem value="recurring">recurring（持续）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-budget">Token 预算（可选）</Label>
              <Input
                id="project-budget"
                type="number"
                min={1}
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="例如：1000000"
              />
            </div>
            {mode === "recurring" && (
              <div className="grid gap-2">
                <Label htmlFor="project-max-cycles">最大周期数</Label>
                <Input
                  id="project-max-cycles"
                  type="number"
                  min={1}
                  value={maxCycles}
                  onChange={(e) => setMaxCycles(e.target.value)}
                  placeholder="默认 3"
                />
              </div>
            )}
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={review} onChange={(e) => setReview(e.target.checked)} />
                开启同行评审
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} />
                自动拆分子任务
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "启动中…" : "启动项目"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ProjectsSection() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { data: projects } = useResourceQuery("projects", listProjects, [])
  const { data: workflows } = useResourceQuery("workflows", listWorkflows, [])
  const [showNew, setShowNew] = useState(false)
  const [pricePerMtok, setPricePerMtok] = useState<number | undefined>()
  const [search, setSearch] = useState("")

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        const sys = (cfg.system || {}) as Record<string, unknown>
        const p = Number(sys.price_per_mtok)
        if (p > 0) setPricePerMtok(p)
      })
      .catch(() => {})
  }, [])

  const filtered = useMemo(
    () =>
      projects.filter((p) =>
        matchQuery(search, p.id, p.name, p.status, p.mode, p.meta?.workflow),
      ),
    [projects, search],
  )

  async function handleDeleteProject(id: string) {
    if (
      !window.confirm(
        `确认彻底删除项目「${id}」？将清除其数据库记录、交付物目录与 agent 临时文件，不可恢复。`,
      )
    ) {
      return
    }
    try {
      await deleteProject(id)
      toast.success(`已删除项目「${id}」`)
      if (projectId === id) navigate("/projects")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="项目"
            widthStorageKey="agentHub.projectsListWidth"
            action={
              <Button size="sm" onClick={() => setShowNew(true)}>
                新建
              </Button>
            }
            search={
              <input
                placeholder="搜索项目…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
          >
            {filtered.map((p) => (
              <ProjectListItem
                key={p.id}
                name={p.name || p.id}
                status={p.status}
                progress={p.progress}
                taskCount={p.task_count}
                active={p.id === projectId}
                onClick={() => navigate(`/projects/${encodeURIComponent(p.id)}`)}
                onDelete={() => handleDeleteProject(p.id)}
              />
            ))}
          </ListColumn>
        }
      >
        {projectId ? (
          <ProjectDetailPanel projectId={projectId} pricePerMtok={pricePerMtok} />
        ) : (
          <WelcomePane
            title="选择一个项目"
            description="左侧选择项目查看详情、DAG、执行过程与交付物；也可点击「新建」直接发起。"
          />
        )}
      </DiscordShell>
      <NewProjectDialog
        open={showNew}
        onOpenChange={setShowNew}
        workflows={workflows}
        onCreated={(id) => {
          navigate(`/projects/${encodeURIComponent(id)}`)
        }}
      />
    </>
  )
}
