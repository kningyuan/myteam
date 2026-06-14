import { NavLink } from "react-router-dom"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export function ListNavItem({
  to,
  end,
  icon: Icon,
  label,
  description,
}: {
  to: string
  end?: boolean
  icon: LucideIcon
  label: string
  description?: string
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => cn("list-nav-item", isActive && "active")}
    >
      <Icon className="list-nav-icon" size={16} strokeWidth={1.75} />
      <span className="list-nav-text">
        <span className="list-nav-label">{label}</span>
        {description && <span className="list-nav-desc">{description}</span>}
      </span>
    </NavLink>
  )
}

export function ListSectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="list-section-label">{children}</div>
}
