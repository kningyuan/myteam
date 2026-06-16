import { useEffect, useMemo, useState, useCallback } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  getSkillLibraryItem,
  listSkillLibrary,
  type SkillLibraryItem,
} from "@/lib/api/workflows"
import { useResourceQuery, useOnResourceInvalidate } from "@/hooks/useResourceQuery"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { SkillDetailPanel } from "@/components/skills/SkillDetailPanel"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

function SkillHome({
  items,
  loading,
  error,
  onSelect,
}: {
  items: SkillLibraryItem[]
  loading: boolean
  error: string
  onSelect: (id: string) => void
}) {
  if (loading) return <div className="p-6 text-[var(--color-muted-foreground)]">加载 Skill…</div>
  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-[var(--color-destructive)]">Skill 加载失败：{error}</p>
      </div>
    )
  }
  if (!items.length) {
    return (
      <WelcomePane
        title="暂无 Skill"
        description="在 business/skills/<id>/SKILL.md 下添加 Skill；项目完成后也可能自动生成 auto-* 条目。"
      />
    )
  }

  return (
    <div className="skill-home">
      <header className="skill-home-head">
        <div>
          <h1 className="text-lg font-semibold">全部 Skill 概览</h1>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            共 {items.length} 个 · 名称用于展示，ID 为英文目录名
          </p>
        </div>
      </header>
      <p className="skill-home-hint hint text-xs">
        简介帮助 Agent 快速了解能力范围；进入详情可查看分章目录与附属文件，无需一次性加载全文。
      </p>
      <ScrollArea className="skill-home-scroll">
        <div className="skill-home-grid">
          {items.map((s) => (
            <button
              key={s.id}
              type="button"
              className="skill-home-card"
              onClick={() => onSelect(s.id)}
            >
              <div className="skill-home-card-top">
                <span className="skill-home-card-name">{s.name || s.id}</span>
                {s.is_draft ? (
                  <span className="skill-home-card-tag">抽提</span>
                ) : s.is_mountable ? (
                  <span className="skill-home-card-tag skill-home-card-tag--ok">可挂载</span>
                ) : null}
              </div>
              <span className="skill-home-card-id">{s.id}</span>
              <p className="skill-home-card-desc">
                {s.description?.trim() || "暂无简介"}
              </p>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

export function SkillsSection() {
  const { draftId: skillId } = useParams()
  const navigate = useNavigate()
  const {
    data: library,
    loading: loadingLibrary,
    error: libraryError,
    reload: reloadLibrary,
  } = useResourceQuery("skill-library", listSkillLibrary, [])
  const [detail, setDetail] = useState<SkillLibraryItem | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const reloadDetail = useCallback(() => {
    if (!skillId) {
      setDetail(null)
      return
    }
    setLoadingDetail(true)
    getSkillLibraryItem(skillId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false))
  }, [skillId])

  useEffect(() => {
    reloadDetail()
  }, [reloadDetail])

  useOnResourceInvalidate("skill-library", reloadDetail)

  const sorted = useMemo(() => {
    const withBump = library.map((s) =>
      detail?.id === s.id && detail.updated_at
        ? { ...s, updated_at: Math.max(s.updated_at ?? 0, detail.updated_at) }
        : s,
    )
    return sortByModifiedDesc(withBump)
  }, [library, detail?.id, detail?.updated_at])

  return (
    <DiscordShell
      list={
        <ListColumn title="Skill">
          <div className="px-3 pb-2 pt-1">
            <Button
              size="sm"
              variant={skillId ? "outline" : "default"}
              className="w-full"
              onClick={() => navigate("/skills")}
            >
              全部 Skill 概览
            </Button>
          </div>
          {loadingLibrary ? (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">加载中…</p>
          ) : libraryError ? (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-destructive)]">加载失败</p>
          ) : sorted.length ? (
            sorted.map((s) => (
              <ListItemRow
                key={s.id}
                name={s.name || s.id}
                sub={s.id}
                avatar={s.is_draft ? "↑" : "SK"}
                active={s.id === skillId}
                onClick={() => navigate(`/skills/${encodeURIComponent(s.id)}`)}
              />
            ))
          ) : (
            <p className="px-4 py-3 text-center text-xs text-[var(--color-muted-foreground)]">暂无 Skill</p>
          )}
        </ListColumn>
      }
    >
      <div
        className={cn(
          "discord-main-scroll workspace-scroll",
          !skillId && "skill-home-main",
        )}
      >
        {skillId ? (
          <SkillDetailPanel
            item={detail}
            loading={loadingDetail}
            onDeleted={() => {
              void reloadLibrary()
              navigate("/skills")
            }}
            onUpdated={(skill) => {
              setDetail(skill)
              void reloadLibrary()
            }}
          />
        ) : (
          <SkillHome
            items={sorted}
            loading={loadingLibrary}
            error={libraryError}
            onSelect={(id) => navigate(`/skills/${encodeURIComponent(id)}`)}
          />
        )}
      </div>
    </DiscordShell>
  )
}
