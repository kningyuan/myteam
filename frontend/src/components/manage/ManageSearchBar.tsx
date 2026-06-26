import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"

export function ManageSearchBar({
  value,
  onChange,
  placeholder,
  total,
  shown,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  total?: number
  shown?: number
}) {
  const countLabel =
    total != null && shown != null && value.trim()
      ? `${shown} / ${total}`
      : total != null
        ? String(total)
        : null

  return (
    <div className="manage-search-row">
      <div className="manage-search-wrap">
        <Search className="manage-search-icon" aria-hidden />
        <Input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="manage-search-input"
          autoComplete="off"
        />
      </div>
      {countLabel != null && <span className="manage-search-count">{countLabel}</span>}
    </div>
  )
}

export function matchQuery(query: string, ...parts: (string | undefined | null)[]) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = parts
    .flatMap((p) => (Array.isArray(p) ? p : [p]))
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
  return hay.includes(q)
}
