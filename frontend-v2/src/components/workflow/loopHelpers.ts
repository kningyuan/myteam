import type { AgentSummary } from "@/lib/api/agents"
import type { DeliveryTemplateSummary, TaskTypeSummary } from "@/lib/api/workflows"

export type LoopBodyTask = {
  id: string
  name?: string
  agent?: string
  task_type?: string
  template_id?: string
  dependencies?: string[]
  description?: string
}

export type LoopUntilCond = {
  type: string
  task?: string
  marker?: string
  status?: string
}

export type LoopAssessInput = {
  kind: string
  phase?: string
  table?: string
  optional?: boolean
}

export type LoopAssessSpec = {
  ref: string
  inputs?: LoopAssessInput[]
}

export type LoopTransitionRule = {
  when: string
  task?: string
  marker?: string
  action?: string
  outcome?: string
  next_body?: string
}

export type LoopSpec = {
  id: string
  description?: string
  max_rounds?: number
  min_rounds?: number
  default_body?: string
  on_pass?: string
  on_exhaust?: string
  body?: LoopBodyTask[]
  until?: LoopUntilCond[]
  bodies?: Record<string, LoopBodyTask[]>
  assess?: LoopAssessSpec
  transition?: LoopTransitionRule[]
  fallback_until?: LoopUntilCond[]
}

export const WF_UNTIL_TYPES: {
  id: string
  label: string
  hint: string
  fields: string[]
}[] = [
  {
    id: "gate_passed",
    label: "Gate 通过",
    hint: "指定 step 经任务类型模板门禁且 status=completed",
    fields: ["task"],
  },
  {
    id: "review_passed",
    label: "Peer Review 通过",
    hint: "启用 review_enabled 时读 review_done.passed",
    fields: ["task"],
  },
  {
    id: "task_status",
    label: "任务状态",
    hint: "指定 step 达到某终态",
    fields: ["task", "status"],
  },
  {
    id: "deliverable_marker",
    label: "交付物含文本（高级）",
    hint: "字符串匹配，非推荐",
    fields: ["task", "marker"],
  },
]

export const WF_LOOP_OUTCOMES = [
  { id: "complete", label: "completed" },
  { id: "completed", label: "completed（别名）" },
  { id: "needs_review", label: "needs_review" },
  { id: "failed", label: "failed" },
]

export const WF_TASK_STATUSES = ["completed", "needs_review", "failed", "blocked"]

const WF_LOOP_TEMPLATE: Omit<LoopSpec, "id"> = {
  max_rounds: 5,
  on_pass: "complete",
  on_exhaust: "needs_review",
  until: [{ type: "gate_passed", task: "step-2" }],
  body: [
    {
      id: "step-1",
      name: "执行",
      agent: "research",
      task_type: "research",
      dependencies: [],
      description: "",
    },
    {
      id: "step-2",
      name: "审计",
      agent: "main",
      task_type: "strategy",
      dependencies: ["step-1"],
      description: "",
    },
  ],
}

export function nextSeqId(prefix: string, used: string[]): string {
  const set = new Set(used.map((s) => s.trim()).filter(Boolean))
  let n = 1
  while (set.has(`${prefix}-${n}`)) n += 1
  return `${prefix}-${n}`
}

export function nextBodyStepId(body: LoopBodyTask[]): string {
  return nextSeqId("step", body.map((t) => t.id))
}

function lastBodyStepId(body: LoopBodyTask[]): string {
  const rows = body || []
  return rows[rows.length - 1]?.id || "step-2"
}

function defaultUntilCond(body: LoopBodyTask[]): LoopUntilCond {
  return { type: "gate_passed", task: lastBodyStepId(body) }
}

