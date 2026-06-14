import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { LoopAssessInput, LoopAssessSpec } from "./loopHelpers"

const ASSESS_INPUT_KINDS = [
  { id: "goal", label: "项目目标" },
  { id: "phase.deliverable", label: "阶段交付物" },
  { id: "ops_log", label: "运营日志" },
]

export function AssessStepEditor({
  assess,
  bodyStepIds,
  onChange,
}: {
  assess?: LoopAssessSpec
  bodyStepIds: string[]
  onChange: (assess: LoopAssessSpec | undefined) => void
}) {
  const ref = assess?.ref ?? ""
  const inputs = assess?.inputs ?? []

  function patchRef(nextRef: string) {
    if (!nextRef.trim()) {
      onChange(undefined)
      return
    }
    onChange({ ref: nextRef.trim(), inputs })
  }

  function updateInput(index: number, row: LoopAssessInput) {
    const next = inputs.map((r, i) => (i === index ? row : r))
    onChange({ ref: ref || "assess", inputs: next })
  }

  function addInput() {
    onChange({
      ref: ref || "assess",
      inputs: [...inputs, { kind: "goal" }],
    })
  }

  function removeInput(index: number) {
    const next = inputs.filter((_, i) => i !== index)
    if (!next.length && !ref) onChange(undefined)
    else onChange({ ref: ref || "assess", inputs: next })
  }

  return (
    <div className="wf-loop-section space-y-2">
      <div className="wf-loop-section-title">Assess 配置 (v2)</div>
      <div className="wf-loop-inline-meta">
        <div>
          <Label className="text-xs">assess.ref（body 内步骤 id）</Label>
          <Input
            className="h-8"
            placeholder="assess"
            value={ref}
            onChange={(e) => patchRef(e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        {inputs.map((inp, i) => (
          <div key={i} className="wf-until-row">
            <div className="wf-until-field">
              <Label className="text-xs">kind</Label>
              <select
                className="wf-input-sm"
                value={inp.kind || "goal"}
                onChange={(e) => updateInput(i, { ...inp, kind: e.target.value })}
              >
                {ASSESS_INPUT_KINDS.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            {inp.kind === "phase.deliverable" && (
              <div className="wf-until-field">
                <Label className="text-xs">phase</Label>
                <select
                  className="wf-input-sm"
                  value={inp.phase || bodyStepIds[0] || ""}
                  onChange={(e) => updateInput(i, { ...inp, phase: e.target.value })}
                >
                  {bodyStepIds.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {inp.kind === "ops_log" && (
              <div className="wf-until-field">
                <Label className="text-xs">table</Label>
                <Input
                  className="h-8"
                  defaultValue="publish_log"
                  onChange={(e) =>
                    updateInput(i, { ...inp, table: e.target.value } as LoopAssessInput)
                  }
                />
              </div>
            )}
            <Button type="button" size="sm" variant="ghost" onClick={() => removeInput(i)}>
              删
            </Button>
          </div>
        ))}
      </div>
      <Button type="button" size="sm" variant="outline" onClick={addInput}>
        添加 assess input
      </Button>
    </div>
  )
}
