import type { SettingsSectionId } from "@/sections/SettingsSection"
import {
  SystemSettingsPanel,
  CollabSettingsPanel,
  GroupSettingsPanel,
  ExecSettingsPanel,
  ProjectSettingsPanel,
  QualitySettingsPanel,
} from "@/components/settings/SettingsPanels"

const panels: Record<SettingsSectionId, React.ElementType | null> = {
  system: SystemSettingsPanel,
  collab: CollabSettingsPanel,
  group: GroupSettingsPanel,
  exec: ExecSettingsPanel,
  project: ProjectSettingsPanel,
  quality: QualitySettingsPanel,
}

export function SettingsPage({ section }: { section: SettingsSectionId }) {
  const Panel = panels[section]
  if (!Panel) {
    return (
      <div className="p-6 text-sm text-[var(--color-muted-foreground)]">
        未知设置项：{section}
      </div>
    )
  }
  return <Panel />
}
