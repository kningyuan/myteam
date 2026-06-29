import { useResourceQuery } from "@/hooks/useResourceQuery"
import { hubFetch } from "@/lib/api/client"
import { DiscordShell } from "@/components/layout/DiscordShell"
import { StatCard } from "@/components/manage/StatCard"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { Link } from "react-router-dom"
import {
  FolderKanban,
  MessageCircle,
  Workflow,
  Sparkles,
  Activity,
  CheckCircle2,
  PlayCircle,
  PauseCircle,
  AlertCircle,
  ArrowRight,
  Zap,
} from "lucide-react"

// ── Types ──────────────────────────────────────────

interface SummaryProject {
  id: string
  title: string
  status: string
  mode: string
  progress: number
  task_count: number
  tokens: number
  budget: number
  budget_ratio: number
  budget_state: string
  updated_at: string
}

interface SummaryResponse {
  projects: SummaryProject[]
  totals?: {
    projects?: number
    running?: number
    tokens?: number
    agents?: number
  }
}

interface AgentInfo {
  id: string
  name: string
  role: string
  description: string
  task_types: string[]
  skills: string[]
  backend: string
  model: string
}

// ── Helpers ────────────────────────────────────────

function statusIcon(status: string) {
  switch (status) {
    case "completed":
      return <CheckCircle2 size={14} className="text-emerald-500" />
    case "in_progress":
    case "running":
      return <PlayCircle size={14} className="text-blue-500" />
    case "paused":
      return <PauseCircle size={14} className="text-amber-500" />
    case "failed":
      return <AlertCircle size={14} className="text-red-500" />
    default:
      return <Activity size={14} className="text-muted-foreground" />
  }
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M"
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K"
  return String(n)
}

function formatTime(iso: string): string {
  if (!iso) return "—"
  const d = new Date(iso)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return "刚刚"
  if (diff < 3600) return Math.floor(diff / 60) + " 分钟前"
  if (diff < 86400) return Math.floor(diff / 3600) + " 小时前"
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
}

// ── Dashboard ──────────────────────────────────────

