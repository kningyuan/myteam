import { describe, it, expect } from "vitest"
import {
  parseGroupDiscussionSettings,
  primaryTerminateCommand,
  groupChatInputPlaceholder,
  effectiveGroupMaxRounds,
  DEFAULT_GROUP_DISCUSSION_SETTINGS,
} from "@/lib/chat/groupDiscussionSettings"

describe("parseGroupDiscussionSettings", () => {
  it("null/undefined 输入返回默认值", () => {
    expect(parseGroupDiscussionSettings(null)).toEqual(DEFAULT_GROUP_DISCUSSION_SETTINGS)
    expect(parseGroupDiscussionSettings(undefined)).toEqual(DEFAULT_GROUP_DISCUSSION_SETTINGS)
  })

  it("自定义值覆盖默认", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: {
        default_max_rounds: 5,
        max_rounds_cap: 20,
        roundtable_turn_timeout: 120,
      },
    })
    expect(s.defaultMaxRounds).toBe(5)
    expect(s.maxRoundsCap).toBe(20)
    expect(s.turnTimeoutSec).toBe(120)
  })

  it("default_max_rounds 为 0 时回退默认（falsy 触发 ||）", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: { default_max_rounds: 0 },
    })
    expect(s.defaultMaxRounds).toBe(DEFAULT_GROUP_DISCUSSION_SETTINGS.defaultMaxRounds)
  })

  it("quorum_ratio 越界（>1）回退默认", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: { quorum_ratio: 1.5 },
    })
    expect(s.quorumRatio).toBe(DEFAULT_GROUP_DISCUSSION_SETTINGS.quorumRatio)
  })

  it("合法 quorum_ratio 保留", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: { quorum_ratio: 0.8 },
    })
    expect(s.quorumRatio).toBe(0.8)
  })

  it("空 terminate_commands 数组回退默认", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: { terminate_commands: [] },
    })
    expect(s.terminateCommands).toEqual(DEFAULT_GROUP_DISCUSSION_SETTINGS.terminateCommands)
  })

  it("自定义 terminate_commands 保留并 trim", () => {
    const s = parseGroupDiscussionSettings({
      group_discussion: { terminate_commands: ["  /stop  ", "/end"] },
    })
    expect(s.terminateCommands).toEqual(["/stop", "/end"])
  })

  it("auto_finalize_on_max_rounds 显式 false 才为 false", () => {
    expect(
      parseGroupDiscussionSettings({ group_discussion: { auto_finalize_on_max_rounds: false } })
        .autoFinalizeOnMaxRounds,
    ).toBe(false)
    expect(parseGroupDiscussionSettings({}).autoFinalizeOnMaxRounds).toBe(true)
  })
})

describe("primaryTerminateCommand", () => {
  it("返回第一条终止命令", () => {
    expect(primaryTerminateCommand(DEFAULT_GROUP_DISCUSSION_SETTINGS)).toBe("/终止讨论")
  })

  it("空列表回退 /终止讨论", () => {
    expect(primaryTerminateCommand({ ...DEFAULT_GROUP_DISCUSSION_SETTINGS, terminateCommands: [] })).toBe(
      "/终止讨论",
    )
  })
})

describe("groupChatInputPlaceholder", () => {
  it("包含终止命令", () => {
    const p = groupChatInputPlaceholder(DEFAULT_GROUP_DISCUSSION_SETTINGS)
    expect(p).toContain("/终止讨论")
    expect(p).toContain("@all")
  })
})

describe("effectiveGroupMaxRounds", () => {
  const s = DEFAULT_GROUP_DISCUSSION_SETTINGS

  it("undefined 使用 defaultMaxRounds", () => {
    expect(effectiveGroupMaxRounds(undefined, s)).toBe(s.defaultMaxRounds)
  })

  it("超过 cap 时截断到 cap", () => {
    expect(effectiveGroupMaxRounds(999, s)).toBe(s.maxRoundsCap)
  })

  it("至少为 1", () => {
    expect(effectiveGroupMaxRounds(0, s)).toBe(1)
    expect(effectiveGroupMaxRounds(-5, s)).toBe(1)
  })

  it("合法值原样返回", () => {
    expect(effectiveGroupMaxRounds(4, s)).toBe(4)
  })
})
