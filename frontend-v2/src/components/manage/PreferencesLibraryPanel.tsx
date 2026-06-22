import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  getPreferencesLibrary,
  savePreferencesLibrary,
  syncPreferencesToAgents,
} from "@/lib/api/preferences"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { MarkdownBody } from "@/components/MarkdownBody"
import { Separator } from "@/components/ui/separator"

export function PreferencesLibraryPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [draft, setDraft] = useState("")
  const [saved, setSaved] = useState("")
  const [view, setView] = useState<"edit" | "preview">("edit")
  const [legacyWarning, setLegacyWarning] = useState<string | null>(null)
  const [path, setPath] = useState("")

  useEffect(() => {
    setLoading(true)
    getPreferencesLibrary()
      .then((res) => {
        setDraft(res.content || "")
        setSaved(res.content || "")
        setLegacyWarning(res.legacy_warning || null)
        setPath(res.path || "")
      })
      .catch((e) => toast.error("加载偏好库失败", { description: e instanceof Error ? e.message : "" }))
      .finally(() => setLoading(false))
  }, [])

  const isDirty = draft !== saved

  async function handleSave() {
    setSaving(true)
    try {
      const res = await savePreferencesLibrary(draft)
      setSaved(draft)
      toast.success("团队偏好已保存", {
        description: res.synced_agents?.length
          ? `已同步 ${res.synced_agents.length} 个 Agent workspace`
          : undefined,
      })
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    try {
      const res = await syncPreferencesToAgents()
      toast.success(`已同步 ${res.synced_agents?.length ?? 0} 个 Agent`)
    } catch (e) {
      toast.error("同步失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return <p className="p-6 text-sm text-[var(--color-muted-foreground)]">加载团队偏好库…</p>
  }

  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">团队偏好库</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            全员 Agent 在 execute / 群聊 harness 中注入同一份规则（config/USER.md），不按 Agent 分叉。
          </p>
          {path ? <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{path}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => setView(view === "edit" ? "preview" : "edit")}>
            {view === "edit" ? "预览" : "编辑"}
          </Button>
          <Button size="sm" variant="outline" disabled={syncing} onClick={() => void handleSync()}>
            {syncing ? "同步中…" : "同步到全部 Agent"}
          </Button>
          <Button size="sm" disabled={!isDirty || saving} onClick={() => void handleSave()}>
            {saving ? "保存中…" : "保存"}
          </Button>
        </div>
      </div>

      {legacyWarning ? (
        <p className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
          {legacyWarning}
        </p>
      ) : null}

      <Separator className="my-5" />

      {view === "edit" ? (
        <div className="grid gap-2">
          <Label>偏好规则（Markdown）</Label>
          <Textarea
            rows={22}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="font-mono text-xs leading-relaxed"
            placeholder="# 团队偏好&#10;&#10;- 交付物须含可验证证据&#10;- 调研报告须列扫描路径≥5"
          />
        </div>
      ) : (
        <MarkdownBody content={draft || "（空）"} />
      )}
    </div>
  )
}
