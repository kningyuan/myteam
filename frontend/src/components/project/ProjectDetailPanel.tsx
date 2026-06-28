import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  BarChart3,
  FileText,
  GitBranch,
  LayoutGrid,
  Play,
  ScrollText,
  Trash2,
  Users,
  X,
} from "lucide-react"
import { toast } from "sonner"
import {
  cancelProject,
  deleteProject,
  getProjectCost,
  getProjectEvents,
  getProjectFleet,
  getProjectOverview,
  getProjectRunStatus,
  projectWorkflowLabel,
  resumeProject,
  subscribeProjectStream,
  type ProjectCost,
  type ProjectEvent,
  type ProjectOverview,
} from "@/lib/api/projects"
import { listGroups } from "@/lib/api/groups"
import { useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { ProjectTaskQualityCard } from "@/components/project/ProjectTaskQualityCard"
import { IterationProgressCard } from "@/components/project/IterationProgressCard"
import { ProjectDag } from "@/components/project/ProjectDag"
import { ProjectDeliverablePanel } from "@/components/project/ProjectDeliverablePanel"
import { ProjectExecTree } from "@/components/project/ProjectExecTree"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatNumber, statusLabel, StatusBadge } from "@/components/ui/page"

function fmtTime(iso?: string) {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN")
  } catch {
    return iso ?? "—"
  }
}

function LaunchConfig({ ov, cyclesDone }: { ov: ProjectOverview; cyclesDone?: number }) {
  const lc = ov.launch || {}
  const items = [
    ["工作流", projectWorkflowLabel(ov)],
    ["模式", lc.mode_label || lc.mode || ov.mode || "—"],
    ...(ov.mode === "recurring" || lc.mode === "recurring"
      ? [
          [
            "周期进度",
            lc.max_cycles
              ? `${cyclesDone ?? 0} / ${lc.max_cycles} 周期完成`
              : cyclesDone
                ? `${cyclesDone} 周期完成`
                : "—",
          ] as const,
        ]
      : []),
    [
      "Token 预算",
      lc.token_budget ?? ov.budget
        ? `${Number(lc.token_budget ?? ov.budget).toLocaleString()} tok`
        : "不限",
    ],
    ["交付模板", lc.template_id || "未指定"],
    ["CLI 后端", lc.backend || "系统默认"],
    ["创建时间", fmtTime(ov.created_at || ov.updated_at)],
  ]
  return (
    <div className="launch-config-grid">
      {items.map(([k, v]) => (
        <div key={k} className="launch-kv">
          <span className="launch-k">{k}</span>
          <span className="launch-v">{v}</span>
        </div>
      ))}
      <div className="launch-kv launch-kv-wide">
        <span className="launch-k">运行选项</span>
        <span className="launch-flags">
          <span className={lc.review ? "launch-flag on" : "launch-flag off"}>同行评审</span>
          <span className={lc.split ? "launch-flag on" : "launch-flag off"}>自动拆分</span>
        </span>
      </div>
      {(lc.goal || ov.goal) && (
        <div className="launch-goal-block">
          <div className="launch-k">项目目标</div>
          <pre className="launch-goal">{lc.goal || ov.goal}</pre>
        </div>
      )}
    </div>
  )
}

