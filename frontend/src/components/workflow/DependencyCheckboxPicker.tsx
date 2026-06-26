import type { NodeRef } from "./loopHelpers"

function mergeCandidates(
  primary: NodeRef[],
  extra: NodeRef[] | undefined,
  excludeId: string,
): NodeRef[] {
  const seen = new Set<string>()
  const out: NodeRef[] = []
  for (const n of [...primary, ...(extra || [])]) {
    const id = (n.id || "").trim()
    if (!id || id === excludeId || seen.has(id)) continue
    seen.add(id)
    out.push(n)
  }
  return out
}

export function DependencyCheckboxPicker({
  currentId,
  candidates,
  extraCandidates,
  value,
  onChange,
}: {
  currentId: string
  candidates: NodeRef[]
  extraCandidates?: NodeRef[]
  value: string[]
  onChange: (deps: string[]) => void
}) {
  const options = mergeCandidates(candidates, extraCandidates, currentId)
  const selected = new Set(value || [])

  if (!options.length) {
    return (
      <span className="text-xs text-[var(--color-muted-foreground)]">无可选前置</span>
    )
  }

  return (
    <div className="wf-deps-checkboxes max-h-28 space-y-0.5 overflow-y-auto rounded-md border border-[var(--color-border)] p-1.5">
      {options.map((n) => (
        <label key={n.id} className="flex items-start gap-2 text-xs leading-snug">
          <input
            type="checkbox"
            className="mt-0.5 shrink-0"
            checked={selected.has(n.id)}
            onChange={(e) => {
              const next = new Set(selected)
              if (e.target.checked) next.add(n.id)
              else next.delete(n.id)
              onChange(Array.from(next))
            }}
          />
          <span title={n.id}>{n.label}</span>
        </label>
      ))}
    </div>
  )
}
