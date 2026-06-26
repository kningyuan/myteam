import { cn } from "@/lib/utils"

export function ListItemRow({
  name,
  sub,
  avatar,
  tag,
  active,
  onClick,
  onDelete,
}: {
  name: string
  sub?: string
  avatar: string
  tag?: string
  active?: boolean
  onClick?: () => void
  onDelete?: () => void
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
        <div className="list-item-name-row">
          <div className="list-item-name">{name}</div>
          {tag ? <span className="skill-category-tag skill-category-tag--static list-item-tag">{tag}</span> : null}
        </div>
        {sub && <div className="list-item-sub">{sub}</div>}
      </div>
      {onDelete && (
        <button
          className="list-item-del"
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          title="删除"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6" />
          </svg>
        </button>
      )}
    </div>
  )
}
