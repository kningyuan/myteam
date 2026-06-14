import type { ReactNode } from "react"
import { NavLink } from "react-router-dom"
import {
  FolderKanban,
  Home,
  Layers,
  MessageCircle,
  Moon,
  Settings,
  Sun,
  Users,
  Workflow,
  Sparkles,
} from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ResizableColumn } from "@/components/ui/ResizableColumn"
import { useColumnWidth } from "@/lib/use-column-width"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

const mainNav: {
  to: string
  end?: boolean
  label: string
  icon: typeof Home
}[] = [
  { to: "/", end: true, label: "总览", icon: Home },
  { to: "/chat", label: "对话", icon: MessageCircle },
  { to: "/groups", label: "群组", icon: Users },
  { to: "/projects", label: "项目", icon: FolderKanban },
  { to: "/manage", label: "管理", icon: Layers },
  { to: "/workflows", label: "流程", icon: Workflow },
  { to: "/skills", label: "Skill", icon: Sparkles },
]

function railClass({ isActive }: { isActive: boolean }) {
  return cn("discord-rail-btn", isActive && "active")
}

export function RailNav() {
  const { theme, toggleTheme } = useTheme()
  return (
    <nav className="discord-rail">
      <div className="discord-rail-logo">M</div>
      <div className="discord-rail-tabs">
        {mainNav.map(({ to, end, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={end} className={railClass} title={label}>
            <Icon size={21} strokeWidth={1.75} />
          </NavLink>
        ))}
      </div>
      <div className="discord-rail-bottom">
        <button
          type="button"
          className="discord-rail-btn"
          title={theme === "dark" ? "切换浅色主题" : "切换深色主题"}
          onClick={toggleTheme}
        >
          {theme === "dark" ? <Sun size={19} strokeWidth={1.75} /> : <Moon size={19} strokeWidth={1.75} />}
        </button>
        <NavLink to="/settings" className={railClass} title="设置">
          <Settings size={19} strokeWidth={1.75} />
        </NavLink>
      </div>
    </nav>
  )
}

export function DiscordShell({
  list,
  children,
  detail,
}: {
  list?: ReactNode
  children: ReactNode
  detail?: ReactNode
}) {
  return (
    <div className="discord-app">
      <RailNav />
      <div className="discord-body">
        {list}
        <main className="discord-main">{children}</main>
        {detail}
      </div>
    </div>
  )
}

export function ListColumn({
  title,
  action,
  tabs,
  search,
  children,
  resizable = true,
  widthStorageKey = "agentHub.listWidth",
}: {
  title: string
  action?: ReactNode
  tabs?: ReactNode
  search?: ReactNode
  children: ReactNode
  resizable?: boolean
  widthStorageKey?: string
}) {
  const { width, setWidth, minWidth, maxWidth } = useColumnWidth(widthStorageKey, 300, 220, 480)

  const column = (
    <>
      <div className="list-header">
        <span>{title}</span>
        {action}
      </div>
      {tabs}
      {search && <div className="list-search">{search}</div>}
      <ScrollArea className="flex-1 min-h-0">
        <div className="list-items">{children}</div>
      </ScrollArea>
    </>
  )

  if (!resizable) {
    return <aside className="discord-list">{column}</aside>
  }

  return (
    <ResizableColumn
      width={width}
      onWidthChange={setWidth}
      minWidth={minWidth}
      maxWidth={maxWidth}
      className="discord-list"
    >
      {column}
    </ResizableColumn>
  )
}

export function WelcomePane({ title, description }: { title: string; description: string }) {
  return (
    <div className="welcome-pane">
      <div className="welcome-pane-icon" aria-hidden />
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  )
}
