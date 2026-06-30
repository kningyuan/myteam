import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { saveAgentWorkspaceFile, saveSharedRuleFile } from "@/lib/api/agents"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownBody } from "@/components/MarkdownBody"
import { cn } from "@/lib/utils"
import type { ConfigFileKey } from "./types"
import { AGENT_FILE_LABELS, AGENT_WORKSPACE_FILES, configFileId } from "./utils"

export function AgentConfigFilesEditor({
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
          <p className="hint text-xs">团队通用规则改一处全员更新；下方为当前 Agent 人设文件（身份/风格）。团队偏好请改「偏好库」tab。</p>
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
