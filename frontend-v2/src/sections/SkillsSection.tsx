import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  getSkillDraftDiff,
  getSkillMatrixAudit,
  listSkillDrafts,
  type SkillDraftDiff,
  type SkillMatrixAudit,
} from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

function MatrixBanner({ matrix }: { matrix: SkillMatrixAudit | null }) {
  if (!matrix) return null
  const gaps = (matrix.missing_router_skill_md?.length ?? 0) + (matrix.in_skill_dir_not_catalog?.length ?? 0)
  return (
    <div className="skill-matrix-banner">
      <div className="skill-matrix-stats">
        <span>注册 task_type {matrix.registered_task_types ?? 0}</span>
        <span>catalog {matrix.catalog_task_types ?? 0}</span>
        <span>Skill 目录 {matrix.skill_router_dirs ?? 0}</span>
        <span>草案 {matrix.draft_count ?? 0}</span>
      </div>
      {gaps > 0 ? (
        <p className="skill-matrix-warn text-xs">
          覆盖缺口 {gaps}：缺 router {(matrix.missing_router_skill_md ?? []).slice(0, 3).join("、")}
          {(matrix.missing_router_skill_md?.length ?? 0) > 3 ? "…" : ""}
        </p>
      ) : (
        <p className="hint text-xs">catalog 与 Skill 目录基本对齐</p>
      )}
    </div>
  )
}

function DiffPanel({ diff, loading }: { diff: SkillDraftDiff | null; loading: boolean }) {
  if (loading) return <div className="p-6 text-[var(--color-muted-foreground)]">加载对比…</div>
  if (!diff) return <WelcomePane title="选择 Skill 草案" description="左侧列出 auto-* 草案，右侧对比正式 SKILL.md。" />

  return (
    <div className="skill-diff-panel">
      <header className="skill-diff-head">
        <div>
          <h1 className="text-lg font-semibold">{diff.draft_id}</h1>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            task_type: {diff.task_type || "—"}
            {diff.production_path ? ` · 对照 ${diff.production_path}` : " · 无正式 Skill"}
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <Badge variant="secondary">草案 {diff.draft_lines ?? 0} 行</Badge>
          <Badge variant="outline">正式 {diff.production_lines ?? 0} 行</Badge>
        </div>
      </header>
      <p className="skill-diff-hint hint text-xs">
        L3 草案仅供人工合入（L4）。合入后删除 auto-* 目录并跑 REG。
      </p>
      <div className="skill-diff-grid">
        <div className="skill-diff-col">
          <h2 className="skill-diff-col-title">草案（auto-*）</h2>
          <ScrollArea className="skill-diff-scroll">
            <pre className="skill-diff-pre">{diff.draft || "（空）"}</pre>
          </ScrollArea>
        </div>
        <div className="skill-diff-col">
          <h2 className="skill-diff-col-title">正式 SKILL.md</h2>
          <ScrollArea className="skill-diff-scroll">
            <pre className="skill-diff-pre">{diff.production || "（该 task_type 尚无正式 Skill）"}</pre>
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}

export function SkillsSection() {
  const { draftId } = useParams()
  const navigate = useNavigate()
  const { data: drafts } = useResourceQuery("skill-drafts", listSkillDrafts, [])
  const { data: matrix } = useResourceQuery("skill-drafts", getSkillMatrixAudit, null as SkillMatrixAudit | null)
  const [diff, setDiff] = useState<SkillDraftDiff | null>(null)
  const [loadingDiff, setLoadingDiff] = useState(false)

  useEffect(() => {
    if (!draftId) {
      setDiff(null)
      return
    }
    setLoadingDiff(true)
    getSkillDraftDiff(draftId)
      .then(setDiff)
      .catch(() => setDiff(null))
      .finally(() => setLoadingDiff(false))
  }, [draftId])

  const sorted = useMemo(
    () => [...drafts].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0)),
    [drafts],
  )

  return (
    <DiscordShell
      list={
        <ListColumn title="Skill 升级">
          <MatrixBanner matrix={matrix} />
          {sorted.length ? (
            sorted.map((d) => (
              <ListItemRow
                key={d.id}
                name={d.id.replace(/^auto-/, "")}
                sub={[d.task_type, d.project_id].filter(Boolean).join(" · ") || d.description}
                avatar={d.task_type || "SK"}
                active={d.id === draftId}
                onClick={() => navigate(`/skills/${encodeURIComponent(d.id)}`)}
              />
            ))
          ) : (
            <p className="px-4 py-6 text-center text-xs text-[var(--color-muted-foreground)]">
              暂无 auto-* 草案。项目 completed 且 skill_extract_enabled 时会自动生成。
            </p>
          )}
        </ListColumn>
      }
    >
      <div className="discord-main-scroll workspace-scroll">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <p className="hint text-sm">
            Skill 自我升级：L3 草案 → 人工 diff → 合入正式 SKILL.md。workflow{" "}
            <code className="text-xs">self-upgrade</code> 用于 REG-L3。
          </p>
          <Button size="sm" variant="outline" onClick={() => navigate("/workflows/self-upgrade")}>
            打开 self-upgrade 流程
          </Button>
        </div>
        <DiffPanel diff={diff} loading={loadingDiff && !!draftId} />
      </div>
    </DiscordShell>
  )
}
