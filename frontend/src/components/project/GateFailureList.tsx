import { formatGateFailures, type GateFailureLike } from "@/lib/project/project-labels"

export function GateFailureList({ failures }: { failures: (GateFailureLike | string)[] }) {
  const lines = formatGateFailures(failures)
  if (!lines.length) return null
  return (
    <ul className="exec-fail-list exec-fail-list--structured">
      {lines.map((line, i) => (
        <li key={i}>{line}</li>
      ))}
    </ul>
  )
}
