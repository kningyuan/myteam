import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Cpu, Layers, MessageCircle, Settings2, Users } from "lucide-react"
import { SettingsPage } from "@/pages/SettingsPage"
import { DiscordShell, ListColumn } from "@/components/layout/DiscordShell"
import { ListNavItem } from "@/components/layout/ListNavItem"

const sections = [
  { id: "system", label: "系统", icon: Settings2, description: "Hub 与 AI 后端" },
  { id: "collab", label: "协作", icon: Users, description: "通知与项目群" },
  { id: "group", label: "群配置", icon: MessageCircle, description: "@all 圆桌讨论" },
  { id: "exec", label: "执行", icon: Cpu, description: "超时与重试" },
  { id: "project", label: "项目", icon: Layers, description: "预算与并行" },
] as const

export type SettingsSectionId = (typeof sections)[number]["id"]

export function SettingsSection() {
  const { section } = useParams()
  const navigate = useNavigate()
  const active = (section as SettingsSectionId) || "system"

  useEffect(() => {
    if (!section) navigate("/settings/system", { replace: true })
  }, [section, navigate])

  return (
    <DiscordShell
      list={
        <ListColumn title="设置" widthStorageKey="agentHub.settingsListWidth">
          {sections.map((s) => (
            <ListNavItem
              key={s.id}
              to={`/settings/${s.id}`}
              icon={s.icon}
              label={s.label}
              description={s.description}
            />
          ))}
        </ListColumn>
      }
    >
      <div className="discord-main-scroll workspace-scroll">
        <SettingsPage section={active} />
      </div>
    </DiscordShell>
  )
}
