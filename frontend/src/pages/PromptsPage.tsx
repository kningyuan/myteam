import { useEffect, useState, useCallback } from "react"
import {
  listPromptTemplates,
  getPromptTemplate,
  createPromptTemplate,
  updatePromptTemplate,
  deletePromptTemplate,
  listPromptInjections,
  getPromptInjection,
  createPromptInjection,
  updatePromptInjection,
  deletePromptInjection,
  type PromptTemplateEntry,
  type InjectionBlock,
} from "@/lib/api/prompts"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"

const KINDS = ["team_config", "task_plan", "evaluate", "execute", "review", "triage", "_default"] as const

type Tab = "templates" | "injections"

export function PromptsPage() {
  const [tab, setTab] = useState<Tab>("templates")
  const [activeKind, setActiveKind] = useState<string>("")

  // Templates state
  const [templateList, setTemplateList] = useState<Record<string, PromptTemplateEntry>>({})
  const [templateLoading, setTemplateLoading] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplateEntry | null>(null)
  const [editDraft, setEditDraft] = useState("")
  const [saving, setSaving] = useState(false)

  // Injections state
  const [injectionList, setInjectionList] = useState<Record<string, InjectionBlock>>({})
  const [injectionLoading, setInjectionLoading] = useState(false)
  const [selectedInjection, setSelectedInjection] = useState<InjectionBlock | null>(null)
  const [injectionDraft, setInjectionDraft] = useState("")
  const [savingInjection, setSavingInjection] = useState(false)

  // New template form
  const [newId, setNewId] = useState("")
  const [newContent, setNewContent] = useState("")
  const [newKind, setNewKind] = useState<"kind" | "task_type">("kind")

  const loadTemplates = useCallback(async () => {
    setTemplateLoading(true)
    try {
      const data = await listPromptTemplates(activeKind || undefined)
      setTemplateList(data.kinds || {})
    } catch (e) {
      toast.error("加载模板失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setTemplateLoading(false)
    }
  }, [activeKind])

  const loadInjections = useCallback(async () => {
    setInjectionLoading(true)
    try {
      const data = await listPromptInjections()
      setInjectionList(data.injections || {})
    } catch (e) {
      toast.error("加载注入块失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setInjectionLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === "templates") loadTemplates()
    else loadInjections()
  }, [tab, activeKind, loadTemplates, loadInjections])

  // ── Template CRUD ──────────────────────────────────────────────

  function selectTemplate(t: PromptTemplateEntry) {
    setSelectedTemplate(t)
    const contentStr = typeof t.content === "string" ? t.content : JSON.stringify(t.content, null, 2)
    setEditDraft(contentStr)
  }

  async function handleSaveTemplate() {
    if (!selectedTemplate) return
    setSaving(true)
    try {
      await updatePromptTemplate(selectedTemplate.id, { content: editDraft })
      toast.success("模板已保存")
      loadTemplates()
      setSelectedTemplate(null)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteTemplate(id: string) {
    if (!window.confirm(`删除模板「${id}」？`)) return
    try {
      await deletePromptTemplate(id)
      toast.success("已删除")
      setSelectedTemplate(null)
      loadTemplates()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleCreateTemplate() {
    if (!newId.trim()) {
      toast.error("ID 不能为空")
      return
    }
    try {
      await createPromptTemplate({ id: newId, content: newContent, kind: newKind })
      toast.success("模板已创建")
      setNewId("")
      setNewContent("")
      loadTemplates()
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  // ── Injection CRUD ─────────────────────────────────────────────

  function selectInjection(i: InjectionBlock) {
    setSelectedInjection(i)
    setInjectionDraft(JSON.stringify(i.content, null, 2))
  }

  async function handleSaveInjection() {
    if (!selectedInjection) return
    setSavingInjection(true)
    try {
      let parsed: Record<string, unknown>
      try {
        parsed = JSON.parse(injectionDraft)
      } catch {
        toast.error("JSON 格式错误")
        return
      }
      await updatePromptInjection(selectedInjection.id, { content: parsed })
      toast.success("注入块已保存")
      loadInjections()
      setSelectedInjection(null)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSavingInjection(false)
    }
  }

  async function handleDeleteInjection(id: string) {
    if (!window.confirm(`删除注入块「${id}」？`)) return
    try {
      await deletePromptInjection(id)
      toast.success("已删除")
      setSelectedInjection(null)
      loadInjections()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div className="flex h-full gap-0">
      {/* Left sidebar: kind navigation */}
      <div className="flex w-[220px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-sidebar)]">
        <div className="px-3 py-3">
          <h3 className="text-xs font-semibold text-[var(--color-sidebar-fg)]">模板种类</h3>
        </div>
        <ScrollArea className="flex-1">
          <div className="px-2 pb-4">
            <button
              className={`mb-1 w-full rounded-md px-2 py-1.5 text-left text-xs font-medium transition-colors ${
                activeKind === ""
                  ? "bg-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                  : "text-[var(--color-sidebar-fg)] hover:bg-[var(--color-sidebar-accent)]"
              }`}
              onClick={() => setActiveKind("")}
            >
              全部
            </button>
            {KINDS.map((k) => (
              <button
                key={k}
                className={`mb-1 block w-full rounded-md px-2 py-1.5 text-left text-xs font-medium transition-colors ${
                  activeKind === k
                    ? "bg-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                    : "text-[var(--color-sidebar-fg)] hover:bg-[var(--color-sidebar-accent)]"
                }`}
                onClick={() => setActiveKind(k)}
              >
                {k}
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Tab bar */}
        <div className="flex border-b border-[var(--color-border)] px-4">
          <button
            className={`mr-4 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              tab === "templates"
                ? "border-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                : "border-transparent text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            }`}
            onClick={() => setTab("templates")}
          >
            Templates
          </button>
          <button
            className={`border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              tab === "injections"
                ? "border-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                : "border-transparent text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            }`}
            onClick={() => setTab("injections")}
          >
            Injections
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* List column */}
          <div className="flex w-[280px] shrink-0 flex-col border-r border-[var(--color-border)]">
            <div className="flex items-center gap-2 px-3 py-2">
              <Input
                placeholder={tab === "templates" ? "新建模板 ID" : "新建注入 ID"}
                value={tab === "templates" ? newId : ""}
                onChange={(e) => tab === "templates" && setNewId(e.target.value)}
                className="h-7 text-xs"
              />
              {tab === "templates" ? (
                <Button size="sm" onClick={handleCreateTemplate} className="h-7 px-2 text-xs">
                  +
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={async () => {
                    if (!newId.trim()) { toast.error("ID 不能为空"); return }
                    try {
                      await createPromptInjection({ id: newId, content: {} })
                      toast.success("已创建")
                      setNewId("")
                      loadInjections()
                    } catch (e) {
                      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
                    }
                  }}
                  className="h-7 px-2 text-xs"
                >
                  +
                </Button>
              )}
            </div>
            <ScrollArea className="flex-1">
              <div className="px-2 pb-4">
                {tab === "templates" && (
                  templateLoading ? (
                    <p className="px-3 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中...</p>
                  ) : Object.entries(templateList).length === 0 ? (
                    <p className="px-3 py-6 text-center text-xs text-[var(--color-muted-foreground)]">无模板</p>
                  ) : (
                    Object.values(templateList).map((t) => (
                      <button
                        key={t.id}
                        className={`mb-1 w-full rounded-md px-2 py-1.5 text-left transition-colors ${
                          selectedTemplate?.id === t.id
                            ? "bg-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                            : "text-[var(--color-sidebar-fg)] hover:bg-[var(--color-sidebar-accent)]"
                        }`}
                        onClick={() => selectTemplate(t)}
                      >
                        <div className="text-xs font-medium">{t.id}</div>
                        <div className="text-[10px] opacity-60">{t.kind}</div>
                      </button>
                    ))
                  )
                )}
                {tab === "injections" && (
                  injectionLoading ? (
                    <p className="px-3 py-6 text-center text-xs text-[var(--color-muted-foreground)]">加载中...</p>
                  ) : Object.entries(injectionList).length === 0 ? (
                    <p className="px-3 py-6 text-center text-xs text-[var(--color-muted-foreground)]">无注入块</p>
                  ) : (
                    Object.values(injectionList).map((i) => (
                      <button
                        key={i.id}
                        className={`mb-1 w-full rounded-md px-2 py-1.5 text-left transition-colors ${
                          selectedInjection?.id === i.id
                            ? "bg-[var(--color-accent)] text-[var(--color-accent-foreground)]"
                            : "text-[var(--color-sidebar-fg)] hover:bg-[var(--color-sidebar-accent)]"
                        }`}
                        onClick={() => selectInjection(i)}
                      >
                        <div className="text-xs font-medium">{i.id}</div>
                      </button>
                    ))
                  )
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Detail / Editor column */}
          <div className="flex min-w-0 flex-1 flex-col">
            {tab === "templates" && selectedTemplate && (
              <>
                <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
                  <div>
                    <span className="text-sm font-semibold">{selectedTemplate.id}</span>
                    <Badge variant="secondary" className="ml-2 text-[10px]">
                      {selectedTemplate.kind}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteTemplate(selectedTemplate.id)}
                      className="text-xs"
                    >
                      删除
                    </Button>
                    <Button size="sm" onClick={handleSaveTemplate} disabled={saving} className="text-xs">
                      {saving ? "保存中..." : "保存"}
                    </Button>
                  </div>
                </div>
                <div className="flex-1">
                  <textarea
                    className="h-full w-full resize-none border-0 bg-[var(--color-background)] p-4 font-mono text-xs text-[var(--color-foreground)] outline-none"
                    value={editDraft}
                    onChange={(e) => setEditDraft(e.target.value)}
                    spellCheck={false}
                  />
                </div>
              </>
            )}
            {tab === "templates" && !selectedTemplate && (
              <div className="flex flex-1 items-center justify-center text-[var(--color-muted-foreground)]">
                <div className="text-center">
                  <p className="text-sm font-medium">选择模板</p>
                  <p className="mt-1 text-xs">从左侧选择一个模板进行编辑</p>
                </div>
              </div>
            )}

            {tab === "injections" && selectedInjection && (
              <>
                <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
                  <span className="text-sm font-semibold">{selectedInjection.id}</span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteInjection(selectedInjection.id)}
                      className="text-xs"
                    >
                      删除
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleSaveInjection}
                      disabled={savingInjection}
                      className="text-xs"
                    >
                      {savingInjection ? "保存中..." : "保存"}
                    </Button>
                  </div>
                </div>
                <div className="flex-1">
                  <textarea
                    className="h-full w-full resize-none border-0 bg-[var(--color-background)] p-4 font-mono text-xs text-[var(--color-foreground)] outline-none"
                    value={injectionDraft}
                    onChange={(e) => setInjectionDraft(e.target.value)}
                    spellCheck={false}
                  />
                </div>
              </>
            )}
            {tab === "injections" && !selectedInjection && (
              <div className="flex flex-1 items-center justify-center text-[var(--color-muted-foreground)]">
                <div className="text-center">
                  <p className="text-sm font-medium">选择注入块</p>
                  <p className="mt-1 text-xs">从左侧选择一个注入块进行编辑</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
