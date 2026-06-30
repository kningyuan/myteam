import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { createAgent, deleteAgent, suggestAgentId, type AgentSummary } from "@/lib/api/agents"
import { AgentEditDialog } from "@/components/manage/AgentEditDialog"
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
import { AgentDetailPanel } from "./AgentDetailPanel"

export function AgentsPanel({ agents }: { agents: AgentSummary[] }) {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [agentEditOpen, setAgentEditOpen] = useState(false)
  const [agentCreateOpen, setAgentCreateOpen] = useState(false)
  const [newAgentId, setNewAgentId] = useState("")
  const [newAgentName, setNewAgentName] = useState("")
  const [newAgentDesc, setNewAgentDesc] = useState("")

  useEffect(() => {
    if (!agentCreateOpen) return
    const desc = newAgentDesc.trim()
    if (desc.length <= 5 || newAgentId.trim()) return
    const timer = window.setTimeout(() => {
      suggestAgentId(desc)
        .then((id) => {
          if (id) setNewAgentId((prev) => prev || id)
        })
        .catch(() => {})
    }, 400)
    return () => window.clearTimeout(timer)
  }, [agentCreateOpen, newAgentDesc, newAgentId])

  const filteredAgents = useMemo(
    () =>
      sortByModifiedDesc(
        agents.filter((a) => matchQuery(search, a.id, a.name, a.backend, a.model, a.role, a.description)),
      ),
    [agents, search],
  )

  const selectedAgent = agents.find((a) => a.id === itemId) ?? null

  async function handleCreateAgent() {
    if (!newAgentDesc.trim() || !newAgentId.trim() || !newAgentName.trim()) return
    try {
      await createAgent({
        description: newAgentDesc.trim(),
        agent_id: newAgentId.trim(),
        chinese_name: newAgentName.trim(),
      })
      toast.success("Agent 已创建")
      setAgentCreateOpen(false)
      navigate(`/manage/agents/${encodeURIComponent(newAgentId.trim())}`)
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleDeleteAgent(id: string) {
    if (!window.confirm(`删除 Agent「${id}」？`)) return
    try {
      await deleteAgent(id)
      toast.success("已删除")
      navigate("/manage/agents")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            action={
              <Button size="sm" onClick={() => setAgentCreateOpen(true)}>
                新建
              </Button>
            }
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder="搜索 Agent…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {filteredAgents.map((a) => (
              <ListItemRow
                key={a.id}
                name={a.name || a.id}
                sub={`${a.role || ""} · ${a.backend || ""} · ${a.model || ""} · ${a.skills?.length ?? 0} skills`}
                tag={a.role || "other"}
                avatar={a.name || a.id}
                active={a.id === itemId}
                onClick={() => navigate(`/manage/agents/${encodeURIComponent(a.id)}`)}
              />
            ))}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader
            title="Agent"
            description="团队成员的后端、模型、Skill/MCP 与 Markdown 配置（修改 skill/mcp 挂载后自动同步）。"
          />
          {selectedAgent ? (
            <AgentDetailPanel
              agent={selectedAgent}
              onEdit={() => setAgentEditOpen(true)}
              onDelete={() => handleDeleteAgent(selectedAgent.id)}
            />
          ) : (
            <WelcomePane title="选择 Agent" description="左侧已列出全部成员，点选一项在右侧查看或编辑。" />
          )}
        </div>
      </DiscordShell>

      <AgentEditDialog
        agent={selectedAgent}
        open={agentEditOpen}
        onOpenChange={setAgentEditOpen}
        onSaved={() => {}}
      />

      <Dialog open={agentCreateOpen} onOpenChange={setAgentCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建 Agent</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>Agent ID</Label>
              <Input value={newAgentId} onChange={(e) => setNewAgentId(e.target.value)} placeholder="例如：writer" />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={newAgentName} onChange={(e) => setNewAgentName(e.target.value)} placeholder="中文名" />
            </div>
            <div className="grid gap-2">
              <Label>描述 *</Label>
              <Textarea value={newAgentDesc} onChange={(e) => setNewAgentDesc(e.target.value)} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAgentCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreateAgent}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
