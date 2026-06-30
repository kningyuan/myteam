import { Link } from "react-router-dom"
import { ChevronDown, ChevronUp } from "lucide-react"
import { toast } from "sonner"
import type { AgentSummary } from "@/lib/api/agents"
import {
  addGroupMember,
  removeGroupMember,
  updateGroupRoundtableSettings,
  type GroupSummary,
} from "@/lib/api/groups"
import type { GroupDiscussionSettings } from "@/lib/chat/groupDiscussionSettings"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export function GroupMembersDialog({
  open,
  onOpenChange,
  groupId,
  group,
  members,
  allAgents,
  gdSettings,
  nameFor,
  onGroupChange,
  onReload,
  onMoveMember,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupId: string
  group: GroupSummary | null
  members: string[]
  allAgents: AgentSummary[]
  gdSettings: GroupDiscussionSettings
  nameFor: (id: string) => string
  onGroupChange: (group: GroupSummary) => void
  onReload: () => void
  onMoveMember: (agentId: string, direction: -1 | 1) => Promise<void>
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>群成员与圆桌设置</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3 border-b border-[var(--color-border)] pb-4">
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)]/30 px-3 py-2 text-xs text-[var(--color-muted-foreground)]">
            <div className="mb-1 font-medium text-[var(--color-foreground)]">全局群配置</div>
            <div>默认 {gdSettings.defaultMaxRounds} 轮 · 上限 {gdSettings.maxRoundsCap} 轮 · 单轮超时 {gdSettings.turnTimeoutSec}s</div>
            <div>参与率 ≥ {Math.round(gdSettings.quorumRatio * 100)}% · 终止命令：{gdSettings.terminateCommands.join("、")}</div>
            <Link to="/settings/group" className="mt-1 inline-block text-[var(--color-brand)] hover:underline">
              在设置 → 群配置 中修改
            </Link>
          </div>
          <Label>圆桌主持人</Label>
          <select
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm"
            value={group?.roundtable_facilitator || "main"}
            onChange={async (e) => {
              try {
                const updated = await updateGroupRoundtableSettings(groupId, {
                  roundtable_facilitator: e.target.value,
                })
                onGroupChange(updated)
                toast.success("主持人已更新")
              } catch (err) {
                toast.error("更新失败", {
                  description: err instanceof Error ? err.message : "",
                })
              }
            }}
          >
            {members
              .filter((m) => m !== "user")
              .map((m) => (
                <option key={m} value={m}>
                  {nameFor(m)}
                </option>
              ))}
          </select>
          <Label>本群最大讨论轮数（1–{gdSettings.maxRoundsCap}）</Label>
          <Input
            type="number"
            min={1}
            max={gdSettings.maxRoundsCap}
            value={group?.roundtable_max_rounds ?? gdSettings.defaultMaxRounds}
            onChange={async (e) => {
              const n = Number(e.target.value)
              if (!Number.isFinite(n) || n < 1 || n > gdSettings.maxRoundsCap) return
              try {
                const updated = await updateGroupRoundtableSettings(groupId, {
                  roundtable_max_rounds: n,
                })
                onGroupChange(updated)
              } catch (err) {
                toast.error("更新失败", {
                  description: err instanceof Error ? err.message : "",
                })
              }
            }}
          />
          <p className="text-xs text-[var(--color-muted-foreground)]">
            未保存单群轮数时使用全局默认 {gdSettings.defaultMaxRounds} 轮。每轮含主持汇总；若有分歧会插入对齐轮。
          </p>
        </div>
        <div className="space-y-1 pb-2">
          <Label>成员与发言顺序</Label>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            从上到下为圆桌立论/对齐轮发言顺序（主持人除外）。
          </p>
        </div>
        <div className="max-h-64 space-y-2 overflow-y-auto py-1">
          {members.map((m, index) => (
            <div key={m} className="flex items-center justify-between gap-2 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <span className="w-5 shrink-0 text-xs text-[var(--color-muted-foreground)]">
                  {m === "user" ? "—" : index + 1}
                </span>
                <span className="truncate">{nameFor(m)}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {m !== "user" && (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 px-0"
                      disabled={index === 0 || members[index - 1] === "user"}
                      aria-label={`${nameFor(m)} 上移`}
                      onClick={() => void onMoveMember(m, -1)}
                    >
                      <ChevronUp className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 px-0"
                      disabled={index >= members.length - 1}
                      aria-label={`${nameFor(m)} 下移`}
                      onClick={() => void onMoveMember(m, 1)}
                    >
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          await removeGroupMember(groupId, m)
                          onReload()
                          toast.success(`已移除 ${nameFor(m)}`)
                        } catch (e) {
                          toast.error("移除失败", { description: e instanceof Error ? e.message : "" })
                        }
                      }}
                    >
                      移除
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="grid gap-2 border-t border-[var(--color-border)] pt-3">
          <Label>添加成员</Label>
          <div className="flex flex-wrap gap-2">
            {allAgents
              .filter((a) => !members.includes(a.id))
              .map((a) => (
                <Button
                  key={a.id}
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    try {
                      await addGroupMember(groupId, a.id)
                      onReload()
                      toast.success(`已添加 ${a.name || a.id}`)
                    } catch (e) {
                      toast.error("添加失败", { description: e instanceof Error ? e.message : "" })
                    }
                  }}
                >
                  + {a.name || a.id}
                </Button>
              ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
