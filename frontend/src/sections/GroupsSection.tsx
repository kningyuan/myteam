import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { listAgents } from "@/lib/api/agents"
import {
  createGroup,
  listGroups,
  restoreGroup,
  searchGroups,
  type GroupSummary,
} from "@/lib/api/groups"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { formatRelativeTime } from "@/lib/thinking"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { GroupChatPanel } from "./groups/GroupChatPanel"

export function GroupsSection() {
  const { groupId } = useParams()
  const navigate = useNavigate()
  const { data: groups } = useResourceQuery("groups", listGroups, [])
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const { data: agents } = useResourceQuery("agents", listAgents, [])
  const [selectedMembers, setSelectedMembers] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [searchHits, setSearchHits] = useState<GroupSummary[]>([])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setSearchHits([])
      return
    }
    const t = setTimeout(() => {
      searchGroups(q, true)
        .then(setSearchHits)
        .catch(() => setSearchHits([]))
    }, 200)
    return () => clearTimeout(t)
  }, [query])

  async function handleCreateGroup() {
    if (!newName.trim()) return
    try {
      const res = await createGroup({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        members: selectedMembers,
      })
      toast.success("群组已创建")
      setShowNew(false)
      setNewName("")
      setNewDesc("")
      setSelectedMembers([])
      navigate(`/groups/${encodeURIComponent(res.group_id)}`)
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  const active = useMemo(
    () => sortByModifiedDesc(groups.filter((g) => g.status !== "dissolved")),
    [groups],
  )
  const listSource = useMemo(
    () => sortByModifiedDesc(query.trim() ? searchHits : active),
    [query, searchHits, active],
  )

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="群组"
            action={
              <Button size="sm" onClick={() => setShowNew(true)}>
                新建
              </Button>
            }
            search={
              <input
                placeholder="搜索群组（含已解散）…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            }
          >
            {listSource.map((g) => (
              <ListItemRow
                key={g.id}
                name={g.name}
                sub={
                  g.status === "dissolved"
                    ? "已解散 · 点击恢复"
                    : g.last_message
                      ? `${g.last_message.slice(0, 48)}${g.last_message.length > 48 ? "…" : ""}${
                          g.last_message_at ? ` · ${formatRelativeTime(g.last_message_at)}` : ""
                        }`
                      : g.project_id
                        ? `项目 ${g.project_id}`
                        : `${g.members?.length ?? 0} 名成员`
                }
                avatar={g.name}
                active={g.id === groupId}
                onClick={async () => {
                  if (g.status === "dissolved") {
                    try {
                      await restoreGroup(g.id)
                      toast.success("群组已恢复")
                    } catch (e) {
                      toast.error("恢复失败", { description: e instanceof Error ? e.message : "" })
                      return
                    }
                  }
                  navigate(`/groups/${encodeURIComponent(g.id)}`)
                }}
              />
            ))}
          </ListColumn>
        }
      >
        {groupId ? (
          <GroupChatPanel groupId={groupId} />
        ) : (
          <WelcomePane
            title="选择一个群组"
            description="项目协作群与独立讨论组。支持 @Agent、成员管理、清空消息与解散/恢复。"
          />
        )}
      </DiscordShell>
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建群组</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>群名称</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>描述（可选）</Label>
              <Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>初始成员</Label>
              <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                {agents.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedMembers.includes(a.id)}
                      onChange={(e) =>
                        setSelectedMembers((prev) =>
                          e.target.checked ? [...prev, a.id] : prev.filter((x) => x !== a.id),
                        )
                      }
                    />
                    <span>{a.name || a.id}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>
              取消
            </Button>
            <Button onClick={handleCreateGroup}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
