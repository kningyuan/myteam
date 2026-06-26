import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ChevronLeft } from "lucide-react"
import {
  getDeliverableMarkdown,
  getProject,
  type ProjectDetail,
  type ProjectTask,
} from "@/lib/api/projects"
import { MarkdownBody } from "@/components/MarkdownBody"
import { ProjectDag } from "@/components/project/ProjectDag"
import { PageHeader, Pill, statusLabel, StatusBadge } from "@/components/ui/page"

function TaskListItem({
  task,
  selected,
  onSelect,
}: {
  task: ProjectTask
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border px-3 py-2.5 text-left transition ${
        selected
          ? "border-[var(--color-brand)]/50 bg-[var(--color-brand)]/10"
          : "border-transparent bg-white/3 hover:bg-white/6"
      }`}
    >
      <div className="text-sm font-medium">{task.name || task.id}</div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--color-muted-foreground)]">
        {task.agent && <span>@{task.agent}</span>}
        <StatusBadge status={task.status} label={statusLabel(task.status)} />
      </div>
    </button>
  )
}

export function ProjectDetailPage() {
  const { projectId = "" } = useParams()
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [selectedTaskId, setSelectedTaskId] = useState<string>("")
  const [deliverable, setDeliverable] = useState("")
  const [deliverableError, setDeliverableError] = useState("")
  const [deliverableLoading, setDeliverableLoading] = useState(false)

  useEffect(() => {
    if (!projectId) return
    getProject(projectId)
      .then((p) => {
        setProject(p)
        const first = p.tasks?.[0]?.id
        if (first) setSelectedTaskId(first)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [projectId])

  useEffect(() => {
    if (!projectId || !selectedTaskId) return
    setDeliverable("")
    setDeliverableError("")
    setDeliverableLoading(true)
    getDeliverableMarkdown(projectId, selectedTaskId)
      .then(setDeliverable)
      .catch((e: Error) => setDeliverableError(e.message))
      .finally(() => setDeliverableLoading(false))
  }, [projectId, selectedTaskId])

  if (loading) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载项目…</p>
  }

  if (error || !project) {
    return (
      <div className="space-y-4">
        <Link to="/projects" className="inline-flex items-center gap-1 text-sm text-[#00a8fc] hover:underline">
          <ChevronLeft className="h-4 w-4" /> 返回项目列表
        </Link>
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error || "项目不存在"}
        </div>
      </div>
    )
  }

  const tasks = project.tasks ?? []
  const selected = tasks.find((t) => t.id === selectedTaskId)

  return (
    <div className="space-y-6">
      <Link to="/projects" className="inline-flex items-center gap-1 text-sm text-[#00a8fc] hover:underline">
        <ChevronLeft className="h-4 w-4" /> 返回项目列表
      </Link>

      <PageHeader
        title={project.name || project.id}
        description={project.goal || undefined}
        action={<StatusBadge status={project.status} label={statusLabel(project.status)} />}
      />

      <div className="flex flex-wrap gap-2">
        {project.meta?.workflow && <Pill tone="brand">流程：{project.meta.workflow}</Pill>}
        <Pill>{tasks.length} 个任务</Pill>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="mb-4 text-sm font-semibold text-[var(--color-sidebar-fg)]">任务编排</h2>
        <ProjectDag tasks={tasks} selectedId={selectedTaskId} onSelect={setSelectedTaskId} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          <h2 className="px-1 text-sm font-semibold text-[var(--color-sidebar-fg)]">任务列表</h2>
          {tasks.map((t) => (
            <TaskListItem
              key={t.id}
              task={t}
              selected={t.id === selectedTaskId}
              onSelect={() => setSelectedTaskId(t.id)}
            />
          ))}
        </div>

        <div className="min-h-[320px] rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="mb-4 text-sm font-semibold text-[var(--color-sidebar-fg)]">
            交付物{selected ? ` · ${selected.name || selected.id}` : ""}
          </h2>
          {deliverableLoading ? (
            <p className="text-sm text-[var(--color-muted-foreground)]">正在加载交付物…</p>
          ) : deliverableError ? (
            <p className="text-sm text-[var(--color-muted-foreground)]">{deliverableError}</p>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto rounded-lg bg-[var(--color-background)] p-4">
              <MarkdownBody content={deliverable} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
