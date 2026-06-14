import type { ReactNode } from "react"
import { Badge, statusBadgeVariant } from "@/components/ui/badge"

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] pb-6">
      <div>
        <h1 className="page-title">{title}</h1>
        {description && (
          <p className="page-description">{description}</p>
        )}
      </div>
      {action}
    </div>
  )
}

export function SettingSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-[var(--shadow-xs)]">
      <div className="border-b border-[var(--color-border)] px-5 py-4">
        <h2 className="setting-section-title">{title}</h2>
        {description && <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{description}</p>}
      </div>
      <div className="divide-y divide-[var(--color-border)] px-5">{children}</div>
    </section>
  )
}

export function SettingRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3.5">
      <span className="text-sm text-[var(--color-muted-foreground)]">{label}</span>
      <span className="text-sm font-medium text-[var(--color-foreground)]">{value ?? "—"}</span>
    </div>
  )
}

export function StatusBadge({
  status,
  label,
}: {
  status?: string
  label?: string
}) {
  const s = status || "unknown"
  return <Badge variant={statusBadgeVariant(s)}>{label || s}</Badge>
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-card)] px-6 py-16 text-center shadow-[var(--shadow-xs)]">
      <p className="text-sm font-medium text-[var(--color-foreground)]">{title}</p>
      {description && <p className="mt-2 max-w-sm text-sm text-[var(--color-muted-foreground)]">{description}</p>}
    </div>
  )
}

export function Pill({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "brand" | "muted" }) {
  const variant = tone === "brand" ? "default" : tone === "muted" ? "secondary" : "outline"
  return <Badge variant={variant}>{children}</Badge>
}

const GATE_LABELS: Record<string, string> = {
  check_format: "文档格式校验",
  check_code_project: "工程包校验",
  check_action_evidence: "动作证据校验",
}

export function gateLabel(algo?: string): string {
  if (!algo) return "—"
  return GATE_LABELS[algo] || algo
}

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  running: "运行中",
  failed: "失败",
  pending: "等待中",
  paused: "已暂停",
}

export function statusLabel(status?: string): string {
  if (!status) return "未知"
  return STATUS_LABELS[status] || status
}

export function boolLabel(v: unknown): string {
  return v === false ? "关闭" : v === true ? "开启" : "—"
}

export function formatNumber(n?: number): string {
  if (n == null || Number.isNaN(n)) return "—"
  return n.toLocaleString("zh-CN")
}
