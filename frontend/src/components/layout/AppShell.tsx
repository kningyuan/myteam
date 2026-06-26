import { NavLink, Outlet } from "react-router-dom"
import {
  Bot,
  FolderKanban,
  LayoutDashboard,
  Layers,
  Settings,
  Users,
  Workflow,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const navItems: {
  to: string
  end?: boolean
  label: string
  icon: typeof LayoutDashboard
}[] = [
  { to: "/", end: true, label: "总览", icon: LayoutDashboard },
  { to: "/projects", label: "项目", icon: FolderKanban },
  { to: "/groups", label: "群组", icon: Users },
  { to: "/agents", label: "Agent", icon: Bot },
  { to: "/workflows", label: "流程", icon: Workflow },
  { to: "/task-types", label: "任务类型", icon: Layers },
  { to: "/settings", label: "设置", icon: Settings },
]

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all",
    isActive
      ? "bg-[var(--color-brand)] font-medium text-white shadow-sm"
      : "text-[var(--color-sidebar-fg)] hover:bg-[var(--color-sidebar-hover)] hover:text-[var(--color-foreground)]",
  )
}

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-[var(--color-background)]">
      <aside className="flex w-[72px] shrink-0 flex-col items-center border-r border-[var(--color-border)] bg-[var(--color-sidebar)] py-3 md:w-56 md:items-stretch md:px-3">
        <div className="mb-4 flex flex-col items-center gap-1 px-2 md:items-start md:px-1 md:pt-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--color-brand)] text-sm font-bold text-white shadow-lg shadow-[var(--color-brand)]/30">
            M
          </div>
          <div className="hidden md:block">
            <div className="px-1 text-sm font-semibold">myteam</div>
            <div className="px-1 text-[11px] text-[var(--color-muted-foreground)]">团队协作工作台</div>
          </div>
        </div>
        <nav className="flex w-full flex-1 flex-col gap-1">
          {navItems.map(({ to, end, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={end} className={navClass} title={label}>
              <Icon className="mx-auto h-[18px] w-[18px] shrink-0 md:mx-0" />
              <span className="hidden md:inline">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-3 hidden w-full border-t border-[var(--color-border)] pt-3 md:block">
          <Button variant="outline" size="sm" className="w-full border-[var(--color-border)] bg-transparent" asChild>
            <a href="/">经典版界面</a>
          </Button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
