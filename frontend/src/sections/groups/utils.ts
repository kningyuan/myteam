import { agentDisplayName } from "@/lib/chat/agentLabels"

export const GROUP_CHAT_INPUT_MIN = 120
export const GROUP_CHAT_INPUT_MAX = 240

/** 根据 @ 过滤候选成员（含 all），最多返回 8 个 */
export function filterMentions(
  members: string[],
  lookup: Map<string, string>,
  filter: string,
) {
  const pool = ["all", ...members.filter((m) => m !== "user")]
  const f = filter.toLowerCase()
  return pool
    .filter((m) => {
      if (m === "all") return !f || "all".includes(f)
      const label = agentDisplayName(m, lookup)
      return m.toLowerCase().includes(f) || label.toLowerCase().includes(f)
    })
    .slice(0, 8)
}
