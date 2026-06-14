import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  createAgent,
  deleteAgent,
  getAgentDetail,
  listAgents,
  saveAgentWorkspaceFile,
  type AgentDetail,
  type AgentSkillRef,
  type AgentSummary,
} from "@/lib/api/agents"
import { listMemory, type MemoryEntry } from "@/lib/api/projects"
import {
  createTaskType,
  deleteDeliveryTemplate,
  deleteTaskType,
  getDeliveryTemplate,
  listDeliveryTemplates,
  listOutcomeKinds,
  listTaskTypes,
  saveDeliveryTemplate,
  type DeliveryTemplateSummary,
  type OutcomeKind,
  type TaskTypeSummary,
} from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { AgentEditDialog } from "@/components/manage/AgentEditDialog"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { matchQuery } from "@/components/manage/ManageSearchBar"
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
  "AGENTS.md",
  "SOUL.md",
  "USER.md",
] as const

type AgentWorkspaceFileName = (typeof AGENT_WORKSPACE_FILES)[number]

const AGENT_FILE_LABELS: Record<AgentWorkspaceFileName, string> = {
  "IDENTITY.md": "身份定义",
  "AGENTS.md": "能力配置",
  "SOUL.md": "人格风格",
  "USER.md": "用户偏好",
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

function AgentWorkspaceFilesEditor({
  agentId,
  files,
  loading,
}: {
  agentId: string
  files: Record<string, string>
  loading: boolean
}) {
  const [selected, setSelected] = useState<AgentWorkspaceFileName>("AGENTS.md")
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, string>>({})
  const [view, setView] = useState<"edit" | "preview">("edit")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const fname of AGENT_WORKSPACE_FILES) {
      next[fname] = files[fname] ?? ""
    }
    setDrafts(next)
    setSaved(next)
    setSelected("AGENTS.md")
    setView("edit")
  }, [agentId, files])

  const currentDraft = drafts[selected] ?? ""
  const isDirty = currentDraft !== (saved[selected] ?? "")

  function selectFile(fname: AgentWorkspaceFileName) {
    if (fname === selected) return
    if (isDirty && !window.confirm(`${selected} 有未保存的修改，确定切换文件？`)) return
    setSelected(fname)
    setView("edit")
  }

  async function handleSave() {
    setSaving(true)
    try {
      await saveAgentWorkspaceFile(agentId, selected, currentDraft)
      setSaved((prev) => ({ ...prev, [selected]: currentDraft }))
      toast.success(`${selected} 已保存`)
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
          <h3 className="text-sm font-semibold">工作区配置文件</h3>
          <p className="hint text-xs">左侧选择文件，右侧编辑 Markdown 内容</p>
        </div>
      </header>
      <div className="agent-config-files">
        <nav className="agent-config-file-list" aria-label="配置文件">
          {AGENT_WORKSPACE_FILES.map((fname) => {
            const dirty = (drafts[fname] ?? "") !== (saved[fname] ?? "")
            const empty = !(saved[fname] ?? "").trim()
            return (
              <button
                key={fname}
                type="button"
                className={cn("agent-config-file-item", selected === fname && "active")}
                onClick={() => selectFile(fname)}
              >
                <span className="agent-config-file-name">{fname}</span>
                <span className="agent-config-file-label">{AGENT_FILE_LABELS[fname]}</span>
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
              <p className="font-mono text-xs font-semibold">{selected}</p>
              <p className="hint text-xs">{AGENT_FILE_LABELS[selected]}</p>
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
              onChange={(e) => setDrafts((prev) => ({ ...prev, [selected]: e.target.value }))}
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

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError("")
    getAgentDetail(agent.id)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setDetail(null)
          setLoadError(e.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [agent.id])

  const backend = detail?.backend ?? agent.backend
  const model = detail?.model ?? agent.model
  const workspace = detail?.workspace
  const taskTypes = detail?.task_types ?? agent.task_types ?? []
  const skills: AgentSkillRef[] =
    detail?.skills ?? taskTypes.map((tt) => ({ task_type: tt, available: undefined }))
  const workspaceFiles = useMemo(() => detail?.files ?? {}, [detail])

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
              <dt>任务类型</dt>
              <dd>
                {taskTypes.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {taskTypes.map((tt) => (
                      <Badge key={tt} variant="secondary">
                        {tt}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未配置"
                )}
              </dd>
            </div>
            <div className="agent-detail-span-full">
              <dt>Skill</dt>
              <dd>
                {skills.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((s) => (
                      <Badge key={s.task_type} variant={s.available === false ? "outline" : "default"}>
                        {s.task_type}
                        {s.available === false ? "（未安装）" : ""}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "未绑定"
                )}
              </dd>
            </div>
          </dl>
        )}
      </div>

      <AgentWorkspaceFilesEditor agentId={agent.id} files={workspaceFiles} loading={loading} />
    </div>
  )
}

function TaskTypeDetailPanel({
  taskType,
  kindMap,
  onDelete,
}: {
  taskType: TaskTypeSummary
  kindMap: Record<string, OutcomeKind>
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
        <Button size="sm" variant="outline" onClick={onDelete}>
          删除
        </Button>
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

function KnowledgeDetailPanel({ entry }: { entry: MemoryEntry }) {
  return (
    <div className="workspace-panel">
      <h2 className="text-lg font-semibold">{entry.title || "（无标题）"}</h2>
      <Separator className="my-5" />
      <dl className="detail-dl">
        <div>
          <dt>项目</dt>
          <dd className="font-mono text-xs">{entry.project_id || "—"}</dd>
        </div>
        <div>
          <dt>任务</dt>
          <dd className="font-mono text-xs">{entry.task_id || "—"}</dd>
        </div>
        <div>
          <dt>时间</dt>
          <dd>{entry.created_at || "—"}</dd>
        </div>
        <div>
          <dt>标签</dt>
          <dd>{(entry.tags || []).join("、 ") || "—"}</dd>
        </div>
      </dl>
      <Separator className="my-5" />
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-muted-foreground)]">
        {entry.preview || "（无内容预览）"}
      </p>
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

  const [typeCreateOpen, setTypeCreateOpen] = useState(false)
  const [newTypeId, setNewTypeId] = useState("")
  const [newTypeName, setNewTypeName] = useState("")
  const [newTypeKind, setNewTypeKind] = useState("artifact")

  const [templateYamlOpen, setTemplateYamlOpen] = useState(false)
  const [templateYaml, setTemplateYaml] = useState("")

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
        if (k[0]) setNewTypeKind(k[0].id)
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
    () => agents.filter((a) => matchQuery(search, a.id, a.name, a.backend, a.model, a.role, a.description)),
    [agents, search],
  )
  const filteredTemplates = useMemo(
    () => templates.filter((t) => matchQuery(search, t.id, t.display_name, t.description, ...(t.task_types || []))),
    [templates, search],
  )
  const filteredTypes = useMemo(
    () =>
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
    [types, search],
  )
  const filteredEntries = useMemo(
    () =>
      entries.filter((e) =>
        matchQuery(search, e.title, e.project_id, e.task_id, e.preview, ...(e.tags || [])),
      ),
    [entries, search],
  )

  const selectedAgent = agents.find((a) => a.id === itemId) ?? null
  const selectedTemplate = templates.find((t) => t.id === itemId) ?? null
  const selectedType = types.find((t) => t.task_type === itemId) ?? null
  const selectedEntry = entries.find((e) => String(e.id) === itemId) ?? null
  const kindMap = Object.fromEntries(kinds.map((k) => [k.id, k]))

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

  async function handleCreateType() {
    if (!newTypeId.trim()) return
    try {
      await createTaskType({
        task_type: newTypeId.trim(),
        display_name: newTypeName.trim() || newTypeId.trim(),
        outcome_kind: newTypeKind,
      })
      toast.success("任务类型已创建")
      setTypeCreateOpen(false)
      navigate(`/manage/task-types/${encodeURIComponent(newTypeId.trim())}`)
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
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

  async function openTemplateYaml(t: DeliveryTemplateSummary) {
    try {
      const detail = await getDeliveryTemplate(t.id)
      setTemplateYaml(detail.yaml || "")
    } catch {
      setTemplateYaml("")
    }
    setTemplateYamlOpen(true)
  }

  async function saveTemplateYaml() {
    if (!selectedTemplate) return
    try {
      await saveDeliveryTemplate(selectedTemplate.id, { yaml: templateYaml, id: selectedTemplate.id })
      toast.success("模板已保存")
      setTemplateYamlOpen(false)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
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
      <Button size="sm" onClick={() => setTypeCreateOpen(true)}>
        新建
      </Button>
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
              <WorkspaceHeader title="Agent" description="团队成员的后端、模型与任务类型绑定。" />
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
                  onEdit={() => openTemplateYaml(selectedTemplate)}
                  onDelete={() => handleDeleteTemplate(selectedTemplate.id)}
                />
              ) : (
                <WelcomePane title="选择模板" description="左侧已列出全部模板，点选一项查看或编辑。" />
              )}
            </>
          )}

          {activeTab === "knowledge" && (
            <>
              <WorkspaceHeader title="知识库" description="团队记忆条目（只读）。" />
              {selectedEntry ? (
                <KnowledgeDetailPanel entry={selectedEntry} />
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

      <Dialog open={typeCreateOpen} onOpenChange={setTypeCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建任务类型</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>task_type ID</Label>
              <Input value={newTypeId} onChange={(e) => setNewTypeId(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={newTypeName} onChange={(e) => setNewTypeName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>产出形态</Label>
              <select
                className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
                value={newTypeKind}
                onChange={(e) => setNewTypeKind(e.target.value)}
              >
                {kinds.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.form_label_zh || k.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTypeCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreateType}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={templateYamlOpen} onOpenChange={setTemplateYamlOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑模板 · {selectedTemplate?.id}</DialogTitle>
          </DialogHeader>
          <Textarea
            rows={16}
            value={templateYaml}
            onChange={(e) => setTemplateYaml(e.target.value)}
            className="font-mono text-xs"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setTemplateYamlOpen(false)}>
              取消
            </Button>
            <Button onClick={saveTemplateYaml}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
