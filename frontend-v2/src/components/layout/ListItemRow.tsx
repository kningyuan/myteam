import { cn } from "@/lib/utils"

export function ListItemRow({
  name,
  sub,
  avatar,
  active,
  onClick,
}: {
  name: string
  sub?: string
  avatar: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <div
      className={cn("list-item", active && "active")}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick?.()}
      role="button"
      tabIndex={0}
    >
      <div className="list-item-avatar">{avatar.slice(0, 2).toUpperCase()}</div>
      <div className="list-item-main">
        <div className="list-item-name">{name}</div>
        {sub && <div className="list-item-sub">{sub}</div>}
      </div>
    </div>
  )
}
