import { DiscordShell, WelcomePane } from "@/components/layout/DiscordShell"

export function DashboardPage() {
  return (
    <DiscordShell>
      <div className="discord-main-scroll">
        <WelcomePane
          title="myteam Agent Hub"
          description="dashboard / agent management / groups / observability"
        />
      </div>
    </DiscordShell>
  )
}
