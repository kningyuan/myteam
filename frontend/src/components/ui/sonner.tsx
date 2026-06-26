import { Toaster as Sonner } from "sonner"
import { useTheme } from "@/lib/theme"

export function Toaster() {
  const { theme } = useTheme()
  return (
    <Sonner
      theme={theme}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "group toast border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)] shadow-lg",
          description: "text-[var(--color-muted-foreground)]",
          actionButton: "bg-[var(--color-brand)] text-white",
          cancelButton: "bg-[var(--color-accent)] text-[var(--color-foreground)]",
        },
      }}
    />
  )
}
