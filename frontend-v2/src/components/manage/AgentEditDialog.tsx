import { useEffect, useState } from "react"
import { toast } from "sonner"
import { updateAgentManage, type AgentSummary } from "@/lib/api/agents"
import { listBackends, listBackendModels, type BackendModel, type BackendSummary } from "@/lib/api/config"
import { listTaskTypes, type TaskTypeSummary } from "@/lib/api/workflows"
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
  const [taskTypes, setTaskTypes] = useState<string[]>([])
  const [allTaskTypes, setAllTaskTypes] = useState<TaskTypeSummary[]>([])
  const [backends, setBackends] = useState<BackendSummary[]>([])
  const [models, setModels] = useState<BackendModel[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!agent) return
    setName(agent.name || agent.id)
    setBackend(agent.backend || "opencode")
    setModel(agent.model || "")
    listTaskTypes().then(setAllTaskTypes).catch(() => setAllTaskTypes([]))
    listBackends().then(setBackends).catch(() => setBackends([]))
  }, [agent])

  useEffect(() => {
    if (!backend) return
    listBackendModels(backend)
      .then((ms) => {
        setModels(ms)
        if (model && !ms.some((m) => m.id === model) && ms[0]) setModel(ms[0].id)
      })
      .catch(() => setModels([]))
  }, [backend])

  async function handleSave() {
    if (!agent || !name.trim()) return
    setBusy(true)
    try {
      await updateAgentManage(agent.id, {
        name: name.trim(),
        backend,
        model,
        workspace: workspace.trim(),
        task_types: taskTypes,
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
      <DialogContent>
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
            <Label>绑定任务类型</Label>
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
              {allTaskTypes.map((t) => (
                <label key={t.task_type} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={taskTypes.includes(t.task_type)}
                    onChange={(e) => {
                      setTaskTypes((prev) =>
                        e.target.checked
                          ? [...prev, t.task_type]
                          : prev.filter((x) => x !== t.task_type),
                      )
                    }}
                  />
                  {t.display_name || t.task_type}
                </label>
              ))}
            </div>
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
