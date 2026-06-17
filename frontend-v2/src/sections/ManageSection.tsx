import { useEffect, useMemo, useRef, useState, useCallback } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  createAgent,
  deleteAgent,
  getAgentDetail,
  listAgents,
  saveAgentWorkspaceFile,
  saveSharedRuleFile,
  suggestAgentId,
  syncAgentSkills,
  syncAgentMcp,
  type AgentDetail,
  type AgentSkillRef,
  type AgentSummary,
} from "@/lib/api/agents"
import { listMemory, getMemory, deleteMemory, type MemoryEntry } from "@/lib/api/projects"
import { listMcpLibrary } from "@/lib/api/mcp"
import {
  createTaskType,
  deleteDeliveryTemplate,
  deleteTaskType,
  getDeliveryTemplate,
  listDeliveryTemplates,
  listOutcomeKinds,
  listSkillLibrary,
  listTaskTypes,
  saveDeliveryTemplate,
  suggestTaskType,
  updateTaskType,
  type DeliveryTemplateSummary,
  type OutcomeKind,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { useResourceQuery, useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { AgentEditDialog } from "@/components/manage/AgentEditDialog"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { matchQuery } from "@/components/manage/ManageSearchBar"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
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
import { MarkdownBody } from "@/components/MarkdownBody"
import { gateLabel } from "@/components/ui/page"
import { cn } from "@/lib/utils"

type ManageTab = "agents" | "task-types" | "templates" | "knowledge"

const AGENT_WORKSPACE_FILES = [
  "IDENTITY.md",
  "SOUL.md",
  "USER.md",
] as const

type AgentWorkspaceFileName = (typeof AGENT_WORKSPACE_FILES)[number]

const AGENT_FILE_LABELS: Record<AgentWorkspaceFileName, string> = {
  "IDENTITY.md": "身份定义",
  "SOUL.md": "人格风格",
  "USER.md": "用户偏好",
}

type ConfigFileKey =
  | { scope: "shared"; filename: string }
  | { scope: "workspace"; filename: AgentWorkspaceFileName }

function configFileId(key: ConfigFileKey): string {
  return key.scope === "shared" ? `shared:${key.filename}` : `ws:${key.filename}`
}

function AgentConfigFilesEditor({
  agentId,
  workspaceFiles,
  sharedRules,
  sharedRuleMeta,
  loading,
}: {
  agentId: string
  workspaceFiles: Record<string, string>
  sharedRules: Record<string, string>
  sharedRuleMeta: { filename: string; label: string }[]
  loading: boolean
}) {
  const fileKeys = useMemo<ConfigFileKey[]>(() => {
    const shared: ConfigFileKey[] = sharedRuleMeta.map((f) => ({
      scope: "shared",
      filename: f.filename,
    }))
    const ws: ConfigFileKey[] = AGENT_WORKSPACE_FILES.map((filename) => ({
      scope: "workspace",
      filename,
    }))
    return [...shared, ...ws]
  }, [sharedRuleMeta])

  const [selected, setSelected] = useState<ConfigFileKey>(() => ({
    scope: "shared",
    filename: sharedRuleMeta[0]?.filename || "ethos.md",
  }))
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, string>>({})
  const [view, setView] = useState<"edit" | "preview">("edit")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const key of fileKeys) {
      const id = configFileId(key)
      if (key.scope === "shared") {
        next[id] = sharedRules[key.filename] ?? ""
      } else {
        next[id] = workspaceFiles[key.filename] ?? ""
      }
    }
    setDrafts(next)
    setSaved(next)
    const first = fileKeys[0]
    if (first) setSelected(first)
    setView("edit")
  }, [agentId, workspaceFiles, sharedRules, fileKeys])

  const selectedId = configFileId(selected)
  const currentDraft = drafts[selectedId] ?? ""
  const isDirty = currentDraft !== (saved[selectedId] ?? "")

  function labelFor(key: ConfigFileKey): string {
    if (key.scope === "shared") {
      return sharedRuleMeta.find((f) => f.filename === key.filename)?.label || key.filename
    }
    return AGENT_FILE_LABELS[key.filename]
  }

  function selectFile(key: ConfigFileKey) {
    if (configFileId(key) === selectedId) return
    if (isDirty && !window.confirm(`${labelFor(selected)} 有未保存的修改，确定切换文件？`)) return
    setSelected(key)
    setView("edit")
  }

  async function handleSave() {
    setSaving(true)
    try {
      if (selected.scope === "shared") {
        await saveSharedRuleFile(selected.filename, currentDraft)
        toast.success(`${labelFor(selected)} 已保存（全员生效）`)
      } else {
        await saveAgentWorkspaceFile(agentId, selected.filename, currentDraft)
        toast.success(`${labelFor(selected)} 已保存`)
      }
      setSaved((prev) => ({ ...prev, [selectedId]: currentDraft }))
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="workspace-panel agent-config-files-panel">
      <header className="agent-detail-capability-head">
        <div>
          <h3 className="text-sm font-semibold">Markdown 配置</h3>
          <p className="hint text-xs">团队通用规则改一处全员更新；下方为当前 Agent 工作区专属文件</p>
        </div>
      </header>
      <div className="agent-config-files">
        <nav className="agent-config-file-list" aria-label="配置文件">
          {fileKeys.map((key) => {
            const id = configFileId(key)
            const dirty = (drafts[id] ?? "") !== (saved[id] ?? "")
            const empty = !(saved[id] ?? "").trim()
            const label = labelFor(key)
            return (
              <button
                key={id}
                type="button"
                className={cn("agent-config-file-item", selectedId === id && "active")}
                onClick={() => selectFile(key)}
              >
                <span className="agent-config-file-name">{label}</span>
                <span className="agent-config-file-label">
                  {key.scope === "shared" ? "团队通用" : key.filename}
                </span>
                {(dirty || empty) && (
                  <span className="agent-config-file-badge">{dirty ? "未保存" : "空"}</span>
                )}
              </button>
            )
          })}
        </nav>
        <div className="agent-config-file-main">
          <div className="agent-config-file-toolbar">
            <div className="min-w-0">
              <p className="text-sm font-semibold">{labelFor(selected)}</p>
              <p className="hint font-mono text-xs">
                {selected.scope === "shared" ? `business/rules/${selected.filename}` : selected.filename}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button
                size="sm"
                variant={view === "edit" ? "default" : "outline"}
                onClick={() => setView("edit")}
              >
                编辑
              </Button>
              <Button
                size="sm"
                variant={view === "preview" ? "default" : "outline"}
                onClick={() => setView("preview")}
              >
                预览
              </Button>
              <Button size="sm" onClick={handleSave} disabled={!isDirty || saving}>
                {saving ? "保存中…" : "保存"}
              </Button>
            </div>
          </div>
          {loading ? (
            <p className="p-4 text-sm text-[var(--color-muted-foreground)]">加载中…</p>
          ) : view === "edit" ? (
            <Textarea
              className="agent-config-file-textarea"
              value={currentDraft}
              spellCheck={false}
              onChange={(e) => setDrafts((prev) => ({ ...prev, [selectedId]: e.target.value }))}
            />
          ) : (
            <ScrollArea className="agent-config-file-preview">
              <MarkdownBody content={currentDraft} />
            </ScrollArea>
          )}
        </div>
      </div>
    </div>
  )
}

function WorkspaceHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <header className="workspace-header-bar">
      <div className="min-w-0">
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </header>
  )
}

function AgentDetailPanel({
  agent,
  onEdit,
  onDelete,
}: {
  agent: AgentSummary
  onEdit: () => void
  onDelete: () => void
}) {
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [skillNameById, setSkillNameById] = useState<Record<string, string>>({})
  const [mcpNameById, setMcpNameById] = useState<Record<string, string>>({})

  useEffect(() => {
    Promise.all([listSkillLibrary(), listMcpLibrary(true)])
      .then(([skills, mcps]) => {
        setSkillNameById(Object.fromEntries(skills.map((s) => [s.id, s.name || s.id])))
        setMcpNameById(Object.fromEntries(mcps.map((m) => [m.id, m.name || m.id])))
      })
      .catch(() => {})
  }, [])

  const reloadDetail = useCallback(() => {
    setLoading(true)
    setLoadError("")
    getAgentDetail(agent.id)
      .then((d) => setDetail(d))
      .catch((e: Error) => {
        setDetail(null)
        setLoadError(e.message)
      })
      .finally(() => setLoading(false))
  }, [agent.id])

  useEffect(() => {
    reloadDetail()
  }, [reloadDetail])

  useOnResourceInvalidate("agents", reloadDetail)

  const backend = detail?.backend ?? agent.backend
  const model = detail?.model ?? agent.model
  const workspace = detail?.workspace
  const skills: AgentSkillRef[] = detail?.skills ?? []
  const mcps = detail?.mcp_servers ?? []

  function skillLabel(skill: AgentSkillRef): string {
    return skill.name || skillNameById[skill.skill_id] || skill.skill_id
  }

  function mcpLabel(serverId: string, name?: string): string {
    return name || mcpNameById[serverId] || serverId
  }

  const workspaceFiles = useMemo(() => detail?.files ?? {}, [detail])
  const sharedRules = useMemo(() => detail?.shared_rules ?? {}, [detail])
  const sharedRuleMeta = useMemo(
    () => detail?.shared_rule_files ?? [],
    [detail],
  )

  return (
    <div className="agent-detail-layout">
      <div className="workspace-panel agent-detail-meta">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{agent.name || agent.id}</h2>
            <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{agent.id}</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={onEdit}>
              编辑
            </Button>
            <Button size="sm" variant="outline" onClick={onDelete}>
              删除
            </Button>
          </div>
        </div>
        {agent.description && (
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">{agent.description}</p>
        )}
        <Separator className="my-5" />
        {loading ? (
          <p className="text-sm text-[var(--color-muted-foreground)]">加载配置…</p>
        ) : loadError ? (
          <p className="text-sm text-[var(--color-destructive)]">{loadError}</p>
        ) : (
          <dl className="detail-dl agent-detail-dl">
            <div>
              <dt>后端</dt>
              <dd>{backend || "—"}</dd>
            </div>
            <div>
              <dt>模型</dt>
              <dd>{model || "—"}</dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>工作目录</dt>
              <dd className="font-mono text-xs break-all">{workspace || "—"}</dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>挂载 Skill</dt>
              <dd>
                {skills.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((s) => (
                      <Badge
                        key={s.skill_id}
                        variant={s.available === false ? "outline" : "default"}
                        title={s.skill_id}
                      >
                        {skillLabel(s)}
                        {s.available === false ? "（文件缺失）" : ""}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未挂载（Agent 不可使用任何 Skill）"
                )}
              </dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>挂载 MCP</dt>
              <dd>
                {mcps.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {mcps.map((m) => (
                      <Badge
                        key={m.server_id}
                        variant={m.enabled === false ? "outline" : "default"}
                        title={m.server_id}
                      >
                        {mcpLabel(m.server_id, m.name)}
                        {m.enabled === false ? "（已停用）" : ""}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未挂载（点击「编辑」勾选 MCP；须先在 MCP 页启用服务）"
                )}
              </dd>
            </div>
          </dl>
        )}
      </div>

      <AgentConfigFilesEditor
        agentId={agent.id}
        workspaceFiles={workspaceFiles}
        sharedRules={sharedRules}
        sharedRuleMeta={sharedRuleMeta}
        loading={loading}
      />
    </div>
  )
}

function TaskTypeDetailPanel({
  taskType,
  kindMap,
  onEdit,
  onDelete,
}: {
  taskType: TaskTypeSummary
  kindMap: Record<string, OutcomeKind>
  onEdit: () => void
  onDelete: () => void
}) {
  const meta = kindMap[taskType.outcome_kind]
  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{taskType.display_name || taskType.task_type}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{taskType.task_type}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onEdit}>
            编辑
          </Button>
          <Button size="sm" variant="outline" onClick={onDelete}>
            删除
          </Button>
        </div>
      </div>
      <Separator className="my-5" />
      <dl className="detail-dl">
        <div>
          <dt>产出形态</dt>
          <dd>{taskType.outcome_form_label || meta?.form_label_zh || "—"}</dd>
        </div>
        <div>
          <dt>Gate 算法</dt>
          <dd>{gateLabel(taskType.gate_algorithm || meta?.gate_algorithm)}</dd>
        </div>
        <div>
          <dt>交付要求</dt>
          <dd>{(taskType.gate_checks || []).join(" · ") || "—"}</dd>
        </div>
      </dl>
      {(taskType.sections || []).length > 0 && (
        <>
          <Separator className="my-5" />
          <h3 className="mb-3 text-sm font-semibold">章节结构</h3>
          <ul className="space-y-2 text-sm text-[var(--color-muted-foreground)]">
            {taskType.sections!.map((s) => (
              <li key={s.name}>
                <span className="font-medium text-[var(--color-foreground)]">{s.name}</span>
                {s.description ? ` — ${s.description}` : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function TemplateDetailPanel({
  template,
  onEdit,
  onDelete,
}: {
  template: DeliveryTemplateSummary
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{template.display_name || template.id}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{template.id}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onEdit}>
            编辑 YAML
          </Button>
          <Button size="sm" variant="outline" onClick={onDelete}>
            删除
          </Button>
        </div>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
        {template.description || "（无描述）"}
      </p>
      <Separator className="my-5" />
      <p className="text-sm">绑定任务类型：{(template.task_types || []).join("、 ") || "未限定"}</p>
    </div>
  )
}

function KnowledgeDetailPanel({
  entry,
  onDelete,
}: {
  entry: MemoryEntry
  onDelete: () => void
}) {
  const [detail, setDetail] = useState<MemoryEntry | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!entry.id) {
      setDetail(entry)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    getMemory(entry.id)
      .then((row) => {
        if (!cancelled) setDetail(row)
      })
      .catch(() => {
        if (!cancelled) setDetail(entry)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entry.id, entry])

  const shown = detail ?? entry
  const body = shown.content ?? shown.preview ?? ""

  async function handleDelete() {
    if (!entry.id) return
    if (!window.confirm(`删除知识条目「${shown.title || entry.id}」？\n\n此操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deleteMemory(entry.id)
      toast.success("已删除")
      onDelete()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{shown.title || "（无标题）"}</h2>
          <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">#{shown.id}</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
          disabled={!entry.id || deleting}
          onClick={() => void handleDelete()}
        >
          {deleting ? "删除中…" : "删除"}
        </Button>
      </div>
      <Separator className="my-5" />
      <dl className="detail-dl">
        <div>
          <dt>项目</dt>
          <dd className="font-mono text-xs">{shown.project_id || "—"}</dd>
        </div>
        <div>
          <dt>任务</dt>
          <dd className="font-mono text-xs">{shown.task_id || "—"}</dd>
        </div>
        <div>
          <dt>时间</dt>
          <dd>{shown.created_at || "—"}</dd>
        </div>
        <div>
          <dt>标签</dt>
          <dd>{(shown.tags || []).join("、 ") || "—"}</dd>
        </div>
      </dl>
      <Separator className="my-5" />
      {loading ? (
        <p className="text-sm text-[var(--color-muted-foreground)]">加载正文…</p>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-muted-foreground)]">
          {body || "（无内容）"}
        </p>
      )}
    </div>
  )
}

export function ManageSection() {
  const { tab, itemId } = useParams()
  const navigate = useNavigate()
  const activeTab = ((tab as ManageTab) || "agents") as ManageTab

  const [search, setSearch] = useState("")
  const { data: agents } = useResourceQuery("agents", listAgents, [])
  const { data: templates } = useResourceQuery("delivery-templates", listDeliveryTemplates, [])
  const { data: types } = useResourceQuery("task-types", listTaskTypes, [])
  const [kinds, setKinds] = useState<OutcomeKind[]>([])
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [kbLoading, setKbLoading] = useState(false)

  const [agentEditOpen, setAgentEditOpen] = useState(false)
  const [agentCreateOpen, setAgentCreateOpen] = useState(false)
  const [newAgentId, setNewAgentId] = useState("")
  const [newAgentName, setNewAgentName] = useState("")
  const [newAgentDesc, setNewAgentDesc] = useState("")

  const [typeEditOpen, setTypeEditOpen] = useState(false)
  const [typeEditMode, setTypeEditMode] = useState<"create" | "edit">("create")
  const [typeEditDesc, setTypeEditDesc] = useState("")
  const [typeEditId, setTypeEditId] = useState("")
  const [typeEditName, setTypeEditName] = useState("")
  const [typeEditKind, setTypeEditKind] = useState("artifact")
  const [typeEditSections, setTypeEditSections] = useState("")
  const [typeEditBusy, setTypeEditBusy] = useState(false)

  const [templateFormOpen, setTemplateFormOpen] = useState(false)
  const [templateFormMode, setTemplateFormMode] = useState<"create" | "edit">("create")
  const [templateFormId, setTemplateFormId] = useState("")
  const [templateFormName, setTemplateFormName] = useState("")
  const [templateFormDesc, setTemplateFormDesc] = useState("")
  const [templateFormTaskTypes, setTemplateFormTaskTypes] = useState<string[]>([])
  const [templateFormDefaultFor, setTemplateFormDefaultFor] = useState("")
  const [templateFormSections, setTemplateFormSections] = useState("")
  const [templateFormYaml, setTemplateFormYaml] = useState("")
  const [syncBusy, setSyncBusy] = useState(false)
  const templateImportRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!tab) navigate("/manage/agents", { replace: true })
  }, [tab, navigate])

  useEffect(() => {
    setSearch("")
  }, [activeTab])

  useEffect(() => {
    listOutcomeKinds()
      .then((k) => {
        setKinds(k)
        if (k[0]) setTypeEditKind(k[0].id)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (activeTab !== "knowledge") return
    let cancelled = false
    setKbLoading(true)
    const timer = window.setTimeout(() => {
      listMemory({ limit: 200, text: search.trim() || undefined })
        .then((rows) => {
          if (!cancelled) setEntries(rows)
        })
        .catch(() => {
          if (!cancelled) setEntries([])
        })
        .finally(() => {
          if (!cancelled) setKbLoading(false)
        })
    }, search.trim() ? 250 : 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [activeTab, search])

  const filteredAgents = useMemo(
    () =>
      sortByModifiedDesc(
        agents.filter((a) => matchQuery(search, a.id, a.name, a.backend, a.model, a.role, a.description)),
      ),
    [agents, search],
  )
  const filteredTemplates = useMemo(
    () =>
      sortByModifiedDesc(
        templates.filter((t) =>
          matchQuery(search, t.id, t.display_name, t.description, ...(t.task_types || [])),
        ),
      ),
    [templates, search],
  )
  const filteredTypes = useMemo(
    () =>
      sortByModifiedDesc(
        types.filter((t) =>
          matchQuery(
            search,
            t.task_type,
            t.display_name,
            t.outcome_kind,
            t.outcome_form_label,
            t.gate_algorithm,
            ...(t.gate_checks || []),
          ),
        ),
      ),
    [types, search],
  )
  const filteredEntries = useMemo(
    () =>
      sortByModifiedDesc(
        entries.filter((e) =>
          matchQuery(search, e.title, e.project_id, e.task_id, e.preview, ...(e.tags || [])),
        ),
      ),
    [entries, search],
  )

  const selectedAgent = agents.find((a) => a.id === itemId) ?? null
  const selectedTemplate = templates.find((t) => t.id === itemId) ?? null
  const selectedType = types.find((t) => t.task_type === itemId) ?? null
  const selectedEntry = entries.find((e) => String(e.id) === itemId) ?? null
  const kindMap = Object.fromEntries(kinds.map((k) => [k.id, k]))

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

  async function handleDeleteKnowledge(entry: MemoryEntry) {
    if (!entry.id) return
    setEntries((prev) => prev.filter((e) => e.id !== entry.id))
    navigate("/manage/knowledge")
  }

  async function handleSyncSkills() {
    setSyncBusy(true)
    try {
      const res = await syncAgentSkills()
      const n = res.count ?? 0
      toast.success(n ? `已为 ${n} 个 Agent 同步 Skill` : "Skill 已是最新")
    } catch (e) {
      toast.error("同步失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSyncBusy(false)
    }
  }

  async function handleSyncMcp() {
    setSyncBusy(true)
    try {
      const res = await syncAgentMcp()
      const n = res.cli?.count ?? 0
      toast.success(res.success ? `已同步 ${n} 个 Agent 的 MCP 挂载` : "MCP 同步完成（部分失败见日志）")
    } catch (e) {
      toast.error("MCP 同步失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSyncBusy(false)
    }
  }

  function openTaskTypeEdit(row: TaskTypeSummary | null) {
    const isNew = !row
    setTypeEditMode(isNew ? "create" : "edit")
    setTypeEditDesc(isNew ? "" : row?.display_name || row?.task_type || "")
    setTypeEditId(row?.task_type || "")
    setTypeEditName(row?.display_name || "")
    setTypeEditKind(row?.outcome_kind || kinds[0]?.id || "artifact")
    setTypeEditSections((row?.required_sections || row?.sections?.map((s) => s.name) || []).join(", "))
    setTypeEditOpen(true)
  }

  async function handleSuggestTaskTypeFields() {
    const desc = typeEditDesc.trim()
    if (!desc) {
      toast.error("请先填写任务描述")
      return
    }
    setTypeEditBusy(true)
    try {
      const res = await suggestTaskType(desc)
      if (typeEditMode === "create" && res.task_type) setTypeEditId(res.task_type)
      if (res.display_name) setTypeEditName(res.display_name)
      if (res.outcome_kind) setTypeEditKind(res.outcome_kind)
      if (res.outcome_catalog?.length) setKinds(res.outcome_catalog)
      if (res.required_sections?.length) setTypeEditSections(res.required_sections.join(", "))
      toast.success(res.pattern ? `已推导（${res.pattern}）` : "已推导，可继续编辑")
    } catch (e) {
      toast.error("推导失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setTypeEditBusy(false)
    }
  }

  async function handleSaveTaskType() {
    const taskType = typeEditId.trim()
    if (!taskType) {
      toast.error("类型 ID 不能为空")
      return
    }
    const sections = typeEditSections
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const body = {
      display_name: typeEditName.trim() || taskType,
      outcome_kind: typeEditKind,
      required_sections: sections.length ? sections : ["正文"],
    }
    try {
      if (typeEditMode === "create") {
        await createTaskType({ task_type: taskType, ...body })
      } else {
        await updateTaskType(taskType, body)
      }
      toast.success("任务类型已保存")
      setTypeEditOpen(false)
      navigate(`/manage/task-types/${encodeURIComponent(taskType)}`)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  function openTemplateForm(row: DeliveryTemplateSummary | null) {
    const isNew = !row
    setTemplateFormMode(isNew ? "create" : "edit")
    setTemplateFormId(row?.id || "")
    setTemplateFormName(row?.display_name || "")
    setTemplateFormDesc(row?.description || "")
    setTemplateFormTaskTypes(row?.task_types || [])
    setTemplateFormDefaultFor(row?.default_for || "")
    setTemplateFormSections(
      (row?.sections || [])
        .map((s) => (typeof s === "string" ? s : (s as { name?: string }).name || ""))
        .filter(Boolean)
        .join(", "),
    )
    setTemplateFormYaml("")
    setTemplateFormOpen(true)
    if (!isNew && row?.id) {
      getDeliveryTemplate(row.id)
        .then((detail) => {
          setTemplateFormYaml(detail.yaml || "")
          if (detail.template) {
            setTemplateFormTaskTypes(detail.template.task_types || row.task_types || [])
            setTemplateFormDefaultFor(detail.template.default_for || row.default_for || "")
          }
        })
        .catch(() => {})
    }
  }

  async function handleSaveTemplateForm() {
    const id = templateFormId.trim()
    if (!id) {
      toast.error("模板 ID 不能为空")
      return
    }
    if (!templateFormTaskTypes.length) {
      toast.error("请至少绑定一个任务类型")
      return
    }
    const body = {
      id,
      display_name: templateFormName.trim() || id,
      description: templateFormDesc.trim(),
      task_types: templateFormTaskTypes,
      default_for: templateFormDefaultFor.trim(),
      required_sections: templateFormSections
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
      yaml: templateFormYaml.trim(),
    }
    try {
      await saveDeliveryTemplate(templateFormMode === "edit" ? id : null, body)
      toast.success("模板已保存")
      setTemplateFormOpen(false)
      navigate(`/manage/templates/${encodeURIComponent(id)}`)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleTemplateYamlImport(file: File | null) {
    if (!file) return
    try {
      const text = await file.text()
      await saveDeliveryTemplate(null, { yaml: text })
      toast.success("模板已导入")
      if (templateImportRef.current) templateImportRef.current.value = ""
    } catch (e) {
      toast.error("导入失败", { description: e instanceof Error ? e.message : "" })
    }
  }

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

  async function handleDeleteType(id: string) {
    if (!window.confirm(`删除任务类型「${id}」？`)) return
    try {
      await deleteTaskType(id)
      toast.success("已删除")
      navigate("/manage/task-types")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleDeleteTemplate(id: string) {
    if (!window.confirm(`删除模板「${id}」？`)) return
    try {
      await deleteDeliveryTemplate(id)
      toast.success("已删除")
      navigate("/manage/templates")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  const listAction =
    activeTab === "agents" ? (
      <Button size="sm" onClick={() => setAgentCreateOpen(true)}>
        新建
      </Button>
    ) : activeTab === "task-types" ? (
      <Button size="sm" onClick={() => openTaskTypeEdit(null)}>
        新建
      </Button>
    ) : activeTab === "templates" ? (
      <div className="flex gap-1">
        <Button size="sm" variant="outline" onClick={() => templateImportRef.current?.click()}>
          导入
        </Button>
        <Button size="sm" onClick={() => openTemplateForm(null)}>
          新建
        </Button>
        <input
          ref={templateImportRef}
          type="file"
          accept=".yaml,.yml,.txt"
          className="hidden"
          onChange={(e) => void handleTemplateYamlImport(e.target.files?.[0] ?? null)}
        />
      </div>
    ) : undefined

  const searchPlaceholder =
    activeTab === "agents"
      ? "搜索 Agent…"
      : activeTab === "templates"
        ? "搜索模板…"
        : activeTab === "task-types"
          ? "搜索任务类型…"
          : "搜索标题 / 项目 / 标签…"

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            action={listAction}
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder={searchPlaceholder}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {activeTab === "agents" &&
              filteredAgents.map((a) => (
                <ListItemRow
                  key={a.id}
                  name={a.name || a.id}
                  sub={a.backend || a.role}
                  avatar={a.name || a.id}
                  active={a.id === itemId}
                  onClick={() => navigate(`/manage/agents/${encodeURIComponent(a.id)}`)}
                />
              ))}

            {activeTab === "task-types" &&
              filteredTypes.map((t) => (
                <ListItemRow
                  key={t.task_type}
                  name={t.display_name || t.task_type}
                  sub={t.outcome_form_label || kindMap[t.outcome_kind]?.form_label_zh}
                  avatar={t.display_name || t.task_type}
                  active={t.task_type === itemId}
                  onClick={() => navigate(`/manage/task-types/${encodeURIComponent(t.task_type)}`)}
                />
              ))}

            {activeTab === "templates" &&
              filteredTemplates.map((t) => (
                <ListItemRow
                  key={t.id}
                  name={t.display_name || t.id}
                  sub={(t.task_types || []).join(", ") || "通用"}
                  avatar={t.display_name || t.id}
                  active={t.id === itemId}
                  onClick={() => navigate(`/manage/templates/${encodeURIComponent(t.id)}`)}
                />
              ))}

            {activeTab === "knowledge" &&
              (kbLoading ? (
                <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
              ) : filteredEntries.length ? (
                filteredEntries.map((e) => (
                  <ListItemRow
                    key={e.id}
                    name={e.title || `条目 #${e.id}`}
                    sub={e.project_id || e.preview?.slice(0, 40)}
                    avatar={e.title || "KB"}
                    active={String(e.id) === itemId}
                    onClick={() => navigate(`/manage/knowledge/${e.id}`)}
                  />
                ))
              ) : (
                <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">无匹配条目</p>
              ))}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          {activeTab === "agents" && (
            <>
              <WorkspaceHeader
                title="Agent"
                description="团队成员的后端、模型、Skill/MCP 与 Markdown 配置。"
                action={
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={syncBusy} onClick={() => void handleSyncSkills()}>
                      同步 Skill
                    </Button>
                    <Button size="sm" variant="outline" disabled={syncBusy} onClick={() => void handleSyncMcp()}>
                      同步 MCP
                    </Button>
                  </div>
                }
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
            </>
          )}

          {activeTab === "task-types" && (
            <>
              <WorkspaceHeader title="任务类型" description="产出形态与 Gate 规则。" />
              {kinds.length > 0 && (
                <div className="mb-5 flex flex-wrap gap-2">
                  {kinds.map((k) => (
                    <Badge key={k.id} variant="secondary">
                      {k.form_label_zh}
                    </Badge>
                  ))}
                </div>
              )}
              {selectedType ? (
                <TaskTypeDetailPanel
                  taskType={selectedType}
                  kindMap={kindMap}
                  onEdit={() => openTaskTypeEdit(selectedType)}
                  onDelete={() => handleDeleteType(selectedType.task_type)}
                />
              ) : (
                <WelcomePane title="选择任务类型" description="左侧已列出全部类型，点选一项查看详情。" />
              )}
            </>
          )}

          {activeTab === "templates" && (
            <>
              <WorkspaceHeader title="交付模板" description="结构化交付契约（YAML）。" />
              {selectedTemplate ? (
                <TemplateDetailPanel
                  template={selectedTemplate}
                  onEdit={() => openTemplateForm(selectedTemplate)}
                  onDelete={() => handleDeleteTemplate(selectedTemplate.id)}
                />
              ) : (
                <WelcomePane title="选择模板" description="左侧已列出全部模板，点选一项查看或编辑。" />
              )}
            </>
          )}

          {activeTab === "knowledge" && (
            <>
              <WorkspaceHeader title="知识库" description="项目运行沉淀的长期记忆，可查看全文或删除条目。" />
              {selectedEntry ? (
                <KnowledgeDetailPanel entry={selectedEntry} onDelete={() => void handleDeleteKnowledge(selectedEntry)} />
              ) : (
                <WelcomePane title="选择知识条目" description="左侧已列出全部条目，点选一项查看详情。" />
              )}
            </>
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

      <Dialog open={typeEditOpen} onOpenChange={setTypeEditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{typeEditMode === "create" ? "新建任务类型" : "编辑任务类型"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>任务描述（用于推导）</Label>
              <div className="flex gap-2">
                <Textarea
                  rows={2}
                  value={typeEditDesc}
                  onChange={(e) => setTypeEditDesc(e.target.value)}
                  placeholder="例如：撰写产品调研报告"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  disabled={typeEditBusy}
                  onClick={() => void handleSuggestTaskTypeFields()}
                >
                  推导
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>task_type ID</Label>
              <Input
                value={typeEditId}
                readOnly={typeEditMode === "edit"}
                onChange={(e) => setTypeEditId(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={typeEditName} onChange={(e) => setTypeEditName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>产出形态</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={typeEditKind}
                onChange={(e) => setTypeEditKind(e.target.value)}
              >
                {kinds.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.form_label_zh || k.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>章节（逗号分隔）</Label>
              <Input value={typeEditSections} onChange={(e) => setTypeEditSections(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTypeEditOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSaveTaskType()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={templateFormOpen} onOpenChange={setTemplateFormOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{templateFormMode === "create" ? "新建交付模板" : "编辑交付模板"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>模板 ID</Label>
                <Input
                  value={templateFormId}
                  readOnly={templateFormMode === "edit"}
                  onChange={(e) => setTemplateFormId(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label>显示名称</Label>
                <Input value={templateFormName} onChange={(e) => setTemplateFormName(e.target.value)} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label>描述</Label>
              <Textarea rows={2} value={templateFormDesc} onChange={(e) => setTemplateFormDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>绑定任务类型（多选）</Label>
              <select
                multiple
                className="min-h-[88px] rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                value={templateFormTaskTypes}
                onChange={(e) => {
                  const picked = Array.from(e.target.selectedOptions).map((o) => o.value)
                  setTemplateFormTaskTypes(picked)
                  if (templateFormDefaultFor && !picked.includes(templateFormDefaultFor)) {
                    setTemplateFormDefaultFor("")
                  }
                }}
              >
                {types.map((t) => (
                  <option key={t.task_type} value={t.task_type}>
                    {t.display_name || t.task_type}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>默认任务类型</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={templateFormDefaultFor}
                onChange={(e) => setTemplateFormDefaultFor(e.target.value)}
              >
                <option value="">（不设置）</option>
                {templateFormTaskTypes.map((id) => (
                  <option key={id} value={id}>
                    {types.find((t) => t.task_type === id)?.display_name || id}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>章节（逗号分隔）</Label>
              <Input value={templateFormSections} onChange={(e) => setTemplateFormSections(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>YAML（可选）</Label>
              <Textarea
                rows={8}
                value={templateFormYaml}
                onChange={(e) => setTemplateFormYaml(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTemplateFormOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSaveTemplateForm()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </>
  )
}
