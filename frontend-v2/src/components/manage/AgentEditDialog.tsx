import { useEffect, useState } from "react"
import { toast } from "sonner"
import { getAgentDetail, suggestAgentTaskTypes, updateAgentManage, type AgentSummary } from "@/lib/api/agents"
import { listBackends, listBackendModels, type BackendModel, type BackendSummary } from "@/lib/api/config"
import { listMcpLibrary, type McpServerSummary } from "@/lib/api/mcp"
import { listSkillLibrary, listTaskTypes, type SkillLibraryItem, type TaskTypeSummary } from "@/lib/api/workflows"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function AgentEditDialog({
  agent,
  open,
  onOpenChange,
  onSaved,
}: {
  agent: AgentSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [name, setName] = useState("")
  const [backend, setBackend] = useState("")
  const [model, setModel] = useState("")
  const [workspace, setWorkspace] = useState("")
  const [taskTypes, setTaskTypes] = useState<string[]>([])
  const [skillIds, setSkillIds] = useState<string[]>([])
  const [mcpIds, setMcpIds] = useState<string[]>([])
  const [allTaskTypes, setAllTaskTypes] = useState<TaskTypeSummary[]>([])
  const [allSkills, setAllSkills] = useState<SkillLibraryItem[]>([])
  const [allMcps, setAllMcps] = useState<McpServerSummary[]>([])
  const [backends, setBackends] = useState<BackendSummary[]>([])
  const [models, setModels] = useState<BackendModel[]>([])
  const [busy, setBusy] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    if (!agent || !open) return
    setName(agent.name || agent.id)
    setBackend(agent.backend || "opencode")
    setModel(agent.model || "")
    setWorkspace("")
    setTaskTypes(agent.task_types ?? [])
    setSkillIds(agent.skills ?? [])
    setMcpIds(agent.mcp_servers ?? [])
    listTaskTypes().then(setAllTaskTypes).catch(() => setAllTaskTypes([]))
    listSkillLibrary().then(setAllSkills).catch(() => setAllSkills([]))
    listMcpLibrary(false).then(setAllMcps).catch(() => setAllMcps([]))
    listBackends().then(setBackends).catch(() => setBackends([]))
    setLoadingDetail(true)
    getAgentDetail(agent.id)
      .then((d) => {
        setTaskTypes(d.task_types ?? agent.task_types ?? [])
        const ids = d.registry_skills ?? d.skills?.map((s) => s.skill_id) ?? []
        setSkillIds(ids)
        setMcpIds(d.registry_mcp_servers ?? d.mcp_servers?.map((m) => m.server_id) ?? agent.mcp_servers ?? [])
        setWorkspace(d.workspace || "")
        setBackend(d.backend || agent.backend || "opencode")
        setModel(d.model || agent.model || "")
      })
      .catch(() => {})
      .finally(() => setLoadingDetail(false))
  }, [agent, open])

  useEffect(() => {
    if (!backend) return
    listBackendModels(backend)
      .then((ms) => {
        setModels(ms)
        if (!model && ms[0]) setModel(ms[0].id)
      })
      .catch(() => setModels([]))
  }, [backend])

  async function handleSuggestTaskTypes() {
    if (!agent) return
    setBusy(true)
    try {
      const detail = await getAgentDetail(agent.id).catch(() => null)
      const desc = detail?.files?.["AGENTS.md"] || agent.description || ""
      const res = await suggestAgentTaskTypes({
        description: desc,
        name: name.trim() || agent.name || agent.id,
        agent_id: agent.id,
      })
      const suggested = res.task_types ?? []
      if (!suggested.length) {
        toast.message("未推导出 task_type")
        return
      }
      setTaskTypes((prev) => [...new Set([...prev, ...suggested])])
      toast.success(`已勾选 ${suggested.length} 个 task_type`, {
        description: res.pattern ? `来源：${res.pattern}` : undefined,
      })
    } catch (e) {
      toast.error("推导失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setBusy(false)
    }
  }

  async function handleSave() {
    if (!agent || !name.trim()) return
    setBusy(true)
    try {
      await updateAgentManage(agent.id, {
        name: name.trim(),
        backend,
        model,
        workspace: workspace.trim(),
        task_types: taskTypes,
        skills: skillIds,
        mcp_servers: mcpIds,
      })
      toast.success("Agent 已保存")
      onOpenChange(false)
      onSaved()
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑 Agent · {agent?.id}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label>显示名称</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>后端</Label>
              <Select value={backend} onValueChange={setBackend}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {backends.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name || b.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>模型</Label>
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {model && !models.some((m) => m.id === model) ? (
                    <SelectItem value={model}>{model}（当前）</SelectItem>
                  ) : null}
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name || m.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label>工作目录（可选）</Label>
            <Input value={workspace} onChange={(e) => setWorkspace(e.target.value)} placeholder="留空使用默认" />
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-2">
              <Label>交付物类型（task_type）</Label>
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void handleSuggestTaskTypes()}>
                按职责推导
              </Button>
            </div>
            <p className="hint text-xs">决定 workflow 可派哪些交付任务与 Gate 格式，不是 Skill 列表。</p>
            <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
              {allTaskTypes.map((t) => (
                <label key={t.task_type} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={taskTypes.includes(t.task_type)}
                    onChange={(e) => {
                      setTaskTypes((prev) =>
                        e.target.checked
                          ? [...prev, t.task_type]
                          : prev.filter((x) => x !== t.task_type),
                      )
                    }}
                  />
                  <span title={t.task_type}>{t.display_name || t.task_type}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="grid gap-2">
            <Label>挂载 Skill</Label>
            <p className="hint text-xs">
              Agent 仅可使用勾选的 Skill（私聊 / 群聊 / workflow 统一生效）。在 Skill 页查看全部可用 Skill。
            </p>
            {loadingDetail ? (
              <p className="text-xs text-[var(--color-muted-foreground)]">加载当前配置…</p>
            ) : (
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                {allSkills.filter((s) => s.is_mountable !== false).length ? (
                  allSkills
                    .filter((s) => s.is_mountable !== false)
                    .map((s) => (
                    <label key={s.id} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={skillIds.includes(s.id)}
                        onChange={(e) => {
                          setSkillIds((prev) =>
                            e.target.checked ? [...prev, s.id] : prev.filter((x) => x !== s.id),
                          )
                        }}
                      />
                      <span title={s.id}>
                        <span className="font-medium">{s.name || s.id}</span>
                        {s.description ? (
                          <span className="block text-xs text-[var(--color-muted-foreground)]">{s.description}</span>
                        ) : null}
                      </span>
                    </label>
                  ))
                ) : (
                  <p className="text-xs text-[var(--color-muted-foreground)]">Skill 库为空</p>
                )}
              </div>
            )}
          </div>
          <div className="grid gap-2">
            <Label>挂载 MCP</Label>
            <p className="hint text-xs">
              仅显示全局已启用的 MCP；勾选后由 Agent 所用 CLI 后端同步到工作区配置。
            </p>
            {loadingDetail ? (
              <p className="text-xs text-[var(--color-muted-foreground)]">加载当前配置…</p>
            ) : (
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                {allMcps.filter((s) => s.is_mountable !== false).length ? (
                  allMcps
                    .filter((s) => s.is_mountable !== false)
                    .map((s) => (
                      <label key={s.id} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={mcpIds.includes(s.id)}
                          onChange={(e) => {
                            setMcpIds((prev) =>
                              e.target.checked ? [...prev, s.id] : prev.filter((x) => x !== s.id),
                            )
                          }}
                        />
                        <span title={s.id}>
                          <span className="font-medium">{s.name || s.id}</span>
                          {s.description ? (
                            <span className="block text-xs text-[var(--color-muted-foreground)]">{s.description}</span>
                          ) : null}
                        </span>
                      </label>
                    ))
                ) : (
                  <p className="text-xs text-[var(--color-muted-foreground)]">
                    无可用 MCP，请先在 MCP 页启用服务
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={busy}>
            {busy ? "保存中…" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
