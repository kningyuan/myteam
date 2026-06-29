import type { SettingsSectionId } from "@/sections/SettingsSection"
import { Separator } from "@/components/ui/separator"

function SettingSection({ title, description, id }: { title: string; id: SettingsSectionId; description: string }) {
  return (
    <div className="workspace-panel">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{description}</p>
      <Separator className="my-5" />
      <p className="text-sm text-[var(--color-muted-foreground)]">
        设置项 {id} 正在建设中。
      </p>
    </div>
  )
}

export function SystemSettingsPanel() {
  return (
    <SettingSection
      title="系统设置"
      id="system"
      description="Hub 与 AI 后端的全局配置（端口、后端列表、默认模型）"
    />
  )
}

export function CollabSettingsPanel() {
  return (
    <SettingSection
      title="协作设置"
      id="collab"
      description="通知方式、项目群组、@mention 路由"
    />
  )
}

export function GroupSettingsPanel() {
  return (
    <SettingSection
      title="群配置"
      id="group"
      description="@all 圆桌讨论与跨角色评审设置"
    />
  )
}

export function ExecSettingsPanel() {
  return (
    <SettingSection
      title="执行设置"
      id="exec"
      description="任务超时、重试策略、并行度控制"
    />
  )
}

export function ProjectSettingsPanel() {
  return (
    <SettingSection
      title="项目设置"
      id="project"
      description="项目预算、最大并行任务数"
    />
  )
}

export function QualitySettingsPanel() {
  return (
    <SettingSection
      title="执行质量设置"
      id="quality"
      description="Harness 注入、Memstack 记忆栈配置"
    />
  )
}