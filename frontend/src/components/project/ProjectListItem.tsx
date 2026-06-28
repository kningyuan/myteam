import { Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { statusLabel } from "@/components/ui/page"

export function ProjectListItem({
  name,
  status,
  progress = 0,
  taskCount = 0,
  active,
  onClick,
  onDelete,
}: {
  name: string
  status?: string
  progress?: number
  taskCount?: number
  active?: boolean
  onClick?: () => void
  onDelete?: () => void
}) {
  const pct = Math.round((progress ?? 0) * 100)

  return (
    <div
      className={cn("list-item project-list-item", active && "active")}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick?.()}
      role="button"
      tabIndex={0}
    >
      <div className="list-item-avatar">{name.slice(0, 2).toUpperCase()}</div>
      <div className="list-item-main">
        <div className="list-item-row1">
          <div className="list-item-name">{name}</div>
          <span className="list-item-pct">{pct}%</span>
        </div>
        <div className="list-item-row2">
          <div className="list-item-sub">
            {statusLabel(status || "unknown")} · {taskCount} 任务
          </div>
        </div>
        <div className="list-item-progress">
          <i style={{ width: `${pct}%` }} />
        </div>
      </div>
      {onDelete && (
        <button
          type="button"
          className="list-item-del"
          title="删除项目"
          aria-label="删除项目"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
