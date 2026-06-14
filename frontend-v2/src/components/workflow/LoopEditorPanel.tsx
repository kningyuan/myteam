import type { AgentSummary } from "@/lib/api/agents"
import type { DeliveryTemplateSummary, TaskTypeSummary } from "@/lib/api/workflows"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { AssessStepEditor } from "./AssessStepEditor"
import { BodyTemplateManager, bodyStepsForSpec } from "./BodyTemplateManager"
import { TransitionEditor } from "./TransitionEditor"
import {
  WF_LOOP_OUTCOMES,
  WF_TASK_STATUSES,
  WF_UNTIL_TYPES,
  autoBodyDescription,
  defaultLoopSpec,
  nextBodyStepId,
  normalizeLoopUntil,
  taskTypesForAgent,
  templatesForTaskType,
  type LoopBodyTask,
  type LoopSpec,
  type LoopUntilCond,
  type NodeRef,
} from "./loopHelpers"

export function LoopEditorPanel({
  loopId,
  spec,
  onChange,
  agents,
  taskTypes,
  templates,
  typeLabel,
  depNodes,
}: {
  loopId: string
  spec: LoopSpec
  onChange: (spec: LoopSpec) => void
  agents: AgentSummary[]
  taskTypes: TaskTypeSummary[]
  templates: DeliveryTemplateSummary[]
  typeLabel: Record<string, string>
  depNodes: NodeRef[]
}) {
  const isV2 = !!(spec.bodies && Object.keys(spec.bodies).length > 0)
  const [activeBodyKey, setActiveBodyKey] = useState(
    spec.default_body || Object.keys(spec.bodies || {})[0] || "default",
  )

  if (isV2) {
    const bodyKeys = Object.keys(spec.bodies || {})
    const bodyStepIds = bodyStepsForSpec(spec, activeBodyKey).map((t) => t.id).filter(Boolean)
    return (
      <div className="wf-loop-inline">
        <div className="wf-loop-inline-head">
          v2 迭代 loop：多 body + assess + transition
        </div>
        <div className="wf-loop-inline-meta">
          <div>
            <Label className="text-xs">最大轮次</Label>
            <Input
              type="number"
              min={1}
              max={20}
              className="h-8"
              value={spec.max_rounds ?? 5}
              onChange={(e) =>
                onChange({
                  ...spec,
                  id: loopId,
                  max_rounds: Math.max(1, parseInt(e.target.value, 10) || 5),
                })
              }
            />
          </div>
          <div>
            <Label className="text-xs">最少轮次</Label>
            <Input
              type="number"
              min={1}
              max={20}
              className="h-8"
              value={spec.min_rounds ?? 1}
              onChange={(e) =>
                onChange({
                  ...spec,
                  id: loopId,
                  min_rounds: Math.max(1, parseInt(e.target.value, 10) || 1),
                })
              }
            />
          </div>
          <div>
            <Label className="text-xs">通过时</Label>
            <select
              className="wf-input-sm"
              value={spec.on_pass || "complete"}
              onChange={(e) => onChange({ ...spec, id: loopId, on_pass: e.target.value })}
            >
              {WF_LOOP_OUTCOMES.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs">轮次用尽</Label>
            <select
              className="wf-input-sm"
              value={spec.on_exhaust || "needs_review"}
              onChange={(e) => onChange({ ...spec, id: loopId, on_exhaust: e.target.value })}
            >
              {WF_LOOP_OUTCOMES.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <BodyTemplateManager
          spec={spec}
          activeBodyKey={activeBodyKey}
          onActiveBodyChange={setActiveBodyKey}
          onChange={(next) => onChange({ ...next, id: loopId })}
          agents={agents}
          taskTypes={taskTypes}
          templates={templates}
          typeLabel={typeLabel}
          depNodes={depNodes}
        />
        <AssessStepEditor
          assess={spec.assess}
          bodyStepIds={bodyStepIds}
          onChange={(assess) => onChange({ ...spec, id: loopId, assess })}
        />
        <TransitionEditor
          rules={spec.transition || []}
          bodyStepIds={bodyStepIds}
          bodyKeys={bodyKeys}
          onChange={(transition) => onChange({ ...spec, id: loopId, transition })}
        />
      </div>
    )
  }

  const body = spec.body?.length ? spec.body : defaultLoopSpec(loopId).body!
  const until = spec.until?.length ? spec.until : normalizeLoopUntil({ body, until: [] })
  const bodyIds = body.map((t) => t.id).filter(Boolean)

  function patch(partial: Partial<LoopSpec>) {
    onChange({ ...spec, ...partial, id: loopId })
  }

  function updateBody(index: number, row: Partial<LoopBodyTask>) {
    const next = body.map((b, i) => (i === index ? { ...b, ...row } : b))
    patch({ body: next })
  }

  function moveBody(index: number, delta: number) {
    const next = index + delta
    if (next < 0 || next >= body.length) return
    const copy = [...body]
    ;[copy[index], copy[next]] = [copy[next], copy[index]]
    patch({ body: copy })
  }

  function addBodyStep() {
    const prevId = body.length ? body[body.length - 1].id : null
    patch({
      body: [
        ...body,
        {
          id: nextBodyStepId(body),
          name: "",
          agent: agents[0]?.id || "research",
          task_type: "research",
          dependencies: prevId ? [prevId] : [],
          description: "",
        },
      ],
    })
  }

  function removeBody(index: number) {
    patch({ body: body.filter((_, i) => i !== index) })
  }

  function updateUntil(index: number, cond: LoopUntilCond) {
    const next = until.map((u, i) => (i === index ? cond : u))
    patch({ until: next })
  }

  function addUntil() {
    const last = bodyIds[bodyIds.length - 1] || "step-2"
    patch({ until: [...until, { type: "gate_passed", task: last }] })
  }

  function removeUntil(index: number) {
    patch({ until: until.filter((_, i) => i !== index) })
  }

  return (
    <div className="wf-loop-inline">
      <div className="wf-loop-inline-head">
        Work → 审计 多轮循环；退出由 <strong>Gate</strong>（交付模板 + 任务类型 + Agent 交付）判定
      </div>
      <div className="wf-loop-inline-meta">
        <div>
          <Label className="text-xs">最大轮次</Label>
          <Input
            type="number"
            min={1}
            max={20}
            className="h-8"
            value={spec.max_rounds ?? 5}
            onChange={(e) => patch({ max_rounds: Math.max(1, parseInt(e.target.value, 10) || 5) })}
          />
        </div>
        <div>
          <Label className="text-xs">通过时</Label>
          <select
            className="wf-input-sm"
            value={spec.on_pass || "complete"}
            onChange={(e) => patch({ on_pass: e.target.value })}
          >
            {WF_LOOP_OUTCOMES.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs">轮次用尽</Label>
          <select
            className="wf-input-sm"
            value={spec.on_exhaust || "needs_review"}
            onChange={(e) => patch({ on_exhaust: e.target.value })}
          >
            {WF_LOOP_OUTCOMES.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs">最少轮次 (v2)</Label>
          <Input
            type="number"
            min={1}
            max={20}
            className="h-8"
            value={spec.min_rounds ?? 1}
            onChange={(e) => patch({ min_rounds: Math.max(1, parseInt(e.target.value, 10) || 1) })}
          />
        </div>
        <div>
          <Label className="text-xs">Assess 步骤 (v2)</Label>
          <Input
            className="h-8"
            placeholder="review"
            value={spec.assess?.ref ?? ""}
            onChange={(e) =>
              patch({
                assess: e.target.value.trim()
                  ? { ref: e.target.value.trim(), inputs: spec.assess?.inputs ?? [] }
                  : undefined,
              })
            }
          />
        </div>
      </div>

      {(spec.transition?.length ?? 0) > 0 && (
        <div className="wf-loop-section-title">
          Transition 规则 (v2) · {spec.transition!.length} 条 — 保存时随 workflow YAML 写入
        </div>
      )}
      <div className="wf-loop-body-scroll">
        <table className="wf-task-table wf-body-table">
          <thead>
            <tr>
              <th className="w-12" />
              <th>ID</th>
              <th>名称</th>
              <th>Agent</th>
              <th>类型</th>
              <th>交付模板</th>
              <th>依赖</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {body.map((step, i) => {
              const allowedTypes = taskTypesForAgent(step.agent || "", agents)
              const tplPool = templatesForTaskType(step.task_type || "", templates)
              return (
                <tr key={step.id}>
                  <td>
                    <div className="wf-order-btns">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-6 px-1"
                        disabled={i === 0}
                        onClick={() => moveBody(i, -1)}
                      >
                        ↑
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-6 px-1"
                        disabled={i === body.length - 1}
                        onClick={() => moveBody(i, 1)}
                      >
                        ↓
                      </Button>
                    </div>
                  </td>
                  <td>
                    <code className="wf-id-badge">{step.id}</code>
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
                      <option value="">（任务类型默认）</option>
                      {tplPool.map((tpl) => (
                        <option key={tpl.id} value={tpl.id}>
                          {tpl.display_name || tpl.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      multiple
                      className="wf-deps-multi wf-input-sm h-[72px]"
                      value={step.dependencies || []}
                      onChange={(e) => {
                        const deps = Array.from(e.target.selectedOptions).map((o) => o.value)
                        updateBody(i, { dependencies: deps })
                      }}
                    >
                      {depNodes
                        .filter((n) => n.id !== step.id)
                        .map((n) => (
                          <option key={n.id} value={n.id}>
                            {n.label}
                          </option>
                        ))}
                    </select>
                  </td>
                  <td>
                    <Button type="button" size="sm" variant="ghost" onClick={() => removeBody(i)}>
                      删
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <Button type="button" size="sm" variant="outline" className="mt-2" onClick={addBodyStep}>
        添加步骤
      </Button>

      <div className="wf-loop-section-title mt-4">何时停止循环（满足任一）</div>
      <p className="text-xs text-[var(--color-muted-foreground)]">
        推荐「Gate 通过」：内核按该 step 的交付模板与任务类型验收交付物。
      </p>
      <div className="wf-until-list space-y-2">
        {until.map((cond, i) => (
          <UntilRow
            key={i}
            cond={cond}
            bodyIds={bodyIds}
            onChange={(c) => updateUntil(i, c)}
            onRemove={() => removeUntil(i)}
          />
        ))}
      </div>
      <Button type="button" size="sm" variant="outline" className="mt-2" onClick={addUntil}>
        添加退出条件
      </Button>
    </div>
  )
}

function UntilRow({
  cond,
  bodyIds,
  onChange,
  onRemove,
}: {
  cond: LoopUntilCond
  bodyIds: string[]
  onChange: (c: LoopUntilCond) => void
  onRemove: () => void
}) {
  const spec = WF_UNTIL_TYPES.find((t) => t.id === cond.type) || WF_UNTIL_TYPES[0]
  const fields = spec.fields

  return (
    <div className="wf-until-row" title={spec.hint}>
      <div className="wf-until-field">
        <Label className="text-xs">退出条件</Label>
        <select
          className="wf-input-sm"
          value={cond.type}
          onChange={(e) => {
            const nextType = e.target.value
            const nextSpec = WF_UNTIL_TYPES.find((t) => t.id === nextType) || WF_UNTIL_TYPES[0]
            const next: LoopUntilCond = { type: nextType }
            if (nextSpec.fields.includes("task")) {
              next.task = cond.task || bodyIds[bodyIds.length - 1] || ""
            }
            if (nextSpec.fields.includes("status")) next.status = cond.status || "completed"
            if (nextSpec.fields.includes("marker")) next.marker = cond.marker || ""
            onChange(next)
          }}
        >
          {WF_UNTIL_TYPES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
      </div>
      {fields.includes("task") && (
        <div className="wf-until-field">
          <Label className="text-xs">step</Label>
          <select
            className="wf-input-sm"
            value={cond.task || bodyIds[bodyIds.length - 1] || ""}
            onChange={(e) => onChange({ ...cond, task: e.target.value })}
          >
            {bodyIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
      )}
      {fields.includes("marker") && (
        <div className="wf-until-field">
          <Label className="text-xs">标记文本</Label>
          <input
            className="wf-input-sm"
            value={cond.marker || ""}
            placeholder="可选"
            onChange={(e) => onChange({ ...cond, marker: e.target.value })}
          />
        </div>
      )}
      {fields.includes("status") && (
        <div className="wf-until-field">
          <Label className="text-xs">目标状态</Label>
          <select
            className="wf-input-sm"
            value={cond.status || "completed"}
            onChange={(e) => onChange({ ...cond, status: e.target.value })}
          >
            {WF_TASK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}
      <Button type="button" size="sm" variant="ghost" onClick={onRemove}>
        删
      </Button>
    </div>
  )
}

export function serializeLoopSpec(spec: LoopSpec): LoopSpec {
  const isV2 = !!(spec.bodies && Object.keys(spec.bodies).length)
  if (isV2) {
    const bodies: Record<string, LoopBodyTask[]> = {}
    for (const [key, rows] of Object.entries(spec.bodies || {})) {
      bodies[key] = rows.map((b) => ({
        ...b,
        description: autoBodyDescription(b),
      }))
    }
    const defaultKey = spec.default_body || "default"
    return {
      ...spec,
      max_rounds: Math.max(1, spec.max_rounds ?? 5),
      min_rounds: Math.max(1, spec.min_rounds ?? 1),
      default_body: defaultKey,
      bodies,
      body: bodies[defaultKey] || [],
      on_pass: spec.on_pass || "complete",
      on_exhaust: spec.on_exhaust || "needs_review",
      assess: spec.assess,
      transition: spec.transition || [],
      fallback_until: spec.fallback_until,
    }
  }
  const body = (spec.body || []).map((b) => ({
    ...b,
    description: autoBodyDescription(b),
  }))
  return {
    ...spec,
    body,
    until: normalizeLoopUntil({ body, until: spec.until }),
    max_rounds: Math.max(1, spec.max_rounds ?? 5),
    min_rounds: spec.min_rounds,
    on_pass: spec.on_pass || "complete",
    on_exhaust: spec.on_exhaust || "needs_review",
  }
}
