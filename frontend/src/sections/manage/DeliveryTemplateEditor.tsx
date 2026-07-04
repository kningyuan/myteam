import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import {
  getDeliveryTemplate,
  saveDeliveryTemplate,
  type CheckRules,
  type DeliveryTemplateSummary,
} from "@/lib/api/workflows"
import { CheckRulesEditor } from "./CheckRulesEditor"

/**
 * 单个交付模板的可视化编辑器：模板结构（章节）+ 质量约束（check_rules）。
 * 保存走 saveDeliveryTemplate（全量覆盖 body：含 deliverable_template + check_rules + 元信息）。
 * YAML 文本区作为兜底，保留老「编辑 YAML」能力。
 */
export function DeliveryTemplateEditor({
  template,
  outcomeKind,
  onSaved,
  onDelete,
}: {
  template: DeliveryTemplateSummary
  outcomeKind?: string
  onSaved?: () => void
  onDelete?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sections, setSections] = useState("")
  const [checkRules, setCheckRules] = useState<CheckRules>({})
  const [yamlText, setYamlText] = useState("")
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!expanded || loaded) return
    setLoaded(true)
    getDeliveryTemplate(template.id)
      .then((detail) => {
        setSections(
          (detail.sections || [])
            .map((s) => (typeof s === "string" ? s : s.name || ""))
            .filter(Boolean)
            .join(", "),
        )
        setCheckRules(detail.check_rules || {})
        setYamlText(detail.yaml || "")
      })
      .catch(() => {})
  }, [expanded, loaded, template.id])

  async function handleSave() {
    setBusy(true)
    try {
      const sectionNames = sections
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean)
      const body: Record<string, unknown> = {
        id: template.id,
        display_name: template.display_name || template.id,
        description: template.description || "",
        task_types: template.task_types || [],
        required_sections: sectionNames,
        check_rules: checkRules,
      }
      await saveDeliveryTemplate(template.id, body)
      toast.success("模板已保存")
      onSaved?.()
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveYaml() {
    setBusy(true)
    try {
      await saveDeliveryTemplate(template.id, { yaml: yamlText })
      toast.success("YAML 已保存")
      // 重新加载解析态
      const detail = await getDeliveryTemplate(template.id)
      setSections(
        (detail.sections || [])
          .map((s) => (typeof s === "string" ? s : s.name || ""))
          .filter(Boolean)
          .join(", "),
      )
      setCheckRules(detail.check_rules || {})
      onSaved?.()
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-md border border-[var(--color-border)]">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">
            {template.display_name || template.id}
          </div>
          <div className="truncate font-mono text-xs text-[var(--color-muted-foreground)]">
            {template.id}
            {template.default_for ? ` · 默认(${template.default_for})` : ""}
          </div>
        </div>
        <span className="text-xs text-[var(--color-muted-foreground)]">
          {expanded ? "收起" : "展开编辑"}
        </span>
      </button>

      {expanded && (
        <div className="grid gap-4 border-t border-[var(--color-border)] px-3 py-3">
          <div className="grid gap-1.5">
            <Label>章节（逗号分隔）</Label>
            <Input value={sections} onChange={(e) => setSections(e.target.value)} />
          </div>

          <Separator />

          <div>
            <h4 className="mb-2 text-sm font-semibold">质量约束（check_rules）</h4>
            <CheckRulesEditor value={checkRules} onChange={setCheckRules} outcomeKind={outcomeKind} />
          </div>

          <Separator />

          <div className="grid gap-1.5">
            <Label>YAML（兜底编辑，保存后回填上方可视化区）</Label>
            <Textarea
              rows={6}
              value={yamlText}
              onChange={(e) => setYamlText(e.target.value)}
              className="font-mono text-xs"
            />
          </div>

          <div className="flex flex-wrap justify-between gap-2">
            <Button size="sm" disabled={busy} onClick={() => void handleSave()}>
              保存可视化
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleSaveYaml()}>
              保存 YAML
            </Button>
            {onDelete && (
              <Button
                size="sm"
                variant="outline"
                onClick={onDelete}
                className="ml-auto"
              >
                删除模板
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