function CostView({
  cost,
  ov,
  pricePerMtok,
}: {
  cost: ProjectCost
  ov: ProjectOverview
  pricePerMtok?: number
}) {
  const total = cost.project ?? ov.tokens ?? 0
  const byAgent = cost.by_agent ?? {}
  const budget = ov.budget
  const ratio = ov.budget_ratio ?? (budget ? total / budget : 0)
  const pct = Math.min(100, Math.round(ratio * 100))
  const yuan = pricePerMtok ? ((total / 1_000_000) * pricePerMtok).toFixed(2) : null
  const maxTok = Math.max(...Object.values(byAgent), 1)
  const colors = ["#6f85ff", "#0891b2", "#059669", "#d97706", "#dc2626", "#7c3aed"]

  return (
    <div className="cost-view space-y-4">
      {budget != null && (
        <div className={`budget-wrap budget-${ov.budget_state || "ok"}`}>
          <div className="budget-track">
            <div className="budget-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="budget-label">
            {formatNumber(total)} / {formatNumber(budget)} tok · {pct}%
            {ov.budget_state === "over" ? " · 超限" : ov.budget_state === "alert" ? " · 接近上限" : ""}
          </div>
        </div>
      )}
      <div className="cost-row cost-total">
        <span>合计</span>
        <span>
          {formatNumber(total)} tok{yuan ? ` · ¥${yuan}` : ""}
        </span>
      </div>
      {Object.keys(byAgent).length > 0 && (
        <div className="cost-bar-chart">
          {Object.entries(byAgent).map(([a, n], i) => (
            <div key={a} className="cost-bar-item">
              <div className="cost-bar-label">{a}</div>
              <div className="cost-bar-track">
                <div
                  className="cost-bar-fill"
                  style={{ width: `${((n / maxTok) * 100).toFixed(0)}%`, background: colors[i % colors.length] }}
                />
              </div>
              <div className="cost-bar-val">{formatNumber(n)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ProjectDetailPanel({
  projectId,
  pricePerMtok,
}: {
  projectId: string
  pricePerMtok?: number
}) {
  const navigate = useNavigate()
  const [ov, setOv] = useState<ProjectOverview | null>(null)
  const [cost, setCost] = useState<ProjectCost>({})
  const [fleet, setFleet] = useState<Record<string, string>>({})
  const [events, setEvents] = useState<ProjectEvent[]>([])
  const [running, setRunning] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState("")
  const [tab, setTab] = useState("overview")
  const [error, setError] = useState("")
  const [groupId, setGroupId] = useState<string | null>(null)
  const mainRef = useRef<HTMLDivElement>(null)
  const reloadSeq = useRef(0)

  const reload = useCallback(async () => {
    const seq = ++reloadSeq.current
    const pid = projectId
    try {
      const [overview, costData, fleetData, runStatus, evData] = await Promise.all([
        getProjectOverview(pid),
        getProjectCost(pid).catch(() => ({})),
        getProjectFleet(pid).catch(() => ({ fleet: {} })),
        getProjectRunStatus(pid).catch(() => ({ running: false })),
        getProjectEvents(pid).catch(() => ({ events: [] })),
      ])
      if (seq !== reloadSeq.current) return
      setOv(overview)
      setCost(costData)
      setFleet(fleetData.fleet ?? {})
      setRunning(!!runStatus.running)
      setEvents(evData.events ?? [])
      setError("")
    } catch (e) {
      if (seq !== reloadSeq.current) return
      setOv(null)
      setError(e instanceof Error ? e.message : "加载失败")
    }
  }, [projectId])

  useOnResourceInvalidate("projects", reload)

  const syncGroupLink = useCallback(() => {
    listGroups()
      .then((gs) => setGroupId(gs.find((g) => g.project_id === projectId)?.id ?? null))
      .catch(() => setGroupId(null))
  }, [projectId])

  useOnResourceInvalidate("groups", syncGroupLink)

  useEffect(() => {
    syncGroupLink()
  }, [syncGroupLink])

  useEffect(() => {
    reloadSeq.current += 1
    setOv(null)
    setError("")
    setSelectedTaskId("")
    setCost({})
    setFleet({})
    setEvents([])
    setRunning(false)
    setTab("overview")
  }, [projectId])

  useEffect(() => {
    if (!ov?.tasks?.length) {
      setSelectedTaskId("")
      return
    }
    setSelectedTaskId((prev) => {
      if (prev && ov.tasks!.some((t) => t.id === prev)) return prev
      return ov.tasks![0].id
    })
  }, [ov])

  useEffect(() => {
    reload()
    const unsub = subscribeProjectStream(projectId, reload)
    const poll = setInterval(reload, 8000)
    return () => {
      unsub()
      clearInterval(poll)
    }
  }, [projectId, reload])

  function selectTask(id: string, goDeliverable = false, goExec = false) {
    setSelectedTaskId(id)
    if (goDeliverable) setTab("deliverable")
    else if (goExec) setTab("exec")
  }

  if (error && !ov) return <div className="p-6 text-red-300">{error}</div>
  if (!ov) return <div className="p-6 text-[var(--color-muted-foreground)]">加载项目…</div>

  const tasks = ov.tasks ?? []
  const status = ov.status || "unknown"
  const progress = Math.round((ov.progress ?? 0) * 100)
  const errMsg = (ov.launch_error || "").trim()
  const resumable = !running && (status === "in_progress" || status === "paused")
  const active = running || !["completed", "failed", "cancelled"].includes(status)
  const byTask = cost.by_task ?? {}
  const totalTok = cost.project ?? ov.tokens ?? 0
  const cyclesDone = events.filter((e) => e.kind === "cycle_done").length
  const workflowLabel = projectWorkflowLabel(ov)

  return (
    <div className="project-workspace" ref={mainRef}>
      <header className="project-workspace-header">
        <div className="project-workspace-title-row">
          <div className="min-w-0">
            <h1>{ov.title || projectId}</h1>
            <p className="project-workspace-meta">
              <span className="font-mono">{projectId}</span>
              {running && " · 内核运行中"}
              {errMsg && ` · 异常: ${errMsg}`}
            </p>
          </div>
          <div className="project-workspace-actions">
            {groupId && (
              <Button size="sm" variant="outline" onClick={() => navigate(`/groups/${encodeURIComponent(groupId)}`)}>
                <Users className="h-4 w-4" />
                协作群组
              </Button>
            )}
            {resumable && (
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  try {
                    await resumeProject(projectId)
                    toast.success("已提交续跑")
                    reload()
                  } catch (e) {
                    toast.error("续跑失败", { description: e instanceof Error ? e.message : "" })
                  }
                }}
              >
                <Play className="h-4 w-4" />
                续跑
              </Button>
            )}
            {active && (
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  if (!window.confirm("取消该项目？当前任务会跑完，之后不再派发新任务。")) return
                  try {
                    await cancelProject(projectId)
                    toast.success("已提交取消")
                    reload()
                  } catch (e) {
                    toast.error("取消失败", { description: e instanceof Error ? e.message : "" })
                  }
                }}
              >
                <X className="h-4 w-4" />
                取消
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              className="!border-red-500/40 !text-red-500 hover:!bg-red-500/10"
              onClick={async () => {
                if (!window.confirm(`确定删除项目「${ov.title || projectId}」？\n该操作会删除项目的所有数据，不可恢复。`)) return
                try {
                  await deleteProject(projectId)
                  toast.success("项目已删除")
                  navigate("/projects")
                } catch (e) {
                  toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
                }
              }}
            >
              <Trash2 className="h-4 w-4" />
              删除
            </Button>
          </div>
        </div>

        <div className="project-workspace-stats">
          <StatusBadge status={status} label={statusLabel(status)} />
          <Badge variant="outline">流程 {workflowLabel}</Badge>
          <span className="stat-pill">{tasks.length} 任务</span>
          <span className="stat-pill">{formatNumber(totalTok)} tok</span>
          {ov.budget && <span className="stat-pill">预算 {formatNumber(ov.budget)}</span>}
        </div>

        <div className="project-progress-card">
          <div className="progress-header">
            <span>整体进度</span>
            <span>{progress}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </header>

      <div className="project-workspace-body">
        <div className="project-workspace-main">
          <Tabs value={tab} onValueChange={setTab} className="project-tabs">
            <TabsList className="project-subnav w-full justify-start overflow-x-auto">
              <TabsTrigger value="overview" className="gap-1.5">
                <LayoutGrid className="h-3.5 w-3.5" />
                概览
              </TabsTrigger>
              <TabsTrigger value="dag" className="gap-1.5">
                <GitBranch className="h-3.5 w-3.5" />
                DAG
              </TabsTrigger>
              <TabsTrigger value="exec" className="gap-1.5">
                <ScrollText className="h-3.5 w-3.5" />
                执行过程
              </TabsTrigger>
              <TabsTrigger value="deliverable" className="gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                交付物
              </TabsTrigger>
              <TabsTrigger value="cost" className="gap-1.5">
                <BarChart3 className="h-3.5 w-3.5" />
                成本
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="project-tab-panel space-y-4">
              <section className="project-section">
                <h3>发起配置</h3>
                <LaunchConfig ov={ov} cyclesDone={cyclesDone} />
              </section>
              <section className="project-section">
                <h3>舰队状态</h3>
                <div className="fleet-list">
                  {Object.keys(fleet).length ? (
                    Object.entries(fleet).map(([a, s]) => (
                      <span key={a} className="fleet-chip">
                        {a} · {s}
                      </span>
                    ))
                  ) : (
                    <span className="hint">暂无</span>
                  )}
                </div>
              </section>
              <section className="project-section">
                <h3>迭代轮次</h3>
                <IterationProgressCard
                  iterations={ov.iterations}
                  highlightTaskId={selectedTaskId}
                />
                {!ov.iterations?.length && (
                  <p className="hint text-sm text-[var(--color-muted-foreground)]">暂无 loop 迭代</p>
                )}
              </section>
              <section className="project-section">
                <h3>成本摘要</h3>
                <p className="hint mb-3">
                  合计 {formatNumber(totalTok)} tok
                  {ov.budget ? ` · 预算 ${formatNumber(ov.budget)}` : ""} — 详见「成本」Tab
                </p>
              </section>
            </TabsContent>

            <TabsContent value="dag" className="project-tab-panel project-tab-panel--dag">
              <p className="dag-hint hint">滚轮缩放 · 拖拽平移 · 点击节点跳转交付物</p>
              <ProjectDag
                tasks={tasks.map((t) => ({
                  id: t.id,
                  name: t.name,
                  status: t.status,
                  agent: t.agent,
                  dependencies: t.dependencies,
                  token: byTask[t.id] ?? null,
                }))}
                selectedId={selectedTaskId}
                onSelect={(id) => selectTask(id, true)}
              />
            </TabsContent>

            <TabsContent value="exec" className="project-tab-panel project-tab-panel--exec">
              {selectedTaskId && (
                <ProjectTaskQualityCard projectId={projectId} taskId={selectedTaskId} compact />
              )}
              <ProjectExecTree
                tasks={tasks}
                events={events}
                selectedTaskId={selectedTaskId}
                onSelectTask={(id) => selectTask(id, false, false)}
                projectId={projectId}
              />
            </TabsContent>

            <TabsContent value="deliverable" className="project-tab-panel project-tab-panel--deliverable">
              {selectedTaskId ? (
                <>
                  <ProjectTaskQualityCard projectId={projectId} taskId={selectedTaskId} />
                  <ProjectDeliverablePanel
                    projectId={projectId}
                    tasks={tasks.map((t) => ({ id: t.id, name: t.name, status: t.status }))}
                    selectedTaskId={selectedTaskId}
                    onSelectTask={setSelectedTaskId}
                  />
                </>
              ) : (
                <p className="hint p-4">暂无任务</p>
              )}
            </TabsContent>

            <TabsContent value="cost" className="project-tab-panel">
              <section className="project-section">
                <h3>Token 成本</h3>
                <CostView cost={cost} ov={ov} pricePerMtok={pricePerMtok} />
              </section>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
