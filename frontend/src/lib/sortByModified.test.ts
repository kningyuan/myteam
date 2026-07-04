import { describe, it, expect } from "vitest"
import {
  toModifiedMs,
  modifiedMsOf,
  sortByModifiedDesc,
} from "@/lib/sortByModified"

describe("toModifiedMs", () => {
  it("空值归零", () => {
    expect(toModifiedMs(null)).toBe(0)
    expect(toModifiedMs(undefined)).toBe(0)
    expect(toModifiedMs("")).toBe(0)
  })

  it("毫秒级数字（>1e12）原样返回", () => {
    const ms = 1_700_000_000_000
    expect(toModifiedMs(ms)).toBe(ms)
  })

  it("秒级数字（<=1e12）乘 1000", () => {
    expect(toModifiedMs(1_700_000_000)).toBe(1_700_000_000_000)
  })

  it("0 / 负数 / NaN 归零", () => {
    expect(toModifiedMs(0)).toBe(0)
    expect(toModifiedMs(-100)).toBe(0)
    expect(toModifiedMs(NaN)).toBe(0)
    expect(toModifiedMs(Infinity)).toBe(0)
  })

  it("合法 ISO 字符串解析为毫秒", () => {
    expect(toModifiedMs("2024-01-01T00:00:00Z")).toBe(Date.parse("2024-01-01T00:00:00Z"))
  })

  it("非法字符串归零", () => {
    expect(toModifiedMs("not-a-date")).toBe(0)
  })
})

describe("modifiedMsOf", () => {
  it("取多字段中的最大值", () => {
    expect(
      modifiedMsOf({
        created_at: 1_700_000_000_000,
        updated_at: 1_700_000_001_000,
        operated_at: 1_700_000_000_500,
      }),
    ).toBe(1_700_000_001_000)
  })

  it("全空字段返回 0", () => {
    expect(modifiedMsOf({})).toBe(0)
  })
})

describe("sortByModifiedDesc", () => {
  it("按修改时间倒序（最新在前）", () => {
    const items = [
      { id: "old", updated_at: 1_000 },
      { id: "new", updated_at: 3_000 },
      { id: "mid", updated_at: 2_000 },
    ]
    const sorted = sortByModifiedDesc(items).map((i) => i.id)
    expect(sorted).toEqual(["new", "mid", "old"])
  })

  it("不修改原数组", () => {
    const items = [{ id: "a", updated_at: 1 }, { id: "b", updated_at: 2 }]
    const snapshot = items.map((i) => i.id)
    sortByModifiedDesc(items)
    expect(items.map((i) => i.id)).toEqual(snapshot)
  })
})
