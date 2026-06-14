import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { WF_LOOP_OUTCOMES, type LoopTransitionRule } from "./loopHelpers"

const WHEN_TYPES = [
  { id: "deliverable_marker", label: "交付物含 marker" },
  { id: "exhausted", label: "轮次用尽" },
  { id: "gate_passed", label: "Gate 通过" },
]

export function TransitionEditor({
  rules,
  bodyStepIds,
  bodyKeys,
  onChange,
}: {
  rules: LoopTransitionRule[]
  bodyStepIds: string[]
  bodyKeys: string[]
  onChange: (rules: LoopTransitionRule[]) => void
}) {
  function update(index: number, row: LoopTransitionRule) {
    onChange(rules.map((r, i) => (i === index ? row : r)))
  }

  function addRule() {
    onChange([
      ...rules,
      {
        when: "deliverable_marker",
        task: bodyStepIds[bodyStepIds.length - 1] || "assess",
        marker: "ITERATION: PASS",
        action: "exit",
        outcome: "complete",
      },
    ])
  }

  function remove(index: number) {
    onChange(rules.filter((_, i) => i !== index))
  }

  return (
    <div className="wf-loop-section space-y-2">
      <div className="wf-loop-section-title">Transition 规则 (v2)</div>
      <div className="space-y-2">
        {rules.map((rule, i) => (
          <div key={i} className="wf-until-row flex-wrap">
            <div className="wf-until-field">
              <Label className="text-xs">when</Label>
              <select
                className="wf-input-sm"
                value={rule.when || "deliverable_marker"}
                onChange={(e) => update(i, { ...rule, when: e.target.value })}
              >
                {WHEN_TYPES.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.label}
                  </option>
                ))}
              </select>
            </div>
            {rule.when !== "exhausted" && (
              <div className="wf-until-field">
                <Label className="text-xs">task</Label>
                <select
                  className="wf-input-sm"
                  value={rule.task || ""}
                  onChange={(e) => update(i, { ...rule, task: e.target.value })}
                >
                  {bodyStepIds.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {rule.when === "deliverable_marker" && (
              <div className="wf-until-field">
                <Label className="text-xs">marker</Label>
                <input
                  className="wf-input-sm"
                  value={rule.marker || ""}
                  onChange={(e) => update(i, { ...rule, marker: e.target.value })}
                />
              </div>
            )}
            <div className="wf-until-field">
              <Label className="text-xs">action</Label>
              <select
                className="wf-input-sm"
                value={rule.action || "exit"}
                onChange={(e) => update(i, { ...rule, action: e.target.value })}
              >
                <option value="exit">exit</option>
                <option value="continue">continue</option>
              </select>
            </div>
            {rule.action === "exit" && (
              <div className="wf-until-field">
                <Label className="text-xs">outcome</Label>
                <select
                  className="wf-input-sm"
                  value={rule.outcome || "complete"}
                  onChange={(e) => update(i, { ...rule, outcome: e.target.value })}
                >
                  {WF_LOOP_OUTCOMES.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {rule.action === "continue" && bodyKeys.length > 1 && (
              <div className="wf-until-field">
                <Label className="text-xs">next_body</Label>
                <select
                  className="wf-input-sm"
                  value={rule.next_body || ""}
                  onChange={(e) => update(i, { ...rule, next_body: e.target.value })}
                >
                  <option value="">（保持当前 body）</option>
                  {bodyKeys.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <Button type="button" size="sm" variant="ghost" onClick={() => remove(i)}>
              删
            </Button>
          </div>
        ))}
      </div>
      <Button type="button" size="sm" variant="outline" onClick={addRule}>
        添加 transition 规则
      </Button>
    </div>
  )
}
