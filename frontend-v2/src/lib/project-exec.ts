import type { ProjectEvent, ProjectOverview } from "@/lib/api/projects"

export type ExecTask = NonNullable<ProjectOverview["tasks"]>[number]

export function taskHasInteractions(events: ProjectEvent[], taskId: string): boolean {
  return events.some((e) => e.category === "interaction" && e.task_id === taskId)
}

/** 执行过程一级折叠：去掉已拆分取消的父任务、子任务（嵌套展示）、无交互的 loop 锚点 */
export function listExecRootTasks(tasks: ExecTask[], events: ProjectEvent[]): ExecTask[] {
  const roots = tasks.filter((t) => {
    if (t.status === "cancelled") return false
    if (t.split_parent) return false
    if (t.loop && !taskHasInteractions(events, t.id)) {
      const others = tasks.some((o) => o.id !== t.id && taskHasInteractions(events, o.id))
      if (others) return false
    }
    return true
  })
  return sortTasksByDag(roots, tasks)
}

export function listExecChildTasks(parent: ExecTask, tasks: ExecTask[]): ExecTask[] {
  const children = parent.split_children ?? []
  if (!children.length) return []
  const byId = new Map(tasks.map((t) => [t.id, t]))
  return children.map((id) => byId.get(id)).filter((t): t is ExecTask => !!t)
}

export function groupInteractionsByTask(events: ProjectEvent[]): Record<string, ProjectEvent[]> {
  const out: Record<string, ProjectEvent[]> = {}
  for (const e of events) {
    if (e.category !== "interaction" || !e.task_id || !e.interaction_id) continue
    ;(out[e.task_id] ??= []).push(e)
  }
  for (const list of Object.values(out)) {
    list.sort((a, b) => (a.ts || "").localeCompare(b.ts || ""))
  }
  return out
}

export function taskSplitEventsFor(
  events: ProjectEvent[],
  taskId: string,
): ProjectEvent[] {
  return events.filter((e) => {
    if (e.category !== "event" || e.kind !== "task_split") return false
    const parent = String((e.payload?.parent as string) || e.task_id || "")
    return parent === taskId
  })
}

export function taskActivityEvents(
  events: ProjectEvent[],
  taskId: string,
): ProjectEvent[] {
  const loopKinds = new Set([
    "loop_round_done",
    "loop_round_assess",
    "loop_transition",
    "branch_selected",
    "loop_finished",
    "parallel_wave",
    "blocked",
  ])
  return events.filter((e) => {
    if (e.category !== "event") return false
    if (e.kind === "task_split") return false
    if (!loopKinds.has(e.kind || "")) return false
    if (e.task_id === taskId) return true
    const tasks = e.payload?.tasks
    if (Array.isArray(tasks) && tasks.includes(taskId)) return true
    return false
  })
}

function sortTasksByDag(roots: ExecTask[], all: ExecTask[]): ExecTask[] {
  const byId = new Map(all.map((t) => [t.id, t]))
  const level = new Map<string, number>()
  const visit = (id: string, stack: Set<string>): number => {
    if (level.has(id)) return level.get(id)!
    if (stack.has(id)) return 0
    stack.add(id)
    const t = byId.get(id)
    const deps = t?.dependencies ?? []
    const lv = deps.length
      ? Math.max(0, ...deps.map((d) => visit(d, stack))) + 1
      : 0
    level.set(id, lv)
    stack.delete(id)
    return lv
  }
  for (const t of roots) visit(t.id, new Set())
  return [...roots].sort((a, b) => {
    const la = level.get(a.id) ?? 0
    const lb = level.get(b.id) ?? 0
    if (la !== lb) return la - lb
    return a.id.localeCompare(b.id)
  })
}
