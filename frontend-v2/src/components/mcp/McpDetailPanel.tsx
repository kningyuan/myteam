import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  deleteMcpServer,
  getMcpServer,
  setMcpEnabled,
  updateMcpServer,
  type McpServerSummary,
} from "@/lib/api/mcp"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"

function parseJsonObject(raw: string, label: string): Record<string, string> | null {
  const t = raw.trim()
  if (!t) return {}
  try {
    const v = JSON.parse(t)
    if (typeof v !== "object" || v === null || Array.isArray(v)) {
      toast.error(`${label} 须为 JSON 对象`)
      return null
    }
    const out: Record<string, string> = {}
    for (const [k, val] of Object.entries(v)) {
      out[String(k)] = String(val)
    }
    return out
  } catch {
    toast.error(`${label} JSON 解析失败`)
    return null
  }
}

export function McpDetailPanel({
  serverId,
  onChanged,
  onDeleted,
}: {
  serverId: string
  onChanged: () => void
  onDeleted: () => void
}) {
  const [item, setItem] = useState<McpServerSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [enabled, setEnabled] = useState(true)
  const [type, setType] = useState<"local" | "remote">("local")
  const [commandText, setCommandText] = useState("")
  const [url, setUrl] = useState("")
  const [envText, setEnvText] = useState("{}")
  const [headersText, setHeadersText] = useState("{}")

  useEffect(() => {
    setLoading(true)
    getMcpServer(serverId)
      .then((s) => {
        setItem(s)
        setName(s.name || s.id)
        setDescription(s.description || "")
        setEnabled(!!s.enabled)
        setType(s.type === "remote" ? "remote" : "local")
        setCommandText((s.command || []).join(" "))
        setUrl(s.url || "")
        setEnvText(JSON.stringify(s.environment || {}, null, 2))
        setHeadersText(JSON.stringify(s.headers || {}, null, 2))
      })
      .catch(() => setItem(null))
      .finally(() => setLoading(false))
  }, [serverId])

  async function handleToggleEnabled(next: boolean) {
    setSaving(true)
    try {
      await setMcpEnabled(serverId, next)
      setEnabled(next)
      toast.success(next ? "MCP 已启用" : "MCP 已停用")
      onChanged()
    } catch (e) {
      toast.error("更新失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleSave() {
    const environment = parseJsonObject(envText, "environment")
    if (environment === null) return
    const headers = parseJsonObject(headersText, "headers")
    if (headers === null) return
    const command = commandText
      .trim()
      .split(/\s+/)
      .filter(Boolean)
    setSaving(true)
    try {
      await updateMcpServer(serverId, {
        name: name.trim(),
        description: description.trim(),
        enabled,
        type,
        command: type === "local" ? command : [],
        url: type === "remote" ? url.trim() : "",
        environment,
        headers,
      })
      toast.success("MCP 已保存")
      onChanged()
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`删除 MCP「${serverId}」？将从所有 Agent 取消挂载。`)) return
    setSaving(true)
    try {
      await deleteMcpServer(serverId)
      toast.success("已删除")
      onDeleted()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-6 text-[var(--color-muted-foreground)]">加载 MCP…</div>
  }
  if (!item) {
    return <div className="p-6 text-[var(--color-destructive)]">MCP 不存在</div>
  }

  return (
    <div className="skill-detail p-6 space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{name || serverId}</h1>
          <p className="text-sm text-[var(--color-muted-foreground)] font-mono">{serverId}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={enabled ? "default" : "secondary"}>{enabled ? "已启用" : "已停用"}</Badge>
          <Button
            size="sm"
            variant="outline"
            disabled={saving}
            onClick={() => void handleToggleEnabled(!enabled)}
          >
            {enabled ? "停用" : "启用"}
          </Button>
        </div>
      </header>

      <p className="hint text-xs">
        全局启用后，Agent 可在「管理 → Agent」中勾选挂载；保存后由对应 CLI 适配器写入 Agent 工作区。
      </p>

      <div className="grid gap-4 max-w-xl">
        <div className="grid gap-2">
          <Label>显示名称</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid gap-2">
          <Label>简介</Label>
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
        </div>
        <div className="grid gap-2">
          <Label>类型</Label>
          <select className="wf-input-sm" value={type} onChange={(e) => setType(e.target.value as "local" | "remote")}>
            <option value="local">local（stdio）</option>
            <option value="remote">remote（HTTP）</option>
          </select>
        </div>
        {type === "local" ? (
          <div className="grid gap-2">
            <Label>command（空格分隔）</Label>
            <Input
              value={commandText}
              onChange={(e) => setCommandText(e.target.value)}
              placeholder="npx -y @package/mcp-server"
            />
          </div>
        ) : (
          <div className="grid gap-2">
            <Label>url</Label>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
          </div>
        )}
        <div className="grid gap-2">
          <Label>environment（JSON）</Label>
          <Textarea value={envText} onChange={(e) => setEnvText(e.target.value)} rows={3} className="font-mono text-xs" />
        </div>
        {type === "remote" ? (
          <div className="grid gap-2">
            <Label>headers（JSON）</Label>
            <Textarea
              value={headersText}
              onChange={(e) => setHeadersText(e.target.value)}
              rows={3}
              className="font-mono text-xs"
            />
          </div>
        ) : null}
      </div>

      <div className="flex gap-2">
        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? "保存中…" : "保存"}
        </Button>
        <Button
          variant="outline"
          className="border-[var(--color-destructive)] text-[var(--color-destructive)] hover:bg-[var(--color-destructive)]/10"
          onClick={() => void handleDelete()}
          disabled={saving}
        >
          删除
        </Button>
      </div>
    </div>
  )
}
