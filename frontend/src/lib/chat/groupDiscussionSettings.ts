/** 全局群讨论配置 — 与 skill_config.group_discussion 对齐 */

export type GroupDiscussionSettings = {
  defaultMaxRounds: number
  maxRoundsCap: number
  turnTimeoutSec: number
  quorumRatio: number
  autoFinalizeOnMaxRounds: boolean
  allowRoundExtension: boolean
  killCliOnCancel: boolean
  terminateCommands: string[]
}

export const DEFAULT_GROUP_DISCUSSION_SETTINGS: GroupDiscussionSettings = {
  defaultMaxRounds: 3,
  maxRoundsCap: 50,
  turnTimeoutSec: 300,
  quorumRatio: 0.667,
  autoFinalizeOnMaxRounds: true,
  allowRoundExtension: true,
  killCliOnCancel: true,
  terminateCommands: ["/终止讨论", "/终止圆桌", "/stop roundtable"],
}

export function parseGroupDiscussionSettings(
  skill: Record<string, unknown> | null | undefined,
): GroupDiscussionSettings {
  const gd = (skill?.group_discussion || {}) as Record<string, unknown>
  const cmds = gd.terminate_commands
  const terminateCommands =
    Array.isArray(cmds) && cmds.length
      ? cmds.map(String).map((s) => s.trim()).filter(Boolean)
      : DEFAULT_GROUP_DISCUSSION_SETTINGS.terminateCommands

  const quorumRaw = Number(gd.quorum_ratio ?? DEFAULT_GROUP_DISCUSSION_SETTINGS.quorumRatio)

  return {
    defaultMaxRounds: Math.max(1, Number(gd.default_max_rounds) || DEFAULT_GROUP_DISCUSSION_SETTINGS.defaultMaxRounds),
    maxRoundsCap: Math.max(1, Number(gd.max_rounds_cap) || DEFAULT_GROUP_DISCUSSION_SETTINGS.maxRoundsCap),
    turnTimeoutSec: Math.max(60, Number(gd.roundtable_turn_timeout) || DEFAULT_GROUP_DISCUSSION_SETTINGS.turnTimeoutSec),
    quorumRatio:
      Number.isFinite(quorumRaw) && quorumRaw > 0 && quorumRaw <= 1
        ? quorumRaw
        : DEFAULT_GROUP_DISCUSSION_SETTINGS.quorumRatio,
    autoFinalizeOnMaxRounds: gd.auto_finalize_on_max_rounds !== false,
    allowRoundExtension: gd.allow_round_extension !== false,
    killCliOnCancel: gd.kill_cli_on_cancel !== false,
    terminateCommands,
  }
}

export function primaryTerminateCommand(settings: GroupDiscussionSettings): string {
  return settings.terminateCommands[0] || "/终止讨论"
}

export function groupChatInputPlaceholder(settings: GroupDiscussionSettings): string {
  const term = primaryTerminateCommand(settings)
  return `@all 发起圆桌；@Agent 群聊；${term} 停止后台讨论（Enter 发送）`
}

export function effectiveGroupMaxRounds(
  groupMaxRounds: number | undefined,
  settings: GroupDiscussionSettings,
): number {
  const raw = groupMaxRounds ?? settings.defaultMaxRounds
  return Math.max(1, Math.min(raw, settings.maxRoundsCap))
}