export function normalizeLoopUntil(lp: Pick<LoopSpec, "body" | "until">): LoopUntilCond[] {
  const body = lp.body || []
  const last = lastBodyStepId(body)
  let until = (lp.until || []).map((u) => {
    if (!u || typeof u !== "object") return u
    if (u.type === "deliverable_marker") {
      const marker = String(u.marker || "")
      if (!marker || /REVIEW:\s*PASS/i.test(marker)) {
        return { type: "gate_passed", task: u.task || last }
      }
    }
    return u
  })
  if (!until.length) until = [defaultUntilCond(body)]
  return until
}

export function defaultLoopSpec(taskId: string): LoopSpec {
  const spec = JSON.parse(JSON.stringify(WF_LOOP_TEMPLATE)) as Omit<LoopSpec, "id">
  return { ...spec, id: taskId, until: normalizeLoopUntil(spec) }
}

export function loopsToRecord(loops: Record<string, unknown>[] | undefined): Record<string, LoopSpec> {
  const out: Record<string, LoopSpec> = {}
  for (const raw of loops || []) {
    const id = String(raw.id || "").trim()
    if (!id) continue
    const body = (raw.body as LoopBodyTask[]) || []
    out[id] = {
      id,
      description: raw.description as string | undefined,
      max_rounds: (raw.max_rounds as number) ?? 5,
      min_rounds: raw.min_rounds as number | undefined,
      default_body: raw.default_body as string | undefined,
      on_pass: (raw.on_pass as string) || "complete",
      on_exhaust: (raw.on_exhaust as string) || "needs_review",
      body,
      until: normalizeLoopUntil({ body, until: raw.until as LoopUntilCond[] }),
      bodies: raw.bodies as Record<string, LoopBodyTask[]> | undefined,
      assess: raw.assess as LoopAssessSpec | undefined,
      transition: raw.transition as LoopTransitionRule[] | undefined,
      fallback_until: raw.fallback_until as LoopUntilCond[] | undefined,
    }
  }
  return out
}

export function autoBodyDescription(task: LoopBodyTask): string {
  if (task.description?.trim()) return task.description
  const lines: string[] = []
  if (task.name) lines.push(`【步骤】${task.name}`)
  if (task.agent) lines.push(`【执行】${task.agent}`)
  if (task.task_type) lines.push(`【类型】${task.task_type}`)
  lines.push("【详情】见【项目目标】")
  return lines.join("\n")
}

export function taskTypesForAgent(agentId: string, agents: AgentSummary[]): string[] {
  return agents.find((a) => a.id === agentId)?.task_types ?? []
}

export function templatesForTaskType(
  taskType: string,
  templates: DeliveryTemplateSummary[],
): DeliveryTemplateSummary[] {
  const tt = taskType.trim()
  if (!tt) return templates
  const bound = templates.filter((t) => (t.task_types || []).includes(tt))
  const unbound = templates.filter((t) => !(t.task_types || []).length)
  return bound.length ? [...bound, ...unbound] : templates
}

export type NodeRef = { id: string; label: string }

export function collectAllNodeIds(
  tasks: { id: string; name?: string; loop?: string }[],
  loopSpecs: Record<string, LoopSpec>,
): NodeRef[] {
  const nodes: NodeRef[] = []
  const seen = new Set<string>()
  for (const t of tasks) {
    if (t.id && !seen.has(t.id)) {
      seen.add(t.id)
      const name = (t.name || "").trim()
      nodes.push({ id: t.id, label: name ? `${t.id} · ${name}` : t.id })
    }
    if (t.loop && loopSpecs[t.loop]?.body) {
      for (const b of loopSpecs[t.loop].body || []) {
        if (b.id && !seen.has(b.id)) {
          seen.add(b.id)
          const bname = (b.name || "").trim()
          nodes.push({ id: b.id, label: bname ? `${b.id} · ${bname}` : b.id })
        }
      }
    }
  }
  return nodes
}

export function typeLabelMap(taskTypes: TaskTypeSummary[]): Record<string, string> {
  return Object.fromEntries(taskTypes.map((t) => [t.task_type, t.display_name || t.task_type]))
}
