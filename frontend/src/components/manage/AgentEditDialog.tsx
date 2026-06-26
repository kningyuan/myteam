import { useEffect, useMemo, useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { toast } from "sonner"
import { getAgentDetail, updateAgentManage, type AgentSummary } from "@/lib/api/agents"
import { listBackends, listBackendModels, type BackendModel, type BackendSummary } from "@/lib/api/config"
import { listMcpLibrary, type McpServerSummary } from "@/lib/api/mcp"
import { listSkillGroups, listSkillLibrary, type SkillGroup, type SkillLibraryItem } from "@/lib/api/workflows"
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

function SkillMountOption({
  name,
  disabled,
  checked,
  onChange,
  emphasized,
  title,
}: {
  name: string
  disabled?: boolean
  checked: boolean
  onChange: (checked: boolean) => void
  emphasized?: boolean
  title?: string
}) {
  return (
    <label className={`flex items-center gap-2 text-sm ${disabled ? "opacity-60" : ""}`}>
      <input
        type="checkbox"
        className="shrink-0"
        disabled={disabled}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className={emphasized ? "font-medium" : undefined} title={title}>
        {name}
      </span>
    </label>
  )
}

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
  const [skillIds, setSkillIds] = useState<string[]>([])
  const [mcpIds, setMcpIds] = useState<string[]>([])
  const [allSkills, setAllSkills] = useState<SkillLibraryItem[]>([])
  const [skillGroups, setSkillGroups] = useState<SkillGroup[]>([])
  const [allMcps, setAllMcps] = useState<McpServerSummary[]>([])
  const [backends, setBackends] = useState<BackendSummary[]>([])
  const [models, setModels] = useState<BackendModel[]>([])
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [busy, setBusy] = useState(false)
  const [expandedGroupIds, setExpandedGroupIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!agent || !open) return
    setName(agent.name || agent.id)
    setBackend(agent.backend || "opencode")
    setModel(agent.model || "")
    setWorkspace("")
    setSkillIds(agent.skills ?? [])
    setMcpIds(agent.mcp_servers ?? [])
    listSkillLibrary().then(setAllSkills).catch(() => setAllSkills([]))
    listSkillGroups().then(setSkillGroups).catch(() => setSkillGroups([]))
    listMcpLibrary(false).then(setAllMcps).catch(() => setAllMcps([]))
    listBackends().then(setBackends).catch(() => setBackends([]))
    setLoadingDetail(true)
    getAgentDetail(agent.id)
      .then((d) => {
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

  const groupedMemberIds = new Set(
    skillGroups.flatMap((g) => (g.members ?? []).map((m) => m.id)),
  )
  const standaloneSkills = allSkills.filter(
    (s) => s.is_mountable !== false && !groupedMemberIds.has(s.id),
  )

  const skillDisplayNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const s of allSkills) map.set(s.id, s.name || s.id)
    for (const g of skillGroups) {
      map.set(g.id, g.name || g.id)
      for (const m of g.members ?? []) map.set(m.id, m.name || m.id)
    }
    return map
  }, [allSkills, skillGroups])

  const selectedSkillLabels = useMemo(
    () =>
      skillIds.map((id) => ({
        id,
        name: skillDisplayNameById.get(id) || id,
      })),
    [skillIds, skillDisplayNameById],
  )

  useEffect(() => {
    if (!open) return
    const expanded = new Set<string>()
    for (const g of skillGroups) {
      const memberIds = (g.members ?? []).map((m) => m.id)
      if (skillIds.includes(g.id) || memberIds.some((id) => skillIds.includes(id))) {
        expanded.add(g.id)
      }
    }
    setExpandedGroupIds(expanded)
  }, [open, skillGroups, skillIds])

  function toggleGroupExpanded(groupId: string) {
    setExpandedGroupIds((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  function toggleSkillId(id: string, checked: boolean) {
    setSkillIds((prev) => {
      if (checked) return prev.includes(id) ? prev : [...prev, id]
      return prev.filter((x) => x !== id)
    })
  }

  function toggleGroup(group: SkillGroup, checked: boolean) {
    const memberIds = (group.members ?? []).map((m) => m.id)
    setSkillIds((prev) => {
      const without = prev.filter((x) => x !== group.id && !memberIds.includes(x))
      return checked ? [...without, group.id] : without
    })
  }

  function toggleGroupMember(group: SkillGroup, memberId: string, checked: boolean) {
    setSkillIds((prev) => {
      let next = prev.filter((x) => x !== group.id)
      if (checked) {
        if (!next.includes(memberId)) next = [...next, memberId]
      } else {
        next = next.filter((x) => x !== memberId)
      }
      return next
    })
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
            <Label>挂载 Skill</Label>
            <p className="hint text-xs">
              可勾选整组（如 Office 文档套件）或组内单项；组与成员互斥。Agent 须 Read 完整 SKILL.md 才能执行。
            </p>
            {selectedSkillLabels.length ? (
              <div className="flex flex-wrap gap-1.5">
                {selectedSkillLabels.map((s) => (
                  <span
                    key={s.id}
                    className="inline-flex rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]/40 px-2 py-1 text-xs font-medium"
                    title={s.id}
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            ) : null}
            {loadingDetail ? (
              <p className="text-xs text-[var(--color-muted-foreground)]">加载当前配置…</p>
            ) : (
              <div className="max-h-56 space-y-3 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                {skillGroups.length ? (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[var(--color-muted-foreground)]">按分类</p>
                    {skillGroups.map((group) => {
                      const groupChecked = skillIds.includes(group.id)
                      const groupName = group.name || group.id
                      const expanded = expandedGroupIds.has(group.id)
                      const memberCount = group.members?.length ?? 0
                      return (
                        <div key={group.id} className="rounded-md border border-[var(--color-border)]/60">
                          <div className="flex items-center gap-1 px-2 py-1.5">
                            <button
                              type="button"
                              className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-[var(--color-muted-foreground)] hover:bg-[var(--color-muted)]"
                              aria-expanded={expanded}
                              aria-label={expanded ? "收起分类" : "展开分类"}
                              onClick={() => toggleGroupExpanded(group.id)}
                            >
                              {expanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </button>
                            <SkillMountOption
                              name={`${groupName}${memberCount ? `（${memberCount}）` : ""}`}
                              title={group.id}
                              checked={groupChecked}
                              emphasized
                              onChange={(checked) => toggleGroup(group, checked)}
                            />
                          </div>
                          {expanded ? (
                            <div className="space-y-1 border-t border-[var(--color-border)]/60 px-2 py-2 pl-9">
                              {(group.members ?? []).map((m) => (
                                <SkillMountOption
                                  key={m.id}
                                  name={m.name || skillDisplayNameById.get(m.id) || m.id}
                                  title={m.id}
                                  disabled={groupChecked}
                                  checked={groupChecked || skillIds.includes(m.id)}
                                  onChange={(checked) => toggleGroupMember(group, m.id, checked)}
                                />
                              ))}
                              {!group.members?.length ? (
                                <p className="text-xs text-[var(--color-muted-foreground)]">该分类下暂无 Skill</p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                ) : null}
                {standaloneSkills.length ? (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-[var(--color-muted-foreground)]">未分类</p>
                    {standaloneSkills.map((s) => (
                      <SkillMountOption
                        key={s.id}
                        name={s.name || skillDisplayNameById.get(s.id) || s.id}
                        title={s.id}
                        checked={skillIds.includes(s.id)}
                        onChange={(checked) => toggleSkillId(s.id, checked)}
                      />
                    ))}
                  </div>
                ) : null}
                {!skillGroups.length && !standaloneSkills.length ? (
                  <p className="text-xs text-[var(--color-muted-foreground)]">Skill 库为空</p>
                ) : null}
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
