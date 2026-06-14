import { useEffect, useState } from "react"
import { toast } from "sonner"
import { applyModelToAllAgents } from "@/lib/api/agents"
import {
  getConfig,
  getSkillConfig,
  listBackendModels,
  listBackends,
  updateConfig,
  updateSkillConfig,
  type BackendModel,
  type BackendSummary,
} from "@/lib/api/config"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PageHeader, SettingRow, SettingSection } from "@/components/ui/page"
import type { SettingsSectionId } from "@/sections/SettingsSection"

function CheckboxRow({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 py-3.5">
      <span className="text-sm text-[var(--color-muted-foreground)]">{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  )
}

export function SettingsPage({ section = "system" }: { section?: SettingsSectionId }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [backends, setBackends] = useState<BackendSummary[]>([])
  const [models, setModels] = useState<BackendModel[]>([])

  const [defaultBackend, setDefaultBackend] = useState("opencode")
  const [defaultModel, setDefaultModel] = useState("")
  const [port, setPort] = useState("8765")
  const [debug, setDebug] = useState(false)
  const [auditLog, setAuditLog] = useState(false)
  const [auditMaxBytes, setAuditMaxBytes] = useState("500000")
  const [pricePerMtok, setPricePerMtok] = useState("")
  const [defaultReview, setDefaultReview] = useState(false)
  const [cliPath, setCliPath] = useState("")
  const [modelAliases, setModelAliases] = useState("{}")

  const [useProjectGroup, setUseProjectGroup] = useState(true)
  const [enableTelegram, setEnableTelegram] = useState(true)
  const [autoGroup, setAutoGroup] = useState(true)
  const [autoGroupMain, setAutoGroupMain] = useState(true)
  const [autoGroupPrefix, setAutoGroupPrefix] = useState("")
  const [hubUrl, setHubUrl] = useState("http://127.0.0.1:8765")

  const [gdDefaultMaxRounds, setGdDefaultMaxRounds] = useState("3")
  const [gdMaxRoundsCap, setGdMaxRoundsCap] = useState("50")
  const [gdTurnTimeout, setGdTurnTimeout] = useState("300")
  const [gdQuorumRatio, setGdQuorumRatio] = useState("67")
  const [gdAutoFinalize, setGdAutoFinalize] = useState(true)
  const [gdAllowExtension, setGdAllowExtension] = useState(true)
  const [gdKillCliOnCancel, setGdKillCliOnCancel] = useState(true)
  const [gdTerminateCommands, setGdTerminateCommands] = useState("/终止讨论\n/终止圆桌\n/stop roundtable")

  const [pollInterval, setPollInterval] = useState("5")
  const [taskTimeout, setTaskTimeout] = useState("3600")
  const [agentMsgTimeout, setAgentMsgTimeout] = useState("1800")
  const [maxRetries, setMaxRetries] = useState("3")

  const [defaultBudget, setDefaultBudget] = useState("1000000")
  const [maxGateRetries, setMaxGateRetries] = useState("5")
  const [parallelEnabled, setParallelEnabled] = useState(false)
  const [maxParallel, setMaxParallel] = useState("3")
  const [maxConcurrentProjects, setMaxConcurrentProjects] = useState("2")
  const [budgetDegradeThreshold, setBudgetDegradeThreshold] = useState("80")
  const [splitDefault, setSplitDefault] = useState(false)

  const [rawCfg, setRawCfg] = useState<Record<string, unknown>>({})
  const [rawSkill, setRawSkill] = useState<Record<string, unknown>>({})

  async function loadModels(backendId: string, selected?: string) {
    try {
      const ms = await listBackendModels(backendId)
      setModels(ms)
      if (selected && ms.some((m) => m.id === selected)) setDefaultModel(selected)
      else if (ms.find((m) => m.default)) setDefaultModel(ms.find((m) => m.default)!.id)
      else if (ms[0]) setDefaultModel(ms[0].id)
    } catch {
      setModels([])
    }
  }

  useEffect(() => {
    Promise.all([getConfig(), getSkillConfig(), listBackends()])
      .then(async ([cfg, skill, bs]) => {
        setRawCfg(cfg)
        setRawSkill(skill)
        setBackends(bs)
        const sys = (cfg.system || {}) as Record<string, unknown>
        const backend = String(sys.default_backend || "opencode")
        setDefaultBackend(backend)
        setPort(String(sys.port ?? 8765))
        setDebug(!!sys.debug)
        setAuditLog(!!sys.audit_log)
        setAuditMaxBytes(String(sys.audit_log_max_bytes ?? 500000))
        setPricePerMtok(sys.price_per_mtok != null ? String(sys.price_per_mtok) : "")
        setDefaultReview(!!sys.default_review)
        const bcfg = ((cfg.backends || {}) as Record<string, Record<string, unknown>>)[backend]
        setCliPath(String(bcfg?.cli_path || ""))
        if (backend === "opencode") {
          setModelAliases(JSON.stringify(bcfg?.model_aliases || {}, null, 2))
        }
        await loadModels(backend, String(sys.default_model || ""))

        const notif = (skill.notifications || {}) as Record<string, unknown>
        setUseProjectGroup(notif.use_project_group !== false)
        setEnableTelegram(notif.enable_telegram !== false)
        const ag = (skill.auto_group || {}) as Record<string, unknown>
        setAutoGroup(ag.enabled !== false)
        setAutoGroupMain(ag.include_main !== false)
        setAutoGroupPrefix(String(ag.name_prefix || ""))
        setHubUrl(String((skill.hub as Record<string, unknown>)?.url || "http://127.0.0.1:8765"))

        const gd = (skill.group_discussion || {}) as Record<string, unknown>
        setGdDefaultMaxRounds(String(gd.default_max_rounds ?? 3))
        setGdMaxRoundsCap(String(gd.max_rounds_cap ?? 50))
        setGdTurnTimeout(String(gd.roundtable_turn_timeout ?? 300))
        const qr = Number(gd.quorum_ratio ?? 0.667)
        setGdQuorumRatio(String(Math.round(qr * 100)))
        setGdAutoFinalize(gd.auto_finalize_on_max_rounds !== false)
        setGdAllowExtension(gd.allow_round_extension !== false)
        setGdKillCliOnCancel(gd.kill_cli_on_cancel !== false)
        const cmds = gd.terminate_commands
        if (Array.isArray(cmds) && cmds.length) {
          setGdTerminateCommands(cmds.map(String).join("\n"))
        }

        const ex = (skill.executor || {}) as Record<string, unknown>
        setPollInterval(String(ex.poll_interval ?? 5))
        setTaskTimeout(String(ex.task_timeout ?? 3600))
        setAgentMsgTimeout(String(ex.agent_msg_timeout ?? 1800))
        setMaxRetries(String(ex.max_retries ?? 3))

        const pd = (skill.process_defaults || {}) as Record<string, unknown>
        setDefaultBudget(String(pd.default_project_budget ?? 1000000))
        setMaxGateRetries(String(pd.max_gate_retries ?? 5))
        setParallelEnabled(!!pd.parallel_enabled)
        setMaxParallel(String(pd.max_parallel ?? 3))
        setMaxConcurrentProjects(String(pd.max_concurrent_projects ?? 2))
        setBudgetDegradeThreshold(String(Math.round(Number(pd.budget_degrade_threshold ?? 0.8) * 100)))
        setSplitDefault(!!pd.split_enabled)
      })
      .catch((e: Error) => toast.error("加载设置失败", { description: e.message }))
      .finally(() => setLoading(false))
  }, [])

  async function onBackendChange(id: string) {
    setDefaultBackend(id)
    const bcfg = ((rawCfg.backends || {}) as Record<string, Record<string, unknown>>)[id]
    setCliPath(String(bcfg?.cli_path || ""))
    await loadModels(id)
  }

  async function handleSave() {
    setSaving(true)
    try {
      let aliases: Record<string, unknown> = {}
      if (defaultBackend === "opencode") {
        try {
          aliases = JSON.parse(modelAliases || "{}")
        } catch {
          toast.error("模型别名 JSON 格式错误")
          setSaving(false)
          return
        }
      }
      const cfg = { ...rawCfg }
      const sys = { ...((cfg.system || {}) as Record<string, unknown>) }
      sys.default_backend = defaultBackend
      sys.default_model = defaultModel
      sys.port = parseInt(port, 10) || 8765
      sys.debug = debug
      sys.audit_log = auditLog
      sys.audit_log_max_bytes = parseInt(auditMaxBytes, 10) || 500000
      sys.price_per_mtok = Number(pricePerMtok) || 0
      sys.default_review = defaultReview
      cfg.system = sys
      const bmap = { ...((cfg.backends || {}) as Record<string, unknown>) }
      const bent = { ...((bmap[defaultBackend] || {}) as Record<string, unknown>) }
      bent.cli_path = cliPath.trim()
      if (defaultBackend === "opencode") bent.model_aliases = aliases
      bmap[defaultBackend] = bent
      cfg.backends = bmap

      const skillCfg = { ...rawSkill }
      skillCfg.notifications = {
        ...((skillCfg.notifications || {}) as Record<string, unknown>),
        use_project_group: useProjectGroup,
        enable_telegram: enableTelegram,
      }
      skillCfg.auto_group = {
        ...((skillCfg.auto_group || {}) as Record<string, unknown>),
        enabled: autoGroup,
        include_main: autoGroupMain,
        name_prefix: autoGroupPrefix.trim(),
      }
      skillCfg.hub = { ...((skillCfg.hub || {}) as Record<string, unknown>), url: hubUrl.trim() }
      const gdQuorum = parseFloat(gdQuorumRatio)
      skillCfg.group_discussion = {
        ...((skillCfg.group_discussion || {}) as Record<string, unknown>),
        default_max_rounds: parseInt(gdDefaultMaxRounds, 10) || 3,
        max_rounds_cap: parseInt(gdMaxRoundsCap, 10) || 50,
        roundtable_turn_timeout: parseInt(gdTurnTimeout, 10) || 300,
        quorum_ratio:
          !Number.isNaN(gdQuorum) && gdQuorum > 0 && gdQuorum <= 100 ? gdQuorum / 100 : 0.667,
        auto_finalize_on_max_rounds: gdAutoFinalize,
        allow_round_extension: gdAllowExtension,
        kill_cli_on_cancel: gdKillCliOnCancel,
        terminate_commands: gdTerminateCommands
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      }
      skillCfg.executor = {
        ...((skillCfg.executor || {}) as Record<string, unknown>),
        poll_interval: parseInt(pollInterval, 10) || 5,
        task_timeout: parseInt(taskTimeout, 10) || 3600,
        agent_msg_timeout: parseInt(agentMsgTimeout, 10) || 1800,
        max_retries: parseInt(maxRetries, 10) || 3,
      }
      const thrPct = parseFloat(budgetDegradeThreshold)
      skillCfg.process_defaults = {
        ...((skillCfg.process_defaults || {}) as Record<string, unknown>),
        default_project_budget: parseInt(defaultBudget, 10) || 1000000,
        max_gate_retries: parseInt(maxGateRetries, 10) || 5,
        parallel_enabled: parallelEnabled,
        max_parallel: parseInt(maxParallel, 10) || 3,
        max_concurrent_projects: parseInt(maxConcurrentProjects, 10) || 2,
        split_enabled: splitDefault,
        budget_degrade_threshold:
          !Number.isNaN(thrPct) && thrPct > 0 && thrPct < 100 ? thrPct / 100 : 0.8,
      }

      await Promise.all([updateConfig(cfg), updateSkillConfig(skillCfg)])
      setRawCfg(cfg)
      setRawSkill(skillCfg)
      toast.success("设置已保存", { description: "端口变更需重启 Hub" })
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setSaving(false)
    }
  }

  async function handleApplyModelAll() {
    if (!defaultModel) return
    try {
      await applyModelToAllAgents(defaultModel)
      toast.success("已将默认模型应用到全部 Agent")
    } catch (e) {
      toast.error("应用失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  if (loading) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">加载设置…</p>
  }

  const sectionMeta: Record<SettingsSectionId, { title: string; description: string }> = {
    system: { title: "系统", description: "Hub 服务、默认 AI 后端与模型。" },
    collab: { title: "协作", description: "项目群通报、Telegram 与 Hub 地址。" },
    group: {
      title: "群配置",
      description: "全局 @all 圆桌讨论参数，对所有群组生效；单群可在成员设置里覆盖轮数。",
    },
    exec: { title: "执行", description: "轮询间隔、任务超时与重试策略。" },
    project: { title: "项目", description: "默认预算、并行度与 Gate 重试。" },
  }

  const meta = sectionMeta[section]

  return (
    <div className="space-y-6">
      <PageHeader
        title={meta.title}
        description={meta.description}
        action={
          <div className="flex gap-2">
            {section === "system" && (
              <Button variant="outline" onClick={handleApplyModelAll}>
                模型应用到全部 Agent
              </Button>
            )}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "保存中…" : "保存设置"}
            </Button>
          </div>
        }
      />

      {section === "system" && (
        <SettingSection title="系统" description="Hub 服务与默认 AI 后端">
          <div className="space-y-3 py-2">
            <div className="grid gap-2">
              <Label>默认 AI 后端</Label>
              <Select value={defaultBackend} onValueChange={onBackendChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {backends.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name || b.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>默认模型</Label>
              <Select value={defaultModel} onValueChange={setDefaultModel}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name || m.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>CLI 路径</Label>
              <Input value={cliPath} onChange={(e) => setCliPath(e.target.value)} placeholder="留空自动检测" />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>服务端口</Label>
                <Input value={port} onChange={(e) => setPort(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label>每百万 Token 单价（¥）</Label>
                <Input value={pricePerMtok} onChange={(e) => setPricePerMtok(e.target.value)} />
              </div>
            </div>
            <CheckboxRow label="调试模式" checked={debug} onChange={setDebug} />
            <CheckboxRow label="审计日志" checked={auditLog} onChange={setAuditLog} />
            <CheckboxRow label="默认开启评审" checked={defaultReview} onChange={setDefaultReview} />
            {defaultBackend === "opencode" && (
              <div className="grid gap-2">
                <Label>OpenCode 模型别名（JSON）</Label>
                <Textarea rows={4} value={modelAliases} onChange={(e) => setModelAliases(e.target.value)} className="font-mono text-xs" />
              </div>
            )}
          </div>
        </SettingSection>
      )}

      {section === "collab" && (
        <SettingSection title="协作与通知">
          <CheckboxRow label="使用项目群通报" checked={useProjectGroup} onChange={setUseProjectGroup} />
          <CheckboxRow label="Telegram 通知" checked={enableTelegram} onChange={setEnableTelegram} />
          <CheckboxRow label="自动建项目群" checked={autoGroup} onChange={setAutoGroup} />
          <CheckboxRow label="群名包含主 Agent" checked={autoGroupMain} onChange={setAutoGroupMain} />
          <SettingRow label="群名前缀" value={<Input value={autoGroupPrefix} onChange={(e) => setAutoGroupPrefix(e.target.value)} className="max-w-[200px]" />} />
          <SettingRow label="Hub 地址" value={<Input value={hubUrl} onChange={(e) => setHubUrl(e.target.value)} className="max-w-[240px]" />} />
        </SettingSection>
      )}

      {section === "group" && (
        <>
          <SettingSection title="圆桌讨论" description="@all 触发全员圆桌；以下均为全局默认。">
            <SettingRow
              label="默认最大轮数"
              value={
                <Input
                  type="number"
                  min={1}
                  max={parseInt(gdMaxRoundsCap, 10) || 50}
                  value={gdDefaultMaxRounds}
                  onChange={(e) => setGdDefaultMaxRounds(e.target.value)}
                  className="max-w-[120px]"
                />
              }
            />
            <SettingRow
              label="轮数上限（cap）"
              value={
                <Input
                  type="number"
                  min={1}
                  value={gdMaxRoundsCap}
                  onChange={(e) => setGdMaxRoundsCap(e.target.value)}
                  className="max-w-[120px]"
                />
              }
            />
            <SettingRow
              label="单轮发言超时（秒）"
              value={
                <Input
                  type="number"
                  min={60}
                  value={gdTurnTimeout}
                  onChange={(e) => setGdTurnTimeout(e.target.value)}
                  className="max-w-[120px]"
                />
              }
            />
            <SettingRow
              label="参与率门槛（%）"
              value={
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={gdQuorumRatio}
                  onChange={(e) => setGdQuorumRatio(e.target.value)}
                  className="max-w-[120px]"
                />
              }
            />
            <p className="text-xs text-[var(--color-muted-foreground)]">
              未单独设置轮数的群组使用「默认最大轮数」；单群可在群成员设置里覆盖（不超过 cap）。
            </p>
          </SettingSection>
          <SettingSection title="终止与保底">
            <CheckboxRow
              label="达轮数上限时自动汇总，待用户拍板（保底）"
              checked={gdAutoFinalize}
              onChange={setGdAutoFinalize}
            />
            <CheckboxRow
              label="未共识时允许扩展轮次（至 cap）"
              checked={gdAllowExtension}
              onChange={setGdAllowExtension}
            />
            <CheckboxRow
              label="取消 / 终止时 kill 后台 CLI 进程"
              checked={gdKillCliOnCancel}
              onChange={setGdKillCliOnCancel}
            />
            <div className="grid gap-2 py-2">
              <Label>终止讨论命令（每行一条，无需 @mention）</Label>
              <Textarea
                rows={4}
                value={gdTerminateCommands}
                onChange={(e) => setGdTerminateCommands(e.target.value)}
                className="font-mono text-xs"
                placeholder="/终止讨论&#10;/终止圆桌"
              />
              <p className="text-xs text-[var(--color-muted-foreground)]">
                群聊输入框发送上述命令即可终止进行中的圆桌，并尝试结束挂起的 Agent CLI。
              </p>
            </div>
          </SettingSection>
        </>
      )}

      {section === "exec" && (
        <SettingSection title="执行与超时">
          <SettingRow label="轮询间隔（秒）" value={<Input value={pollInterval} onChange={(e) => setPollInterval(e.target.value)} className="max-w-[120px]" />} />
          <SettingRow label="任务超时（秒）" value={<Input value={taskTimeout} onChange={(e) => setTaskTimeout(e.target.value)} className="max-w-[120px]" />} />
          <SettingRow label="Agent 消息超时（秒）" value={<Input value={agentMsgTimeout} onChange={(e) => setAgentMsgTimeout(e.target.value)} className="max-w-[120px]" />} />
          <SettingRow label="最大重试" value={<Input value={maxRetries} onChange={(e) => setMaxRetries(e.target.value)} className="max-w-[120px]" />} />
        </SettingSection>
      )}

      {section === "project" && (
        <SettingSection title="项目运行默认">
          <SettingRow label="默认项目预算（tok）" value={<Input value={defaultBudget} onChange={(e) => setDefaultBudget(e.target.value)} className="max-w-[160px]" />} />
          <SettingRow label="Gate 最大重试" value={<Input value={maxGateRetries} onChange={(e) => setMaxGateRetries(e.target.value)} className="max-w-[120px]" />} />
          <CheckboxRow label="波次并行" checked={parallelEnabled} onChange={setParallelEnabled} />
          <SettingRow label="最大并行数" value={<Input value={maxParallel} onChange={(e) => setMaxParallel(e.target.value)} className="max-w-[120px]" />} />
          <SettingRow label="最大并发项目" value={<Input value={maxConcurrentProjects} onChange={(e) => setMaxConcurrentProjects(e.target.value)} className="max-w-[120px]" />} />
          <SettingRow label="预算降级阈值（%）" value={<Input value={budgetDegradeThreshold} onChange={(e) => setBudgetDegradeThreshold(e.target.value)} className="max-w-[120px]" />} />
          <CheckboxRow label="默认自动拆分子任务" checked={splitDefault} onChange={setSplitDefault} />
        </SettingSection>
      )}
    </div>
  )
}
