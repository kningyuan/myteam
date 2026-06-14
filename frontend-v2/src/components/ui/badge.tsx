import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-[var(--color-brand)]/20 text-[var(--color-brand-light)]",
        secondary: "border-transparent bg-[var(--color-accent)] text-[var(--color-foreground)]",
        outline: "border-[var(--color-border)] text-[var(--color-foreground)]",
        success: "border-transparent bg-emerald-500/15 text-[var(--color-success)]",
        warning: "border-transparent bg-amber-500/15 text-[var(--color-warning)]",
        destructive: "border-transparent bg-red-500/15 text-[var(--color-danger)]",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

export function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export function statusBadgeVariant(status?: string): VariantProps<typeof badgeVariants>["variant"] {
  switch (status) {
    case "completed":
    case "online":
      return "success"
    case "running":
      return "default"
    case "failed":
      return "destructive"
    case "paused":
      return "warning"
    default:
      return "secondary"
  }
}
