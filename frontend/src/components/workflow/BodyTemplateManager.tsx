import type { AgentSummary } from "@/lib/api/agents"
import type { DeliveryTemplateSummary, TaskTypeSummary } from "@/lib/api/workflows"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  nextBodyStepId,
  renumberBodySteps,
  remapLoopSpecStepRefs,
  taskTypesForAgent,
  templatesForTaskType,
  type LoopBodyTask,
  type LoopSpec,
  type NodeRef,
} from "./loopHelpers"
import { DependencyCheckboxPicker } from "./DependencyCheckboxPicker"

export function BodyTemplateManager({
  spec,
  activeBodyKey,
  onActiveBodyChange,
  onChange,
  agents,
  taskTypes,
  templates,
  typeLabel,
  depNodes,
}: {
  spec: LoopSpec
  activeBodyKey: string
  onActiveBodyChange: (key: string) => void
  onChange: (spec: LoopSpec) => void
  agents: AgentSummary[]
  taskTypes: TaskTypeSummary[]
  templates: DeliveryTemplateSummary[]
  typeLabel: Record<string, string>
  depNodes: NodeRef[]
}) {
  const bodies = spec.bodies || { default: spec.body || [] }
  const bodyKeys = Object.keys(bodies)
  const body = bodies[activeBodyKey] || []

  function patchBodies(next: Record<string, LoopBodyTask[]>) {
    onChange({ ...spec, bodies: next, body: next[spec.default_body || "default"] || [] })
  }

  function updateBody(index: number, row: Partial<LoopBodyTask>) {
    const nextBody = body.map((b, i) => (i === index ? { ...b, ...row } : b))
    patchBodies({ ...bodies, [activeBodyKey]: nextBody })
  }

  function addBodyKey() {
    const base = `body-${bodyKeys.length + 1}`
    let key = base
    let n = 1
    while (bodyKeys.includes(key)) {
      n += 1
      key = `${base}-${n}`
    }
    patchBodies({
      ...bodies,
      [key]: [
        {
          id: "step-1",
          name: "",
          agent: agents[0]?.id || "research",
          task_type: "research",
          dependencies: [],
        },
      ],
    })
    onActiveBodyChange(key)
  }

  function removeBodyKey(key: string) {
    if (bodyKeys.length <= 1) return
    const next = { ...bodies }
    delete next[key]
    const nextDefault =
      spec.default_body === key ? Object.keys(next)[0] : spec.default_body || "default"
    onChange({ ...spec, bodies: next, default_body: nextDefault, body: next[nextDefault] || [] })
    onActiveBodyChange(nextDefault)
  }

  function removeStep(index: number) {
    const filtered = body.filter((_, j) => j !== index)
    const { steps, idMap } = renumberBodySteps(filtered)
    const newBodies = { ...bodies, [activeBodyKey]: steps }
    onChange(
      remapLoopSpecStepRefs(
        {
          ...spec,
          bodies: newBodies,
          body: newBodies[spec.default_body || "default"] || [],
        },
        idMap,
      ),
    )
  }

  function addStep() {
    const prevId = body.length ? body[body.length - 1].id : null
    const nextBody = [
      ...body,
      {
        id: nextBodyStepId(body),
        name: "",
        agent: agents[0]?.id || "research",
        task_type: "research",
        dependencies: prevId ? [prevId] : [],
        description: "",
      },
    ]
    patchBodies({ ...bodies, [activeBodyKey]: nextBody })
  }

  return (
    <div className="wf-loop-section space-y-2">
      <div className="wf-loop-section-title">Body 模板 (v2)</div>
      <div className="flex flex-wrap gap-2 items-center">
        {bodyKeys.map((k) => (
          <Button
            key={k}
            type="button"
            size="sm"
            variant={k === activeBodyKey ? "default" : "outline"}
            onClick={() => onActiveBodyChange(k)}
          >
            {k}
            {spec.default_body === k ? " · default" : ""}
          </Button>
        ))}
        <Button type="button" size="sm" variant="outline" onClick={addBodyKey}>
          + body
        </Button>
      </div>
      <div className="wf-loop-inline-meta">
        <div>
          <Label className="text-xs">default_body</Label>
          <select
            className="wf-input-sm"
            value={spec.default_body || "default"}
            onChange={(e) => onChange({ ...spec, default_body: e.target.value })}
          >
            {bodyKeys.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        {bodyKeys.length > 1 && (
          <Button type="button" size="sm" variant="ghost" onClick={() => removeBodyKey(activeBodyKey)}>
            删除当前 body
          </Button>
        )}
      </div>
      <div className="wf-loop-body-scroll">
        <table className="wf-task-table wf-body-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>名称</th>
              <th>Agent</th>
              <th>类型</th>
              <th>模板</th>
              <th>依赖</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {body.map((step, i) => {
              const allowedTypes = taskTypesForAgent(step.agent || "", agents)
              const tplPool = templatesForTaskType(step.task_type || "", templates)
              return (
                <tr key={step.id}>
                  <td>
                    <code className="wf-id-badge" title="按创建顺序自动生成">
                      {step.id}
                    </code>
                  </td>
                  <td>
                    <input
                      className="wf-input-sm"
                      value={step.name || ""}
                      onChange={(e) => updateBody(i, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="wf-input-sm"
                      value={step.agent || ""}
                      onChange={(e) => {
                        const agent = e.target.value
                        const types = taskTypesForAgent(agent, agents)
                        updateBody(i, {
                          agent,
                          task_type: types.includes(step.task_type || "")
                            ? step.task_type
                            : types[0] || step.task_type,
                          template_id: "",
                        })
                      }}
                    >
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name || a.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="wf-input-sm"
                      value={step.task_type || ""}
                      onChange={(e) =>
                        updateBody(i, { task_type: e.target.value, template_id: "" })
                      }
                    >
                      {(allowedTypes.length ? allowedTypes : taskTypes.map((t) => t.task_type)).map(
                        (tid) => (
                          <option key={tid} value={tid}>
                            {typeLabel[tid] || tid}
                          </option>
                        ),
                      )}
                    </select>
                  </td>
                  <td>
                    <select
                      className="wf-input-sm"
                      value={step.template_id || ""}
                      onChange={(e) => updateBody(i, { template_id: e.target.value })}
                    >
                      <option value="">（默认）</option>
                      {tplPool.map((tpl) => (
                        <option key={tpl.id} value={tpl.id}>
                          {tpl.display_name || tpl.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <DependencyCheckboxPicker
                      currentId={step.id}
                      candidates={depNodes}
                      extraCandidates={body
                        .filter((b) => b.id !== step.id)
                        .map((b) => ({
                          id: b.id,
                          label: b.name ? `${b.id} · ${b.name}` : b.id,
                        }))}
                      value={step.dependencies || []}
                      onChange={(deps) => updateBody(i, { dependencies: deps })}
                    />
                  </td>
                  <td>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => removeStep(i)}
                    >
                      删
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <Button type="button" size="sm" variant="outline" onClick={addStep}>
        添加步骤
      </Button>
    </div>
  )
}

export function bodyStepsForSpec(spec: LoopSpec, bodyKey?: string): LoopBodyTask[] {
  const key = bodyKey || spec.default_body || "default"
  if (spec.bodies?.[key]) return spec.bodies[key]
  return spec.body || []
}