export function DashboardPage() {
  const { data: summary, loading: summaryLoading } = useResourceQuery<SummaryResponse>(
    "dashboard",
    () => hubFetch<SummaryResponse>("/api/obs/summary"),
    { projects: [] },
  )

  const { data: agentsData } = useResourceQuery<{ agents: AgentInfo[] }>(
    "agents",
    () => hubFetch<{ agents: AgentInfo[] }>("/api/agents"),
    { agents: [] },
  )

  const projects = summary.projects || []
  const agents = agentsData.agents || []
  const runningCount = projects.filter(
    (p) => p.status === "in_progress" || p.status === "running",
  ).length
  const totalTokens = projects.reduce((sum, p) => sum + (p.tokens || 0), 0)
  const workerAgents = agents.filter((a) => a.role === "worker")

  const quickLinks = [
    { to: "/chat", icon: MessageCircle, label: "对话", desc: "与 Agent 一对一交流" },
    { to: "/projects", icon: FolderKanban, label: "项目", desc: "编排任务 DAG" },
    { to: "/workflows", icon: Workflow, label: "流程", desc: "定义团队协作流" },
    { to: "/skills", icon: Sparkles, label: "Skill", desc: "管理能力技能包" },
  ]

  return (
    <DiscordShell>
      <div className="discord-main-scroll">
        {/* 欢迎区 */}
        <div className="dashboard-hero">
          <h1 className="dashboard-hero-title">myteam Agent Hub</h1>
          <p className="dashboard-hero-desc">
            多 Agent 协作平台 — 项目编排 · 团队对话 · 能力管理 · 全链路可观测
          </p>
        </div>

        {/* 统计卡片 */}
        <div className="dashboard-stat-grid">
          <StatCard
            title="项目总数"
            count={projects.length}
            badge={
              runningCount > 0
                ? { label: `${runningCount} 运行中`, variant: "default" }
                : undefined
            }
          />
          <StatCard
            title="Agent 团队"
            count={agents.length}
            badge={{ label: `${workerAgents.length} 个 Worker`, variant: "secondary" }}
          />
          <div className="stat-card stat-card-token">
            <div className="stat-card-value">{formatTokens(totalTokens)}</div>
            <div className="stat-card-label">累计 Token</div>
            <div className="stat-card-hint flex items-center gap-1">
              <Zap size={12} /> {projects.length} 个项目
            </div>
          </div>
          <StatCard
            title="运行中项目"
            count={runningCount}
            badge={
              runningCount === 0
                ? { label: "空闲", variant: "outline" }
                : undefined
            }
          />
        </div>

        {/* 主体两栏 */}
        <div className="dashboard-body-grid">
          {/* 左栏：最近项目 */}
          <section className="dashboard-section">
            <div className="dashboard-section-header">
              <h2 className="dashboard-section-title">最近项目</h2>
              <Link to="/projects" className="dashboard-section-link">
                全部 <ArrowRight size={14} />
              </Link>
            </div>

            {summaryLoading && projects.length === 0 ? (
              <div className="dashboard-empty">加载中…</div>
            ) : projects.length === 0 ? (
              <div className="dashboard-empty">
                还没有项目，去
                <Link to="/projects" className="dashboard-inline-link">项目页</Link>
                发起一个吧
              </div>
            ) : (
              <div className="dashboard-project-list">
                {projects.slice(0, 6).map((p) => (
                  <Link
                    key={p.id}
                    to={`/projects/${p.id}`}
                    className="dashboard-project-row"
                  >
                    <div className="dashboard-project-info">
                      <div className="dashboard-project-name-row">
                        {statusIcon(p.status)}
                        <span className="dashboard-project-name">{p.title}</span>
                      </div>
                      <div className="dashboard-project-meta">
                        <span>{p.task_count} 任务</span>
                        <span>·</span>
                        <span>{formatTokens(p.tokens)} tokens</span>
                        <span>·</span>
                        <span>{formatTime(p.updated_at)}</span>
                      </div>
                    </div>
                    <div className="dashboard-project-right">
                      <div className="progress-bar" style={{ width: 80 }}>
                        <div
                          className={cn(
                            "progress-fill",
                            p.budget_state === "over" && "progress-fill-over",
                          )}
                          style={{
                            width: `${Math.min(p.progress * 100, 100)}%`,
                          }}
                        />
                      </div>
                      <span className="dashboard-project-progress">
                        {Math.round(p.progress * 100)}%
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          {/* 右栏：Agent 团队 + 快捷入口 */}
          <div className="dashboard-side">
            <section className="dashboard-section">
              <div className="dashboard-section-header">
                <h2 className="dashboard-section-title">Agent 团队</h2>
                <Link to="/manage" className="dashboard-section-link">
                  管理 <ArrowRight size={14} />
                </Link>
              </div>
              <div className="dashboard-agent-list">
                {agents.slice(0, 8).map((a) => (
                  <Link
                    key={a.id}
                    to={`/chat/${a.id}`}
                    className="dashboard-agent-row"
                  >
                    <div className="dashboard-agent-avatar" data-role={a.role}>
                      {a.name.charAt(0)}
                    </div>
                    <div className="dashboard-agent-info">
                      <span className="dashboard-agent-name">{a.name}</span>
                      <span className="dashboard-agent-meta">
                        {a.role === "coordinator" ? "协调者" : `${a.skills.length} skills`}
                      </span>
                    </div>
                    <Badge variant="outline" className="dashboard-agent-badge">
                      {a.task_types.length} types
                    </Badge>
                  </Link>
                ))}
              </div>
            </section>

            <section className="dashboard-section">
              <div className="dashboard-section-header">
                <h2 className="dashboard-section-title">快捷入口</h2>
              </div>
              <div className="dashboard-quick-grid">
                {quickLinks.map(({ to, icon: Icon, label, desc }) => (
                  <Link key={to} to={to} className="quick-link-card dashboard-quick-card">
                    <div className="quick-link-icon">
                      <Icon size={18} strokeWidth={1.75} />
                    </div>
                    <div className="quick-link-label">{label}</div>
                    <div className="quick-link-desc">{desc}</div>
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>
    </DiscordShell>
  )
}
