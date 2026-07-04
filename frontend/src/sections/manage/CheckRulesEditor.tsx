import { useEffect, useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { listCheckConstraints, type CheckConstraintMeta, type CheckRules } from "@/lib/api/workflows"

/**
 * 质量约束可视化编辑器（全集驱动，非写死）。
 *
 * 从后端 GET /api/delivery-templates/constraints 拉取 Gate 可用约束全集（CHECK_REGISTRY），
 * 按 group（A 存在性 / B 对比矩阵 / C 数据可信 / D 维度覆盖）分组渲染。
 * 用户勾选/填值配置，所见即所验——UI 能配的 = Gate 真验的。
 * 详见 docs/quality-constraint-design.md 第七章。
 */

const GROUP_LABEL: Record<string, string> = {
  A: "存在性",
  B: "对比矩阵",
  C: "数据可信",
  D: "维度覆盖",
}

// 每组的一句白话说明，让普通人看懂这组约束是干嘛的、什么任务用
const GROUP_HINT: Record<string, string> = {
  A: "必备章节与防占位，所有任务都适用",
  B: "结构化对比表格，仅调研/分析类需要",
  C: "量化数据要标来源，仅带数据的文档适用",
  D: "指定维度词必须覆盖，仅调研/分析类需要",
}

export function CheckRulesEditor({
  value,
  onChange,
  outcomeKind = "artifact",
}: {
  value: CheckRules
  onChange: (next: CheckRules) => void
  /** 模板所属 task_type 的 outcome_kind；用于按族过滤可见约束。默认 artifact（显示全集）。 */
  outcomeKind?: string
}) {
  const [constraints, setConstraints] = useState<CheckConstraintMeta[]>([])

  useEffect(() => {
    listCheckConstraints()
      .then(setConstraints)
      .catch(() => setConstraints([]))
  }, [])

  const updateBool = (key: string, v: boolean) => onChange({ ...value, [key]: v })
  const updateInt = (key: string, raw: string) => {
    if (raw.trim() === "") {
      const next = { ...value }
      delete next[key]
      onChange(next)
      return
    }
    const n = Number(raw)
    if (!Number.isNaN(n)) onChange({ ...value, [key]: n })
  }
  const updateStr = (key: string, v: string) => {
    if (v.trim() === "") {
      const next = { ...value }
      delete next[key]
      onChange(next)
      return
    }
    onChange({ ...value, [key]: v })
  }
  const updateList = (key: string, raw: string) => {
    const items = raw
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (items.length === 0) {
      const next = { ...value }
      delete next[key]
      onChange(next)
      return
    }
    onChange({ ...value, [key]: items })
  }

  const listVal = (key: string): string =>
    Array.isArray(value[key]) ? (value[key] as string[]).join(", ") : String(value[key] ?? "")

  // 按族过滤：applies 为空=全通用；否则仅当 outcomeKind 命中才显示
  const visible = constraints.filter(
    (c) => !c.applies || c.applies.length === 0 || c.applies.includes(outcomeKind),
  )

  // 按组分组
  const groups = ["A", "B", "C", "D"]
  const byGroup = (g: string) => visible.filter((c) => c.group === g)

  return (
    <div className="grid gap-4">
      <p className="text-xs text-[var(--color-muted-foreground)]">
        按任务产出类型（{outcomeKind}）过滤可见约束。勾选即生效（Gate 机器判）。不同模板可配不同约束。
      </p>
      {groups.map((g, gi) => {
        const items = byGroup(g)
        if (!items.length) return null
        return (
          <div key={g}>
            {gi > 0 && <Separator className="my-3" />}
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted-foreground)]">
              {GROUP_LABEL[g] || g}
            </h4>
            {GROUP_HINT[g] && (
              <p className="mb-2 text-xs text-[var(--color-muted-foreground)]">{GROUP_HINT[g]}</p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {items.map((c) => {
                if (c.type === "bool") {
                  const checked = Boolean(value[c.key])
                  return (
                    <label
                      key={c.key}
                      className="flex items-start gap-2 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]"
                        checked={checked}
                        onChange={(e) => updateBool(c.key, e.target.checked)}
                      />
                      <span>
                        <span className="font-medium">{c.label}</span>
                        {c.hint && (
                          <span className="block text-xs text-[var(--color-muted-foreground)]">{c.hint}</span>
                        )}
                      </span>
                    </label>
                  )
                }
                if (c.type === "int") {
                  return (
                    <div key={c.key} className="grid gap-1.5">
                      <Label>{c.label}</Label>
                      <Input
                        type="number"
                        min={0}
                        value={typeof value[c.key] === "number" ? String(value[c.key]) : ""}
                        placeholder="（不限制）"
                        onChange={(e) => updateInt(c.key, e.target.value)}
                      />
                    </div>
                  )
                }
                if (c.type === "str") {
                  return (
                    <div key={c.key} className="grid gap-1.5">
                      <Label>{c.label}</Label>
                      <Input
                        value={typeof value[c.key] === "string" ? (value[c.key] as string) : ""}
                        placeholder={c.hint || ""}
                        onChange={(e) => updateStr(c.key, e.target.value)}
                      />
                    </div>
                  )
                }
                // list
                return (
                  <div key={c.key} className="grid gap-1.5 sm:col-span-2">
                    <Label>{c.label}</Label>
                    <Input value={listVal(c.key)} onChange={(e) => updateList(c.key, e.target.value)} />
                    {c.hint && (
                      <span className="text-xs text-[var(--color-muted-foreground)]">{c.hint}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
