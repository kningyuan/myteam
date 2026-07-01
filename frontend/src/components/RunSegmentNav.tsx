import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const segments = [
  { id: "workflows", label: "流程模板" },
  { id: "single", label: "独立任务" },
] as const

export type RunSegmentId = (typeof segments)[number]["id"]

export function RunSegmentNav() {
  return (
    <div className="list-segment-nav" role="tablist" aria-label="执行分类">
      {segments.map((s) => (
        <NavLink
          key={s.id}
          to={`/run/${s.id}`}
          className={({ isActive }) => cn("list-segment-item", isActive && "active")}
        >
          {s.label}
        </NavLink>
      ))}
    </div>
  )
}
