import { Fragment, useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { listAgents, type AgentSummary } from "@/lib/api/agents"
import {
  deleteWorkflow,
  getWorkflow,
  listDeliveryTemplates,
  listTaskTypes,
  saveWorkflow,
  suggestWorkflow,
  type DeliveryTemplateSummary,
  type TaskTypeSummary,
  type WorkflowDetail,
} from "@/lib/api/workflows"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { LoopEditorPanel, serializeLoopSpec } from "./LoopEditorPanel"
import {
  collectAllNodeIds,
  defaultLoopSpec,
  loopsToRecord,
  taskTypesForAgent,
  templatesForTaskType,
  type LoopSpec,
  typeLabelMap,
} from "./loopHelpers"

const WF_TEMPLATE: WorkflowDetail = {
  id: "GitHub项目调研",
  version: "1.0",
  description:
    "对任意 GitHub 开源项目做产品/架构/工程化三视角调研并汇总；具体仓库在发起项目时填写 goal",
  options: {
    review_enabled: false,
    split_enabled: false,
    parallel_enabled: false,
    max_parallel: 3,
  },
  tasks: [
    {
      id: "task-1",
      name: "调研",
      agent: "research",
      task_type: "research",
      dependencies: [],
      description: "【对象】目标 GitHub 仓库（链接见【项目目标】）",
    },
    {
      id: "task-2",
      name: "汇总",
      agent: "main",
      task_type: "strategy",
      dependencies: ["task-1"],
      description: "【输入】只读 task-1 交付物",
    },
  ],
}

type WfTask = NonNullable<WorkflowDetail["tasks"]>[number]

function nextTaskId(tasks: WfTask[]): string {
  const used = new Set(tasks.map((t) => t.id))
  let n = tasks.length + 1
  while (used.has(`task-${n}`)) n += 1
  return `task-${n}`
}

function autoDescription(task: WfTask, isLoop: boolean): string {
  if (task.description?.trim()) return task.description
  const lines: string[] = []
  if (task.name) lines.push(`【任务】${task.name}`)
  if (isLoop) {
    lines.push("【说明】多轮循环；每轮 body 与 until 见 loops 配置")
  } else {
    if (task.agent) lines.push(`【执行】${task.agent}`)
    if (task.task_type) lines.push(`【类型】${task.task_type}`)
  }
  lines.push("【详情】见 workflow 描述与发起项目时的【项目目标】")
  return lines.join("\n")
}

export function WorkflowEditor({
  workflowId,
  onSaved,
  onDeleted,
}: {
  workflowId: string | null
  onSaved: (id: string) => void
  onDeleted: () => void
}) {
  const isNew = !workflowId || workflowId === "new"
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [id, setId] = useState("")
  const [version, setVersion] = useState("1.0")
  const [description, setDescription] = useState("")
  const [options, setOptions] = useState(WF_TEMPLATE.options!)
  const [tasks, setTasks] = useState<WfTask[]>([])
  const [loopSpecs, setLoopSpecs] = useState<Record<string, LoopSpec>>({})
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [taskTypes, setTaskTypes] = useState<TaskTypeSummary[]>([])
  const [templates, setTemplates] = useState<DeliveryTemplateSummary[]>([])

  const typeLabel = useMemo(() => typeLabelMap(taskTypes), [taskTypes])

  const allNodeIds = useMemo(
    () => collectAllNodeIds(tasks, loopSpecs),
    [tasks, loopSpecs],
  )

  const fillForm = useCallback((data: WorkflowDetail) => {
    setId(data.id || "")
    setVersion(data.version || "1.0")
    setDescription(data.description || "")
    setOptions({
      review_enabled: !!data.options?.review_enabled,
      split_enabled: !!data.options?.split_enabled,
      parallel_enabled: !!data.options?.parallel_enabled,
      max_parallel: data.options?.max_parallel ?? 3,
    })
    setTasks(data.tasks?.length ? [...data.tasks] : [])
    setLoopSpecs(loopsToRecord(data.loops))
  }, [])

  useEffect(() => {
    Promise.all([listAgents(), listTaskTypes(), listDeliveryTemplates()])
      .then(([a, tt, tpl]) => {
        setAgents(a)
        setTaskTypes(tt)
        setTemplates(tpl)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (isNew) {
      fillForm(JSON.parse(JSON.stringify(WF_TEMPLATE)) as WorkflowDetail)
      setLoading(false)
      return
    }
    setLoading(true)
    getWorkflow(workflowId!)
      .then(fillForm)
      .catch(() => toast.error("加载工作流失败"))
      .finally(() => setLoading(false))
  }, [workflowId, isNew, fillForm])

  function updateTask(index: number, patch: Partial<WfTask>) {
    setTasks((prev) => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)))
  }

  function setTaskMode(index: number, mode: "normal" | "loop_ref") {
    const task = tasks[index]
    if (!task) return
    const tid = task.id
    if (mode === "loop_ref") {
      setLoopSpecs((specs) => ({
        ...specs,
        [tid]: specs[tid] || defaultLoopSpec(tid),
      }))
      setTasks((prev) =>
        prev.map((t, i) =>
          i === index
            ? {
                ...t,
                loop: tid,
                agent: undefined,
                task_type: undefined,
                template_id: undefined,
              }
            : t,
        ),
      )
      return
    }
    setLoopSpecs((specs) => {
      const next = { ...specs }
      delete next[tid]
      return next
    })
    const { loop: _loop, ...rest } = task as WfTask & { loop?: string }
    setTasks((prev) =>
      prev.map((t, i) =>
        i === index
          ? {
              ...rest,
              agent: rest.agent || agents[0]?.id || "research",
              task_type: rest.task_type || "research",
            }
          : t,
      ),
    )
  }

  function moveTask(index: number, delta: number) {
    setTasks((prev) => {
      const next = index + delta
      if (next < 0 || next >= prev.length) return prev
      const copy = [...prev]
      ;[copy[index], copy[next]] = [copy[next], copy[index]]
      return copy
    })
  }

  function addTask() {
    setTasks((prev) => {
      const prevId = prev.length ? prev[prev.length - 1].id : null
      return [
        ...prev,
        {
          id: nextTaskId(prev),
          name: "",
          agent: agents[0]?.id || "research",
          task_type: "research",
          dependencies: prevId ? [prevId] : [],
          description: "",
        },
      ]
    })
  }

  function removeTask(index: number) {
    const task = tasks[index]
    if (task?.loop) {
      setLoopSpecs((specs) => {
        const next = { ...specs }
        delete next[task.loop!]
        return next
      })
    }
    setTasks((prev) => prev.filter((_, i) => i !== index))
  }

  function buildPayload(): WorkflowDetail {
    const loops: LoopSpec[] = []
    const payloadTasks = tasks.map((t) => {
      const isLoop = !!(t.loop && String(t.loop).trim())
      const base = {
        id: t.id,
        name: (t.name || "").trim(),
        dependencies: t.dependencies || [],
        description: autoDescription(t, isLoop),
      }
      if (isLoop) {
        const loopId = String(t.loop)
        const spec = serializeLoopSpec(loopSpecs[loopId] || defaultLoopSpec(loopId))
        loops.push({ ...spec, id: loopId })
        return { ...base, loop: loopId }
      }
      const item: WfTask = {
        ...base,
        agent: t.agent || "",
        task_type: t.task_type || "research",
      }
      if (t.template_id?.trim()) item.template_id = t.template_id.trim()
      return item
    })

    const payload: WorkflowDetail = {
      id: id.trim(),
      version: version.trim() || "1.0",
      description: description.trim(),
      options: { ...options },
      tasks: payloadTasks,
    }
    if (loops.length) payload.loops = loops
    return payload
  }

  async function handleSave() {
    const data = buildPayload()
    if (!data.id) {
      toast.error("请填写 workflow ID")
      return
    }
    if (!data.tasks?.length) {
      toast.error("至少需要一个任务")
      return
    }
    setSaving(true)
    try {
      const savedId = await saveWorkflow(isNew ? null : workflowId, { workflow: data })
      toast.success("工作流已保存")
      onSaved(savedId || data.id!)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const wid = workflowId && workflowId !== "new" ? workflowId : id.trim()
    if (!wid) return
    if (!window.confirm(`删除工作流「${wid}」？此操作不可恢复。`)) return
    try {
      await deleteWorkflow(wid)
      toast.success("已删除")
      onDeleted()
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  async function handleSuggest() {
    const desc = description.trim()
    if (!desc) {
      toast.error("请先填写描述，再点击自动推导")
      return
    }
    try {
      const result = await suggestWorkflow(desc)
      if (result.workflow) {
        fillForm(result.workflow)
        toast.success(result.pattern_label ? `已推导：${result.pattern_label}` : "任务已自动推导")
      }
    } catch (e) {
      toast.error("推导失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  if (loading) {
    return <div className="p-6 text-[var(--color-muted-foreground)]">加载中…</div>
  }

  return (
    <div className="discord-main-scroll workspace-scroll">
      <header className="workspace-header-bar mb-5">
        <div className="min-w-0">
          <h1>{isNew ? "新建工作流" : id || workflowId}</h1>
          <p>表单编辑任务编排；保存前会自动校验。</p>
        </div>
        <div className="wf-toolbar">
          <Button size="sm" variant="outline" onClick={handleSuggest}>
            自动推导
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
          {!isNew && (
            <Button size="sm" variant="outline" onClick={handleDelete}>
              删除
            </Button>
          )}
        </div>
      </header>

      <div className="wf-editor-form">
        <div className="workspace-panel">
          <div className="wf-meta-grid">
            <div className="grid gap-2">
              <Label htmlFor="wf-id">Workflow ID</Label>
              <Input
                id="wf-id"
                value={id}
                onChange={(e) => setId(e.target.value)}
                disabled={!isNew}
                placeholder="例如：GitHub项目调研"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="wf-version">版本</Label>
              <Input id="wf-version" value={version} onChange={(e) => setVersion(e.target.value)} />
            </div>
          </div>
          <div className="mt-4 grid gap-2">
            <Label htmlFor="wf-desc">描述</Label>
            <Textarea
              id="wf-desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述项目类型与目标，可用于自动推导任务"
            />
          </div>
          <div className="wf-options-row mt-4">
            <label>
              <input
                type="checkbox"
                checked={!!options.review_enabled}
                onChange={(e) => setOptions((o) => ({ ...o, review_enabled: e.target.checked }))}
              />
              启用 Review
            </label>
            <label>
              <input
                type="checkbox"
                checked={!!options.split_enabled}
                onChange={(e) => setOptions((o) => ({ ...o, split_enabled: e.target.checked }))}
              />
              启用拆分
            </label>
            <label>
              <input
                type="checkbox"
                checked={!!options.parallel_enabled}
                onChange={(e) => setOptions((o) => ({ ...o, parallel_enabled: e.target.checked }))}
              />
              允许并行
            </label>
            <label className="inline-flex items-center gap-2">
              最大并行
              <Input
                type="number"
                className="h-8 w-16"
                min={1}
                max={20}
                value={options.max_parallel ?? 3}
                onChange={(e) =>
                  setOptions((o) => ({ ...o, max_parallel: parseInt(e.target.value, 10) || 3 }))
                }
              />
            </label>
          </div>
        </div>

        <div className="workspace-panel workspace-panel-flush">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
            <h2 className="text-sm font-semibold">任务列表</h2>
            <Button size="sm" variant="outline" onClick={addTask}>
              添加任务
            </Button>
          </div>
          <div className="wf-task-table-wrap">
            <table className="wf-task-table">
              <thead>
                <tr>
                  <th className="w-12" />
                  <th>ID</th>
                  <th>名称</th>
                  <th>模式</th>
                  <th>Agent</th>
                  <th>任务类型</th>
                  <th>交付模板</th>
                  <th>依赖</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {tasks.map((task, i) => {
                  const isLoop = !!(task.loop && String(task.loop).trim())
                  const allowedTypes = taskTypesForAgent(task.agent || "", agents)
                  const tplPool = templatesForTaskType(task.task_type || "", templates)
                  return (
                    <Fragment key={task.id}>
                      <tr>
                        <td>
                          <div className="wf-order-btns">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-6 px-1"
                              disabled={i === 0}
                              onClick={() => moveTask(i, -1)}
                            >
                              ↑
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-6 px-1"
                              disabled={i === tasks.length - 1}
                              onClick={() => moveTask(i, 1)}
                            >
                              ↓
                            </Button>
                          </div>
                        </td>
                        <td>
                          <code className="wf-id-badge">{task.id}</code>
                          {isLoop && (
                            <Badge variant="secondary" className="ml-1 text-[10px]">
                              循环
                            </Badge>
                          )}
                        </td>
                        <td>
                          <input
                            className="wf-input-sm"
                            value={task.name || ""}
                            onChange={(e) => updateTask(i, { name: e.target.value })}
                          />
                        </td>
                        <td>
                          <select
                            className="wf-input-sm"
                            value={isLoop ? "loop_ref" : "normal"}
                            onChange={(e) =>
                              setTaskMode(i, e.target.value as "normal" | "loop_ref")
                            }
                          >
                            <option value="normal">普通</option>
                            <option value="loop_ref">循环</option>
                          </select>
                        </td>
                        <td>
                          {isLoop ? (
                            <span className="text-xs text-[var(--color-muted-foreground)]">—</span>
                          ) : (
                            <select
                              className="wf-input-sm"
                              value={task.agent || ""}
                              onChange={(e) => {
                                const agent = e.target.value
                                const types = taskTypesForAgent(agent, agents)
                                updateTask(i, {
                                  agent,
                                  task_type: types.includes(task.task_type || "")
                                    ? task.task_type
                                    : types[0] || task.task_type,
                                })
                              }}
                            >
                              {agents.map((a) => (
                                <option key={a.id} value={a.id}>
                                  {a.name || a.id}
                                </option>
                              ))}
                            </select>
                          )}
                        </td>
                        <td>
                          {isLoop ? (
                            <span className="text-xs text-[var(--color-muted-foreground)]">—</span>
                          ) : (
                            <select
                              className="wf-input-sm"
                              value={task.task_type || ""}
                              onChange={(e) =>
                                updateTask(i, { task_type: e.target.value, template_id: "" })
                              }
                            >
                              {(allowedTypes.length
                                ? allowedTypes
                                : taskTypes.map((t) => t.task_type)
                              ).map((tid) => (
                                <option key={tid} value={tid}>
                                  {typeLabel[tid] || tid}
                                </option>
                              ))}
                            </select>
                          )}
                        </td>
                        <td>
                          {isLoop ? (
                            <span className="text-xs text-[var(--color-muted-foreground)]">—</span>
                          ) : (
                            <select
                              className="wf-input-sm"
                              value={task.template_id || ""}
                              onChange={(e) => updateTask(i, { template_id: e.target.value })}
                            >
                              <option value="">（任务类型默认）</option>
                              {tplPool.map((tpl) => (
                                <option key={tpl.id} value={tpl.id}>
                                  {tpl.display_name || tpl.id}
                                </option>
                              ))}
                            </select>
                          )}
                        </td>
                        <td>
                          <select
                            multiple
                            className="wf-deps-multi wf-input-sm h-[72px]"
                            value={task.dependencies || []}
                            onChange={(e) => {
                              const deps = Array.from(e.target.selectedOptions).map((o) => o.value)
                              updateTask(i, { dependencies: deps })
                            }}
                          >
                            {allNodeIds
                              .filter((n) => n.id !== task.id)
                              .map((n) => (
                                <option key={n.id} value={n.id}>
                                  {n.label}
                                </option>
                              ))}
                          </select>
                        </td>
                        <td>
                          <Button type="button" size="sm" variant="ghost" onClick={() => removeTask(i)}>
                            删
                          </Button>
                        </td>
                      </tr>
                      {isLoop && (
                        <tr className="wf-loop-detail-row">
                          <td colSpan={9}>
                            <LoopEditorPanel
                              loopId={task.loop!}
                              spec={loopSpecs[task.loop!] || defaultLoopSpec(task.loop!)}
                              onChange={(spec) =>
                                setLoopSpecs((prev) => ({ ...prev, [task.loop!]: spec }))
                              }
                              agents={agents}
                              taskTypes={taskTypes}
                              templates={templates}
                              typeLabel={typeLabel}
                              depNodes={allNodeIds}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
