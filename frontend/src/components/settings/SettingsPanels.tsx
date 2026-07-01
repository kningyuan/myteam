import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  getConfig,
  getSkillConfig,
  patchConfig,
  patchSkillConfig,
} from "@/lib/api/config"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"

type Cfg = Record<string, any>

// -------------------- 通用工具 --------------------

/** 按路径取值，找不到返回 fallback。 */
function get(obj: any, path: string[], fallback: any = ""): any {
  let cur = obj
  for (const k of path) {
    if (cur == null || typeof cur !== "object") return fallback
    cur = cur[k]
  }
  return cur === undefined ? fallback : cur
}

/** 不可变地按路径写入，返回新对象。 */
function setIn(obj: Cfg, path: string[], value: any): Cfg {
  const [head, ...rest] = path
  if (rest.length === 0) {
    return { ...obj, [head]: value }
  }
  return { ...obj, [head]: setIn(obj[head] ?? {}, rest, value) }
}

function jsonEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

function arrToText(arr: any): string {
  return Array.isArray(arr) ? arr.join("\n") : ""
}

function textToArr(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean)
}

// -------------------- 表单原语 --------------------

function PanelShell({
  title,
  description,
  loading,
  saving,
  dirty,
  onSave,
  children,
  footer,
}: {
  title: string
  description: string
  loading: boolean
  saving: boolean
  dirty: boolean
  onSave: () => void
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  if (loading) {
    return (
      <div className="workspace-panel">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{description}</p>
        <Separator className="my-5" />
        <p className="text-sm text-[var(--color-muted-foreground)]">加载中…</p>
      </div>
    )
  }
  return (
    <div className="workspace-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{description}</p>
        </div>
        <Button size="sm" disabled={!dirty || saving} onClick={onSave}>
          {saving ? "保存中…" : "保存"}
        </Button>
      </div>
      <Separator className="my-5" />
      <div className="grid gap-4">{children}</div>
      {footer}
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
      {hint ? (
        <p className="text-xs text-[var(--color-muted-foreground)]">{hint}</p>
      ) : null}
    </div>
  )
}

function TextRow({
  label,
  hint,
  value,
  onChange,
  placeholder,
}: {
  label: string
  hint?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <Field label={label} hint={hint}>
      <Input
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </Field>
  )
}

function NumRow({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <Field label={label} hint={hint}>
      <Input
        type="number"
        value={value ?? 0}
        onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
      />
    </Field>
  )
}

function BoolRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string
  hint?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <input
        type="checkbox"
        className="mt-0.5 shrink-0"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="font-medium">{label}</span>
        {hint ? (
          <span className="block text-xs text-[var(--color-muted-foreground)]">{hint}</span>
        ) : null}
      </span>
    </label>
  )
}

function ArrayRow({
  label,
  hint,
  value,
  onChange,
  placeholder,
  rows = 5,
}: {
  label: string
  hint?: string
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
  rows?: number
}) {
  // 本地文本状态在挂载时由 value 播种；Panel 仅在加载完成后渲染表单，故播种值正确。
  const [text, setText] = useState(() => arrToText(value))
  return (
    <Field label={label} hint={hint ?? "每行一项"}>
      <Textarea
        rows={rows}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          onChange(textToArr(e.target.value))
        }}
        placeholder={placeholder}
        className="font-mono text-xs"
      />
    </Field>
  )
}

function SubGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)]/40 p-4">
      <p className="mb-3 text-sm font-semibold text-[var(--color-foreground)]">{title}</p>
      <div className="grid gap-3">{children}</div>
    </div>
  )
}

// -------------------- 1. 系统配置 --------------------

