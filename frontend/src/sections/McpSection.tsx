import { useCallback, useMemo, useState } from "react"
import { NavLink, useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { createMcpServer, deleteMcpServer, listMcpLibrary, type McpServerSummary } from "@/lib/api/mcp"
import { useResourceQuery, useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { McpDetailPanel } from "@/components/mcp/McpDetailPanel"
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

function McpHome({
  items,
  loading,
  error,
  onSelect,
}: {
  items: McpServerSummary[]
  loading: boolean
  error: string
  onSelect: (id: string) => void
}) {
  if (loading) return <div className="p-6 text-[var(--color-muted-foreground)]">加载 MCP…</div>
  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-[var(--color-destructive)]">MCP 加载失败：{error}</p>
      </div>
    )
  }
  if (!items.length) {
    return (
      <WelcomePane
        title="暂无 MCP"
        description="点击左侧「新建 MCP」添加 Server；启用后可在 Agent 配置中勾选挂载。"
      />
    )
  }

  return (
    <div className="skill-home">
      <header className="skill-home-head">
        <div>
          <h1 className="text-lg font-semibold">MCP 服务</h1>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            共 {items.length} 个 · 全局启用/停用；Agent 按勾选挂载并由 CLI 适配器同步
          </p>
        </div>
      </header>
      <div className="skill-home-grid">
        {items.map((s) => (
          <button key={s.id} type="button" className="skill-home-card" onClick={() => onSelect(s.id)}>
            <div className="skill-home-card-top">
              <span className="skill-home-card-name">{s.name || s.id}</span>
              <span
                className={
                  s.enabled
                    ? "skill-home-card-tag skill-home-card-tag--ok"
                    : "skill-home-card-tag"
                }
              >
                {s.enabled ? "已启用" : "已停用"}
              </span>
            </div>
            <span className="skill-home-card-id">{s.id}</span>
            <p className="skill-home-card-desc">{s.description?.trim() || s.type || "MCP Server"}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

export function McpSection() {
  const { serverId } = useParams()
  const navigate = useNavigate()
  const {
    data: library,
    loading: loadingLibrary,
    error: libraryError,
    reload: reloadLibrary,
  } = useResourceQuery("mcp-library", () => listMcpLibrary(true), [])
  const [createOpen, setCreateOpen] = useState(false)
  const [newId, setNewId] = useState("")
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)

  useOnResourceInvalidate("mcp-library", reloadLibrary)

  const sorted = useMemo(() => {
    return [...library].sort((a, b) => a.id.localeCompare(b.id))
  }, [library])

  const handleCreated = useCallback(async () => {
    const id = newId.trim()
    if (!id) {
      toast.error("请填写 MCP id")
      return
    }
    setCreating(true)
    try {
      await createMcpServer({
        id,
        name: newName.trim() || id,
        enabled: false,
        type: "local",
        command: ["npx", "-y", "example-mcp"],
      })
      toast.success("MCP 已创建")
      setCreateOpen(false)
      setNewId("")
      setNewName("")
      reloadLibrary()
      navigate(`/mcp/${encodeURIComponent(id)}`)
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setCreating(false)
    }
  }, [newId, newName, navigate, reloadLibrary])

  const handleDeleteMcp = useCallback(async (id: string, name?: string) => {
    if (!confirm(`确定要删除 MCP「${name || id}」吗？`)) return
    try {
      await deleteMcpServer(id)
      toast.success("MCP 已删除")
      if (serverId === id) navigate("/mcp")
      reloadLibrary()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }, [serverId, navigate, reloadLibrary])

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="MCP"
            action={
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                新建 MCP
              </Button>
            }
          >
            <div className="skill-list-toolbar">
              <NavLink
                to="/mcp"
                end
                className={({ isActive }) =>
                  `skill-list-overview-btn${isActive && !serverId ? " active" : ""}`
                }
              >
                全部 MCP
              </NavLink>
            </div>
            {loadingLibrary ? (
              <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
            ) : sorted.length ? (
              sorted.map((s) => (
                <ListItemRow
                  key={s.id}
                  active={serverId === s.id}
                  name={s.name || s.id}
                  sub={s.enabled ? "已启用" : "已停用"}
                  avatar="MC"
                  onClick={() => navigate(`/mcp/${encodeURIComponent(s.id)}`)}
                  onDelete={() => handleDeleteMcp(s.id, s.name)}
                />
              ))
            ) : (
              <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">暂无 MCP</p>
            )}
          </ListColumn>
        }
      >
        {serverId ? (
          <McpDetailPanel
            serverId={serverId}
            onChanged={reloadLibrary}
            onDeleted={() => {
              reloadLibrary()
              navigate("/mcp")
            }}
          />
        ) : (
          <McpHome
            items={sorted}
            loading={loadingLibrary}
            error={libraryError || ""}
            onSelect={(id) => navigate(`/mcp/${encodeURIComponent(id)}`)}
          />
        )}
      </DiscordShell>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建 MCP Server</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>ID（英文小写）</Label>
              <Input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="browser" />
            </div>
            <div className="grid gap-2">
              <Label>显示名称</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="浏览器 MCP" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleCreated()} disabled={creating}>
              {creating ? "创建中…" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
