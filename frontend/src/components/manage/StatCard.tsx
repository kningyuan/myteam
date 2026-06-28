import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface StatCardProps {
  title: string
  count: number
  badge?: { label: string; variant?: "default" | "secondary" | "outline" }
  className?: string
}

export function StatCard({ title, count, badge, className }: StatCardProps) {
  return (
    <div className={cn("stat-card", className)}>
      <div className="stat-card-value">{count}</div>
      <div className="stat-card-label">{title}</div>
      {badge && (
        <div className="mt-2">
          <Badge variant={badge.variant || "secondary"}>{badge.label}</Badge>
        </div>
      )}
    </div>
  )
}
