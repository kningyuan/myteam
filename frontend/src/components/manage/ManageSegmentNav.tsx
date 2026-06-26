import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const segments = [
  { id: "agents", label: "Agent" },
  { id: "preferences", label: "偏好库" },
  { id: "knowledge", label: "知识库" },
  { id: "task-types", label: "任务类型" },
  { id: "templates", label: "交付模板" },
  { id: "delivery-profiles", label: "交付流程" },
] as const

export type ManageSegmentId = (typeof segments)[number]["id"]

export function ManageSegmentNav() {
  return (
    <div className="list-segment-nav" role="tablist" aria-label="管理分类">
      {segments.map((s) => (
        <NavLink
          key={s.id}
          to={`/manage/${s.id}`}
          className={({ isActive }) => cn("list-segment-item", isActive && "active")}
        >
          {s.label}
        </NavLink>
      ))}
    </div>
  )
}
