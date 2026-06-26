import { useEffect, useState } from "react"
import {
  listAgents,
  type AgentSummary,
  updateAgentRegistry,
  type AgentDetail,
  getAgentDetail,
} from "@/lib/api/agents"
import { listTaskTypes, type TaskTypeSummary } from "@/lib/api/workflows"
import { EmptyState, PageHeader, Pill, StatusBadge } from "@/components/ui/page"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "sonner"

export function AgentsPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [taskTypes, setTaskTypes] = useState<TaskTypeSummary[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"overview" | "role">("overview")

  // Edit dialog state
  const [editOpen, setEditOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<AgentSummary | null>(null)
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [editRole, setEditRole] = useState("worker")
  const [editCapabilities, setEditCapabilities] = useState("")
  const [editTaskTypes, setEditTaskTypes] = useState("")
  const [editBusy, setEditBusy] = useState(false)

  useEffect(() => {
    Promise.all([listAgents(), listTaskTypes()])
      .then(([a, t]) => {
        setAgents(a)
        setTaskTypes(t)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function openEdit(agent: AgentSummary) {
    setEditingAgent(agent)
    setEditRole(agent.role || "worker")
    setEditCapabilities((agent.capabilities || []).join(", "))
    setEditTaskTypes((agent.task_types || []).join(", "))
    setEditOpen(true)
    // Load full detail for skills/MCP info
    getAgentDetail(agent.id)
      .then(setDetail)
      .catch(() => setDetail(null))
  }

  async function handleSaveEdit() {
    if (!editingAgent) return
    setEditBusy(true)
    try {
      const capabilities = editCapabilities
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean)
      const task_types = editTaskTypes
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean)
      await updateAgentRegistry(editingAgent.id, {
        role: editRole,
        capabilities,
        task_types,
      })
      toast.success("Agent 注册信息已更新")
      setEditOpen(false)
      // Refresh agent list
      const [a] = await Promise.all([listAgents()])
      setAgents(a)
    } catch (e) {
      toast.error("更新失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setEditBusy(false)
    }
  }

  if (loading) return <p className="text-sm text-[var(--color-muted-foreground)]">加载 Agent…</p>

  return (
    <div className="space-y-6">
      <PageHeader title="Agent" description="团队中的 AI 成员。详细配置与后端绑定请在经典版「管理」中操作。" />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>
      )}

      {/* Tab bar */}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={activeTab === "overview" ? "default" : "outline"}
          onClick={() => setActiveTab("overview")}
        >
          概览
        </Button>
        <Button
          size="sm"
          variant={activeTab === "role" ? "default" : "outline"}
          onClick={() => setActiveTab("role")}
        >
          Role & Capabilities
        </Button>
      </div>

      {activeTab === "overview" && (
        <>
          {!agents.length ? (
            <EmptyState title="暂无 Agent" description="请先在经典版界面初始化 Agent 团队。" />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {agents.map((a) => (
                <article
                  key={a.id}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h2 className="font-semibold">{a.name || a.id}</h2>
                      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">角色标识：{a.id}</p>
                    </div>
                    <StatusBadge
                      status={a.status === "online" || a.status === "ready" ? "online" : "offline"}
                      label={a.status || "未知"}
                    />
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === "role" && (
        <>
          {!agents.length ? (
            <EmptyState title="暂无 Agent" description="请先在经典版界面初始化 Agent 团队。" />
          ) : (
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-sm">
                <thead className="bg-[var(--color-accent)] text-left text-xs text-[var(--color-muted-foreground)]">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">角色</th>
                    <th className="px-4 py-3 font-medium">能力标签</th>
                    <th className="px-4 py-3 font-medium">可接 task_type</th>
                    <th className="px-4 py-3 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)] bg-[var(--color-card)]">
                  {agents.map((a) => (
                    <tr key={a.id} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3">
                        <div className="font-medium">{a.name || a.id}</div>
                        <div className="text-xs text-[var(--color-muted-foreground)] font-mono">{a.id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Pill tone="brand">{a.role || "worker"}</Pill>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {(a.capabilities || []).length ? (
                            (a.capabilities || []).map((c) => (
                              <Badge key={c} variant="secondary">
                                {c}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-[var(--color-muted-foreground)]">未配置</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {(a.task_types || []).length ? (
                            (a.task_types || []).map((tt) => {
                              const summary = taskTypes.find((t) => t.task_type === tt)
                              return (
                                <Badge key={tt} variant="outline" title={tt}>
                                  {summary?.display_name || tt}
                                </Badge>
                              )
                            })
                          ) : (
                            <span className="text-xs text-[var(--color-muted-foreground)]">未配置</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Button size="sm" variant="outline" onClick={() => openEdit(a)}>
                          编辑
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑 Agent：{editingAgent?.name || editingAgent?.id}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>角色（role）</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
              >
                <option value="worker">worker</option>
                <option value="coordinator">coordinator</option>
                <option value="reviewer">reviewer</option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label>能力标签（逗号分隔）</Label>
              <Input
                value={editCapabilities}
                onChange={(e) => setEditCapabilities(e.target.value)}
                placeholder="例如：写作，研究，分析"
              />
            </div>
            <div className="grid gap-2">
              <Label>可接 task_type（逗号分隔）</Label>
              <Textarea
                rows={3}
                value={editTaskTypes}
                onChange={(e) => setEditTaskTypes(e.target.value)}
                placeholder="例如：requirements，design，code-review"
              />
            </div>
          </div>
          {detail && (
            <>
              <Separator />
              <div className="text-xs text-[var(--color-muted-foreground)]">
                <p className="font-medium text-[var(--color-foreground)]">当前挂载信息（不可在此编辑）：</p>
                <p>后端：{detail.backend || "—"} | 模型：{detail.model || "—"}</p>
                <p>Skill：{(detail.registry_skills || []).length} 个 | MCP：{(detail.registry_mcp_servers || []).length} 个</p>
              </div>
            </>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button disabled={editBusy} onClick={() => void handleSaveEdit()}>
              {editBusy ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
