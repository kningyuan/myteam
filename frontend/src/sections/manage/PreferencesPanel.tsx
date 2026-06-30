import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { PreferencesLibraryPanel } from "@/components/manage/PreferencesLibraryPanel"
import { DiscordShell, ListColumn } from "@/components/layout/DiscordShell"
import { WorkspaceHeader } from "./WorkspaceHeader"

export function PreferencesPanel() {
  return (
    <DiscordShell
      list={
        <ListColumn title="管理" tabs={<ManageSegmentNav />} widthStorageKey="agentHub.manageListWidth">
          <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">
            团队偏好库在右侧编辑；全员 Agent 共用，不按成员分叉。
          </p>
        </ListColumn>
      }
    >
      <div className="discord-main-scroll workspace-scroll">
        <WorkspaceHeader
          title="偏好库"
          description="人类操作规则与交付标准；execute harness 注入全员 Agent，与 Agent 人设（IDENTITY/SOUL）分离。"
        />
        <PreferencesLibraryPanel />
      </div>
    </DiscordShell>
  )
}
