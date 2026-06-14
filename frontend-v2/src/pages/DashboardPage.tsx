import { Link } from "react-router-dom"
import { ArrowRight, Bot, FolderKanban, Users, Workflow } from "lucide-react"
import { listAgents } from "@/lib/api/agents"
import { getObsSummary, type ObsSummary } from "@/lib/api/config"
import { listGroups } from "@/lib/api/groups"
import { listProjects } from "@/lib/api/projects"
import { listWorkflows } from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { Button } from "@/components/ui/button"
import { EmptyState, formatNumber, PageHeader, statusLabel, StatusBadge } from "@/components/ui/page"

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-value">{value}</div>
      <div className="stat-card-label">{label}</div>
      {hint && <div className="stat-card-hint">{hint}</div>}
    </div>
  )
}

type DashboardSnapshot = {
  summary: ObsSummary | null
  counts: { projects: number; groups: number; agents: number; workflows: number }
}

async function loadDashboard(): Promise<DashboardSnapshot> {
  const [obs, projects, groups, agents, workflows] = await Promise.all([
    getObsSummary().catch(() => null),
    listProjects(),
    listGroups(),
    listAgents(),
    listWorkflows(),
  ])
  return {
    summary: obs,
    counts: {
      projects: projects.length,
      groups: groups.filter((g) => g.status !== "dissolved").length,
      agents: agents.length,
      workflows: workflows.length,
    },
  }
}

export function DashboardPage() {
  const { data, loading, error } = useResourceQuery("dashboard", loadDashboard, {
    summary: null,
    counts: { projects: 0, groups: 0, agents: 0, workflows: 0 },
  })

  if (loading && !data.summary && data.counts.projects === 0) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载工作台…</p>
  }

  const summary = data.summary
  const counts = data.counts
  const totals = summary?.totals
  const running = totals?.running ?? 0
  const tokens = totals?.tokens ?? 0

  const quickLinks = [
    { to: "/projects", label: "项目", desc: "查看进度与交付物", icon: FolderKanban },
    { to: "/groups", label: "群组", desc: "团队协作与 @Agent", icon: Users },
    { to: "/chat", label: "对话", desc: "与 Agent 1 对 1", icon: Bot },
    { to: "/workflows", label: "流程", desc: "已注册工作流", icon: Workflow },
  ]

  return (
    <div className="space-y-8">
      <PageHeader
        title="总览"
        description="一眼看清团队项目、协作群与 Agent 运行情况。"
        action={
          <Button asChild>
            <Link to="/projects">
              查看项目
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {error && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-[var(--color-warning)]">
          部分数据未能加载：{error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="项目总数" value={counts.projects} hint={`${running} 个运行中`} />
        <StatCard label="活跃群组" value={counts.groups} />
        <StatCard label="Agent" value={counts.agents} />
        <StatCard label="累计 Token" value={formatNumber(tokens)} hint={`已完成 ${totals?.completed ?? 0} 个任务`} />
      </div>

      <section className="space-y-3">
        <h2 className="section-heading">快捷入口</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {quickLinks.map(({ to, label, desc, icon: Icon }) => (
            <Link key={to} to={to}>
              <div className="quick-link-card">
                <div className="quick-link-icon">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="text-sm font-medium">{label}</div>
                <div className="mt-1 text-xs text-[var(--color-muted-foreground)]">{desc}</div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="section-heading">最近项目</h2>
          <Link to="/projects" className="text-xs text-[var(--color-brand-light)] hover:underline">
            全部项目
          </Link>
        </div>
        {summary?.projects?.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {summary.projects.slice(0, 4).map((p) => (
              <Link key={p.id} to={`/projects/${encodeURIComponent(p.id)}`}>
                <div className="project-summary-card">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-medium">{p.title || p.id}</div>
                    <StatusBadge status={p.status} label={statusLabel(p.status)} />
                  </div>
                  <div className="mt-3">
                    <div className="mb-1 flex justify-between text-xs text-[var(--color-muted-foreground)]">
                      <span>{p.task_count ?? 0} 个任务</span>
                      <span>{Math.round((p.progress || 0) * 100)}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-[var(--color-accent)]">
                      <div
                        className="h-full rounded-full bg-[var(--color-brand)] transition-all"
                        style={{ width: `${Math.round((p.progress || 0) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState title="还没有项目" description="点击「项目 → 新建」发起第一个项目。" />
        )}
      </section>
    </div>
  )
}