export function SystemSettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initial, setInitial] = useState<Cfg>({})
  const [draft, setDraft] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    getConfig()
      .then((cfg) => {
        const slice: Cfg = {
          system: cfg.system ?? {},
          backends: cfg.backends ?? {},
        }
        setDraft(slice)
        setInitial(slice)
      })
      .catch((e: Error) => toast.error("加载系统配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirty = !jsonEqual(draft, initial)
  function update(path: string[], value: any) {
    setDraft((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await patchConfig(draft)
      setInitial(draft)
      toast.success("系统配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="系统设置"
      description="Hub 与 AI 后端的全局配置（端口、后端列表、默认模型）"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
    >
      <SubGroup title="基础">
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="Hub 端口"
            value={get(draft, ["system", "port"], 0)}
            onChange={(v) => update(["system", "port"], v)}
          />
          <TextRow
            label="默认后端"
            value={get(draft, ["system", "default_backend"], "")}
            onChange={(v) => update(["system", "default_backend"], v)}
            placeholder="opencode / claude"
          />
        </div>
        <TextRow
          label="默认模型"
          value={get(draft, ["system", "default_model"], "")}
          onChange={(v) => update(["system", "default_model"], v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <TextRow
            label="协调者 Agent ID"
            value={get(draft, ["system", "coordinator_agent_id"], "")}
            onChange={(v) => update(["system", "coordinator_agent_id"], v)}
          />
          <TextRow
            label="副协调者 Agent ID"
            value={get(draft, ["system", "deputy_agent_id"], "")}
            onChange={(v) => update(["system", "deputy_agent_id"], v)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="每 Mtok 价格"
            hint="用于成本核算"
            value={get(draft, ["system", "price_per_mtok"], 0)}
            onChange={(v) => update(["system", "price_per_mtok"], v)}
          />
          <NumRow
            label="审计日志最大字节"
            value={get(draft, ["system", "audit_log_max_bytes"], 0)}
            onChange={(v) => update(["system", "audit_log_max_bytes"], v)}
          />
        </div>
      </SubGroup>

      <SubGroup title="行为开关">
        <BoolRow
          label="调试模式"
          checked={get(draft, ["system", "debug"], false)}
          onChange={(v) => update(["system", "debug"], v)}
        />
        <BoolRow
          label="默认启用 review"
          checked={get(draft, ["system", "default_review"], false)}
          onChange={(v) => update(["system", "default_review"], v)}
        />
        <BoolRow
          label="审计日志"
          checked={get(draft, ["system", "audit_log"], false)}
          onChange={(v) => update(["system", "audit_log"], v)}
        />
        <BoolRow
          label="使用 SQLite 项目存储"
          checked={get(draft, ["system", "use_sqlite_project_store"], false)}
          onChange={(v) => update(["system", "use_sqlite_project_store"], v)}
        />
        <BoolRow
          label="outcome_kind 检测"
          checked={get(draft, ["system", "use_outcome_kind_detection"], false)}
          onChange={(v) => update(["system", "use_outcome_kind_detection"], v)}
        />
        <BoolRow
          label="严格 must_include 配置"
          checked={get(draft, ["system", "use_strict_must_include_config"], false)}
          onChange={(v) => update(["system", "use_strict_must_include_config"], v)}
        />
        <BoolRow
          label="可观测性走 KB 后端"
          checked={get(draft, ["system", "use_kb_backend_for_observability"], false)}
          onChange={(v) => update(["system", "use_kb_backend_for_observability"], v)}
        />
      </SubGroup>

      <SubGroup title="标记与扩展名">
        <ArrayRow
          label="占位标记（placeholder_markers）"
          hint="出现这些标记视为未完成"
          value={get(draft, ["system", "placeholder_markers"], [])}
          onChange={(v) => update(["system", "placeholder_markers"], v)}
          placeholder="待补充&#10;todo"
        />
        <ArrayRow
          label="屏蔽标记（blocked_markers）"
          hint="出现这些标记视为抓取受阻"
          value={get(draft, ["system", "blocked_markers"], [])}
          onChange={(v) => update(["system", "blocked_markers"], v)}
          placeholder="signin&#10;captcha"
        />
        <ArrayRow
          label="代码扩展名（code_extensions）"
          value={get(draft, ["system", "code_extensions"], [])}
          onChange={(v) => update(["system", "code_extensions"], v)}
          placeholder=".py&#10;.ts"
        />
      </SubGroup>

      <SubGroup title="规则文件名（rules.profile_filenames）">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextRow
            label="interactive"
            value={get(draft, ["system", "rules", "profile_filenames", "interactive"], "")}
            onChange={(v) =>
              update(["system", "rules", "profile_filenames", "interactive"], v)
            }
          />
          <TextRow
            label="discussion"
            value={get(draft, ["system", "rules", "profile_filenames", "discussion"], "")}
            onChange={(v) =>
              update(["system", "rules", "profile_filenames", "discussion"], v)
            }
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextRow
            label="workflow_execute"
            value={get(draft, ["system", "rules", "profile_filenames", "workflow_execute"], "")}
            onChange={(v) =>
              update(["system", "rules", "profile_filenames", "workflow_execute"], v)
            }
          />
          <TextRow
            label="ethos"
            value={get(draft, ["system", "rules", "profile_filenames", "ethos"], "")}
            onChange={(v) =>
              update(["system", "rules", "profile_filenames", "ethos"], v)
            }
          />
        </div>
      </SubGroup>

      <SubGroup title="后端">
        <div className="grid gap-3 sm:grid-cols-2">
          <BoolRow
            label="opencode 启用"
            checked={get(draft, ["backends", "opencode", "enabled"], false)}
            onChange={(v) => update(["backends", "opencode", "enabled"], v)}
          />
          <BoolRow
            label="claude 启用"
            checked={get(draft, ["backends", "claude", "enabled"], false)}
            onChange={(v) => update(["backends", "claude", "enabled"], v)}
          />
        </div>
        <TextRow
          label="opencode CLI 路径"
          value={get(draft, ["backends", "opencode", "cli_path"], "")}
          onChange={(v) => update(["backends", "opencode", "cli_path"], v)}
          placeholder="留空使用默认 ~/.opencode/bin/opencode"
        />
        <TextRow
          label="claude CLI 路径"
          value={get(draft, ["backends", "claude", "cli_path"], "")}
          onChange={(v) => update(["backends", "claude", "cli_path"], v)}
          placeholder="claude 可执行文件路径"
        />
      </SubGroup>
    </PanelShell>
  )
}

// -------------------- 2. 协作配置 --------------------

export function CollabSettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initial, setInitial] = useState<Cfg>({})
  const [draft, setDraft] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    getSkillConfig()
      .then((cfg) => {
        const slice: Cfg = {
          notifications: cfg.notifications ?? {},
          hub: cfg.hub ?? {},
          auto_group: cfg.auto_group ?? {},
        }
        setDraft(slice)
        setInitial(slice)
      })
      .catch((e: Error) => toast.error("加载协作配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirty = !jsonEqual(draft, initial)
  function update(path: string[], value: any) {
    setDraft((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await patchSkillConfig(draft)
      setInitial(draft)
      toast.success("协作配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="协作设置"
      description="通知方式、自动建群、Hub 地址"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
    >
      <SubGroup title="通知">
        <BoolRow
          label="启用 Telegram 通知"
          checked={get(draft, ["notifications", "enable_telegram"], false)}
          onChange={(v) => update(["notifications", "enable_telegram"], v)}
        />
        <BoolRow
          label="使用项目群发送通知"
          checked={get(draft, ["notifications", "use_project_group"], false)}
          onChange={(v) => update(["notifications", "use_project_group"], v)}
        />
      </SubGroup>

      <SubGroup title="Hub">
        <TextRow
          label="Hub URL"
          value={get(draft, ["hub", "url"], "")}
          onChange={(v) => update(["hub", "url"], v)}
          placeholder="http://127.0.0.1:8765"
        />
      </SubGroup>

      <SubGroup title="自动建群">
        <BoolRow
          label="启用自动建群"
          checked={get(draft, ["auto_group", "enabled"], false)}
          onChange={(v) => update(["auto_group", "enabled"], v)}
        />
        <BoolRow
          label="包含 main（协调者）"
          checked={get(draft, ["auto_group", "include_main"], false)}
          onChange={(v) => update(["auto_group", "include_main"], v)}
        />
        <TextRow
          label="群名前缀"
          value={get(draft, ["auto_group", "name_prefix"], "")}
          onChange={(v) => update(["auto_group", "name_prefix"], v)}
          placeholder="留空使用默认前缀"
        />
      </SubGroup>
    </PanelShell>
  )
}

// -------------------- 3. 群组配置 --------------------

export function GroupSettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initial, setInitial] = useState<Cfg>({})
  const [draft, setDraft] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    getSkillConfig()
      .then((cfg) => {
        const slice: Cfg = {
          group_discussion: cfg.group_discussion ?? {},
        }
        setDraft(slice)
        setInitial(slice)
      })
      .catch((e: Error) => toast.error("加载群组配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirty = !jsonEqual(draft, initial)
  function update(path: string[], value: any) {
    setDraft((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await patchSkillConfig(draft)
      setInitial(draft)
      toast.success("群组配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="群配置"
      description="@all 圆桌讨论的轮次、法定人数与终止指令"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
      footer={
        <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
          群组成员随群组创建时设定，请在
          <a href="/v2/groups" className="mx-1 underline">群组管理</a>
          页操作。
        </p>
      }
    >
      <SubGroup title="轮次">
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="默认最大轮数"
            value={get(draft, ["group_discussion", "default_max_rounds"], 0)}
            onChange={(v) => update(["group_discussion", "default_max_rounds"], v)}
          />
          <NumRow
            label="轮数上限（硬顶）"
            value={get(draft, ["group_discussion", "max_rounds_cap"], 0)}
            onChange={(v) => update(["group_discussion", "max_rounds_cap"], v)}
          />
        </div>
        <NumRow
          label="单轮发言超时（秒）"
          value={get(draft, ["group_discussion", "roundtable_turn_timeout"], 0)}
          onChange={(v) => update(["group_discussion", "roundtable_turn_timeout"], v)}
        />
        <NumRow
          label="法定人数比例"
          hint="0~1 之间，例如 0.667"
          value={get(draft, ["group_discussion", "quorum_ratio"], 0)}
          onChange={(v) => update(["group_discussion", "quorum_ratio"], v)}
        />
      </SubGroup>

      <SubGroup title="行为开关">
        <BoolRow
          label="达到最大轮数时自动收尾"
          checked={get(draft, ["group_discussion", "auto_finalize_on_max_rounds"], false)}
          onChange={(v) => update(["group_discussion", "auto_finalize_on_max_rounds"], v)}
        />
        <BoolRow
          label="允许轮次延伸"
          checked={get(draft, ["group_discussion", "allow_round_extension"], false)}
          onChange={(v) => update(["group_discussion", "allow_round_extension"], v)}
        />
        <BoolRow
          label="取消时 kill CLI"
          checked={get(draft, ["group_discussion", "kill_cli_on_cancel"], false)}
          onChange={(v) => update(["group_discussion", "kill_cli_on_cancel"], v)}
        />
      </SubGroup>

      <SubGroup title="终止指令">
        <ArrayRow
          label="终止指令（terminate_commands）"
          value={get(draft, ["group_discussion", "terminate_commands"], [])}
          onChange={(v) => update(["group_discussion", "terminate_commands"], v)}
          placeholder="/终止讨论&#10;/stop roundtable"
        />
      </SubGroup>
    </PanelShell>
  )
}

// -------------------- 4. 执行配置 --------------------

export function ExecSettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initial, setInitial] = useState<Cfg>({})
  const [draft, setDraft] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    getSkillConfig()
      .then((cfg) => {
        const slice: Cfg = {
          executor: cfg.executor ?? {},
        }
        setDraft(slice)
        setInitial(slice)
      })
      .catch((e: Error) => toast.error("加载执行配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirty = !jsonEqual(draft, initial)
  function update(path: string[], value: any) {
    setDraft((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await patchSkillConfig(draft)
      setInitial(draft)
      toast.success("执行配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="执行设置"
      description="任务超时、轮询间隔、重试次数"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
    >
      <SubGroup title="轮询与超时（秒）">
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="轮询间隔"
            value={get(draft, ["executor", "poll_interval"], 0)}
            onChange={(v) => update(["executor", "poll_interval"], v)}
          />
          <NumRow
            label="ACK 超时"
            value={get(draft, ["executor", "ack_timeout"], 0)}
            onChange={(v) => update(["executor", "ack_timeout"], v)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="任务超时"
            value={get(draft, ["executor", "task_timeout"], 0)}
            onChange={(v) => update(["executor", "task_timeout"], v)}
          />
          <NumRow
            label="team_config 超时"
            value={get(draft, ["executor", "team_config_timeout"], 0)}
            onChange={(v) => update(["executor", "team_config_timeout"], v)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="task_plan 超时"
            value={get(draft, ["executor", "task_plan_timeout"], 0)}
            onChange={(v) => update(["executor", "task_plan_timeout"], v)}
          />
          <NumRow
            label="agent_msg 超时"
            value={get(draft, ["executor", "agent_msg_timeout"], 0)}
            onChange={(v) => update(["executor", "agent_msg_timeout"], v)}
          />
        </div>
      </SubGroup>

      <SubGroup title="重试">
        <NumRow
          label="最大重试次数"
          value={get(draft, ["executor", "max_retries"], 0)}
          onChange={(v) => update(["executor", "max_retries"], v)}
        />
      </SubGroup>
    </PanelShell>
  )
}

// -------------------- 5. 项目配置 --------------------

export function ProjectSettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initial, setInitial] = useState<Cfg>({})
  const [draft, setDraft] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    getSkillConfig()
      .then((cfg) => {
        const slice: Cfg = {
          process_defaults: cfg.process_defaults ?? {},
        }
        setDraft(slice)
        setInitial(slice)
      })
      .catch((e: Error) => toast.error("加载项目配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirty = !jsonEqual(draft, initial)
  function update(path: string[], value: any) {
    setDraft((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await patchSkillConfig(draft)
      setInitial(draft)
      toast.success("项目配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="项目设置"
      description="项目预算、并行度、空闲与拆分策略"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
    >
      <SubGroup title="预算">
        <NumRow
          label="默认项目预算（token）"
          value={get(draft, ["process_defaults", "default_project_budget"], 0)}
          onChange={(v) => update(["process_defaults", "default_project_budget"], v)}
        />
        <NumRow
          label="预算降级阈值"
          hint="0~1 之间，例如 0.8"
          value={get(draft, ["process_defaults", "budget_degrade_threshold"], 0)}
          onChange={(v) => update(["process_defaults", "budget_degrade_threshold"], v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <TextRow
            label="降级后端"
            value={get(draft, ["process_defaults", "budget_degrade_backend"], "")}
            onChange={(v) => update(["process_defaults", "budget_degrade_backend"], v)}
            placeholder="留空不降级后端"
          />
          <TextRow
            label="降级模型"
            value={get(draft, ["process_defaults", "budget_degrade_model"], "")}
            onChange={(v) => update(["process_defaults", "budget_degrade_model"], v)}
            placeholder="留空不降级模型"
          />
        </div>
      </SubGroup>

      <SubGroup title="并行与并发">
        <BoolRow
          label="启用并行任务"
          checked={get(draft, ["process_defaults", "parallel_enabled"], false)}
          onChange={(v) => update(["process_defaults", "parallel_enabled"], v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="最大并行任务数"
            value={get(draft, ["process_defaults", "max_parallel"], 0)}
            onChange={(v) => update(["process_defaults", "max_parallel"], v)}
          />
          <NumRow
            label="最大并发项目数"
            value={get(draft, ["process_defaults", "max_concurrent_projects"], 0)}
            onChange={(v) => update(["process_defaults", "max_concurrent_projects"], v)}
          />
        </div>
      </SubGroup>

      <SubGroup title="循环与空闲">
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="最大循环数"
            value={get(draft, ["process_defaults", "max_cycles"], 0)}
            onChange={(v) => update(["process_defaults", "max_cycles"], v)}
          />
          <NumRow
            label="Gate 最大重试"
            value={get(draft, ["process_defaults", "max_gate_retries"], 0)}
            onChange={(v) => update(["process_defaults", "max_gate_retries"], v)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <NumRow
            label="软空闲阈值（秒）"
            value={get(draft, ["process_defaults", "soft_idle_sec"], 0)}
            onChange={(v) => update(["process_defaults", "soft_idle_sec"], v)}
          />
          <NumRow
            label="硬空闲阈值（秒）"
            value={get(draft, ["process_defaults", "hard_idle_sec"], 0)}
            onChange={(v) => update(["process_defaults", "hard_idle_sec"], v)}
          />
        </div>
        <BoolRow
          label="启用拆分（split）"
          checked={get(draft, ["process_defaults", "split_enabled"], false)}
          onChange={(v) => update(["process_defaults", "split_enabled"], v)}
        />
      </SubGroup>
    </PanelShell>
  )
}

// -------------------- 6. 质量配置 --------------------

export function QualitySettingsPanel() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [initialSys, setInitialSys] = useState<Cfg>({})
  const [initialSkill, setInitialSkill] = useState<Cfg>({})
  const [draftSys, setDraftSys] = useState<Cfg>({})
  const [draftSkill, setDraftSkill] = useState<Cfg>({})

  useEffect(() => {
    setLoading(true)
    Promise.all([getConfig(), getSkillConfig()])
      .then(([sys, skill]) => {
        const sysSlice: Cfg = {
          system: {
            placeholder_markers: get(sys, ["system", "placeholder_markers"], []),
            blocked_markers: get(sys, ["system", "blocked_markers"], []),
            use_strict_must_include_config: get(sys, ["system", "use_strict_must_include_config"], false),
            use_outcome_kind_detection: get(sys, ["system", "use_outcome_kind_detection"], false),
            use_kb_backend_for_observability: get(sys, ["system", "use_kb_backend_for_observability"], false),
          },
        }
        const skillSlice: Cfg = {
          process_defaults: {
            max_gate_retries: get(skill, ["process_defaults", "max_gate_retries"], 0),
            budget_degrade_threshold: get(skill, ["process_defaults", "budget_degrade_threshold"], 0),
            budget_degrade_backend: get(skill, ["process_defaults", "budget_degrade_backend"], ""),
            budget_degrade_model: get(skill, ["process_defaults", "budget_degrade_model"], ""),
          },
        }
        setDraftSys(sysSlice)
        setInitialSys(sysSlice)
        setDraftSkill(skillSlice)
        setInitialSkill(skillSlice)
      })
      .catch((e: Error) => toast.error("加载质量配置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  const dirtySys = !jsonEqual(draftSys, initialSys)
  const dirtySkill = !jsonEqual(draftSkill, initialSkill)
  const dirty = dirtySys || dirtySkill

  function updateSys(path: string[], value: any) {
    setDraftSys((d) => setIn(d, path, value))
  }
  function updateSkill(path: string[], value: any) {
    setDraftSkill((d) => setIn(d, path, value))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const tasks: Promise<unknown>[] = []
      if (dirtySys) tasks.push(patchConfig(draftSys))
      if (dirtySkill) tasks.push(patchSkillConfig(draftSkill))
      await Promise.all(tasks)
      setInitialSys(draftSys)
      setInitialSkill(draftSkill)
      toast.success("质量配置已保存")
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelShell
      title="执行质量设置"
      description="Gate 检测标记、严格校验开关与预算降级策略"
      loading={loading}
      saving={saving}
      dirty={dirty}
      onSave={() => void handleSave()}
    >
      <SubGroup title="占位与屏蔽标记（system_config）">
        <ArrayRow
          label="占位标记（placeholder_markers）"
          hint="出现这些标记视为交付未完成"
          value={get(draftSys, ["system", "placeholder_markers"], [])}
          onChange={(v) => updateSys(["system", "placeholder_markers"], v)}
          placeholder="待补充&#10;todo"
        />
        <ArrayRow
          label="屏蔽标记（blocked_markers）"
          hint="出现这些标记视为抓取受阻"
          value={get(draftSys, ["system", "blocked_markers"], [])}
          onChange={(v) => updateSys(["system", "blocked_markers"], v)}
          placeholder="signin&#10;captcha"
        />
      </SubGroup>

      <SubGroup title="质量检测开关（system_config）">
        <BoolRow
          label="严格 must_include 配置"
          hint="PGD 严格类型校验"
          checked={get(draftSys, ["system", "use_strict_must_include_config"], false)}
          onChange={(v) => updateSys(["system", "use_strict_must_include_config"], v)}
        />
        <BoolRow
          label="outcome_kind 检测"
          hint="code_project outcome 类型识别"
          checked={get(draftSys, ["system", "use_outcome_kind_detection"], false)}
          onChange={(v) => updateSys(["system", "use_outcome_kind_detection"], v)}
        />
        <BoolRow
          label="可观测性走 KB 后端"
          checked={get(draftSys, ["system", "use_kb_backend_for_observability"], false)}
          onChange={(v) => updateSys(["system", "use_kb_backend_for_observability"], v)}
        />
      </SubGroup>

      <SubGroup title="预算降级（skill_config.process_defaults）">
        <NumRow
          label="Gate 最大重试"
          value={get(draftSkill, ["process_defaults", "max_gate_retries"], 0)}
          onChange={(v) => updateSkill(["process_defaults", "max_gate_retries"], v)}
        />
        <NumRow
          label="预算降级阈值"
          hint="0~1 之间，例如 0.8"
          value={get(draftSkill, ["process_defaults", "budget_degrade_threshold"], 0)}
          onChange={(v) => updateSkill(["process_defaults", "budget_degrade_threshold"], v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <TextRow
            label="降级后端"
            value={get(draftSkill, ["process_defaults", "budget_degrade_backend"], "")}
            onChange={(v) => updateSkill(["process_defaults", "budget_degrade_backend"], v)}
            placeholder="留空不降级"
          />
          <TextRow
            label="降级模型"
            value={get(draftSkill, ["process_defaults", "budget_degrade_model"], "")}
            onChange={(v) => updateSkill(["process_defaults", "budget_degrade_model"], v)}
            placeholder="留空不降级"
          />
        </div>
      </SubGroup>
    </PanelShell>
  )
}
