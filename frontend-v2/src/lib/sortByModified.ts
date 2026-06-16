/** 将各类时间字段统一为毫秒时间戳，用于「最近修改在前」排序。 */
export function toModifiedMs(value: unknown): number {
  if (value == null || value === "") return 0
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) return 0
    return value > 1e12 ? value : value * 1000
  }
  const parsed = Date.parse(String(value))
  return Number.isNaN(parsed) ? 0 : parsed
}

/** 从条目常见字段中取最大时间作为「修改时间」。 */
export function modifiedMsOf(item: Record<string, unknown>): number {
  const fields = [
    item.updated_at,
    item.operated_at,
    item.last_message_at,
    item.hidden_at,
    item.created_at,
  ]
  return Math.max(0, ...fields.map(toModifiedMs))
}

/** 按修改时间倒序（最新在上）。 */
export function sortByModifiedDesc<T>(items: T[]): T[] {
  return [...items].sort(
    (a, b) =>
      modifiedMsOf(b as Record<string, unknown>) - modifiedMsOf(a as Record<string, unknown>),
  )
}
