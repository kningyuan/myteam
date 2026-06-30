import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  deleteDeliveryProfile,
  listDeliveryProfiles,
  saveDeliveryProfile,
  type DeliveryProfileSummary,
} from "@/lib/api/workflows"
import { ManageSegmentNav } from "@/components/manage/ManageSegmentNav"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { WorkspaceHeader } from "./WorkspaceHeader"

export function DeliveryProfilesPanel() {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [profiles, setProfiles] = useState<DeliveryProfileSummary[]>([])
  const [profileFormOpen, setProfileFormOpen] = useState(false)
  const [profileFormMode, setProfileFormMode] = useState<"create" | "edit">("create")
  const [profileFormId, setProfileFormId] = useState("")
  const [profileFormName, setProfileFormName] = useState("")
  const [profileFormDesc, setProfileFormDesc] = useState("")
  const [profileFormArtifacts, setProfileFormArtifacts] = useState("")
  const [profileFormScaffold, setProfileFormScaffold] = useState("")
  const [profileFormBusy, setProfileFormBusy] = useState(false)

  useEffect(() => {
    listDeliveryProfiles()
      .then((p) => setProfiles(p))
      .catch(() => {})
  }, [])

  const selectedProfile = profiles.find((p) => p.id === itemId) ?? null

  function openProfileForm(row: DeliveryProfileSummary | null) {
    const isNew = !row
    setProfileFormMode(isNew ? "create" : "edit")
    setProfileFormId(row?.id || "")
    setProfileFormName(row?.name || row?.id || "")
    setProfileFormDesc(row?.description || "")
    setProfileFormArtifacts((row?.process_artifacts || []).join(", "))
    setProfileFormScaffold(row?.scaffold || "")
    setProfileFormOpen(true)
  }

  async function handleSaveProfile() {
    const id = profileFormId.trim()
    if (!id) {
      toast.error("Profile ID 不能为空")
      return
    }
    const artifacts = profileFormArtifacts
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const body: Record<string, unknown> = {
      id,
      name: profileFormName.trim() || id,
      description: profileFormDesc.trim(),
      process_artifacts: artifacts,
      scaffold: profileFormScaffold.trim(),
    }
    setProfileFormBusy(true)
    try {
      await saveDeliveryProfile(profileFormMode === "edit" ? id : null, body)
      toast.success("Profile 已保存")
      setProfileFormOpen(false)
      const allProfiles = await listDeliveryProfiles()
      setProfiles(allProfiles)
      navigate(`/manage/delivery-profiles/${encodeURIComponent(id)}`)
    } catch (e) {
      toast.error("保存失败", { description: e instanceof Error ? e.message : "" })
    } finally {
      setProfileFormBusy(false)
    }
  }

  async function handleDeleteProfile(id: string) {
    if (!window.confirm(`删除交付流程「${id}」？`)) return
    try {
      await deleteDeliveryProfile(id)
      toast.success("已删除")
      setProfiles((prev) => prev.filter((p) => p.id !== id))
      navigate("/manage/delivery-profiles")
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : "" })
    }
  }

  return (
    <>
      <DiscordShell
        list={
          <ListColumn
            title="管理"
            action={
              <Button size="sm" onClick={() => openProfileForm(null)}>
                新建
              </Button>
            }
            tabs={<ManageSegmentNav />}
            search={
              <input
                placeholder="搜索交付流程…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            }
            widthStorageKey="agentHub.manageListWidth"
          >
            {profiles.map((p) => (
              <ListItemRow
                key={p.id}
                name={p.name || p.id}
                sub={p.description?.slice(0, 40) || p.id}
                avatar={p.id}
                active={p.id === itemId}
                onClick={() => navigate(`/manage/delivery-profiles/${encodeURIComponent(p.id)}`)}
                onDelete={() => handleDeleteProfile(p.id)}
              />
            ))}
          </ListColumn>
        }
      >
        <div className="discord-main-scroll workspace-scroll">
          <WorkspaceHeader
            title="交付流程"
            description="定义任务执行过程中的附加工件（process_artifacts）与脚手架。"
          />
          {selectedProfile ? (
            <div className="workspace-panel">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{selectedProfile.name || selectedProfile.id}</h2>
                  <p className="mt-1 font-mono text-xs text-[var(--color-muted-foreground)]">{selectedProfile.id}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => openProfileForm(selectedProfile)}>
                    编辑
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteProfile(selectedProfile.id)}>
                    删除
                  </Button>
                </div>
              </div>
              {selectedProfile.description && (
                <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                  {selectedProfile.description}
                </p>
              )}
              <Separator className="my-5" />
              <dl className="detail-dl">
                <div className="agent-detail-span-full">
                  <dt>过程工件</dt>
                  <dd>
                    {(selectedProfile.process_artifacts || []).length ? (
                      <div className="flex flex-wrap gap-1.5">
                        {selectedProfile.process_artifacts!.map((a) => (
                          <Badge key={a} variant="secondary">
                            {a}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      "无"
                    )}
                  </dd>
                </div>
                {selectedProfile.scaffold && (
                  <div className="agent-detail-span-full">
                    <dt>脚手架</dt>
                    <dd className="font-mono text-xs">{selectedProfile.scaffold}</dd>
                  </div>
                )}
              </dl>
            </div>
          ) : (
            <WelcomePane title="选择交付流程" description="左侧已列出全部流程，点选一项查看详情。" />
          )}
        </div>
      </DiscordShell>

      <Dialog open={profileFormOpen} onOpenChange={setProfileFormOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{profileFormMode === "create" ? "新建交付流程" : "编辑交付流程"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Profile ID</Label>
                <Input
                  value={profileFormId}
                  readOnly={profileFormMode === "edit"}
                  onChange={(e) => setProfileFormId(e.target.value)}
                  placeholder="例如：light_v1"
                />
              </div>
              <div className="grid gap-2">
                <Label>显示名称</Label>
                <Input value={profileFormName} onChange={(e) => setProfileFormName(e.target.value)} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label>描述</Label>
              <Textarea rows={2} value={profileFormDesc} onChange={(e) => setProfileFormDesc(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>过程工件（逗号分隔）</Label>
              <Textarea
                rows={3}
                value={profileFormArtifacts}
                onChange={(e) => setProfileFormArtifacts(e.target.value)}
                placeholder="例如：align.md, verify.log, plan.md"
              />
            </div>
            <div className="grid gap-2">
              <Label>脚手架（scaffold）</Label>
              <Input
                value={profileFormScaffold}
                onChange={(e) => setProfileFormScaffold(e.target.value)}
                placeholder="例如：deliverable_guarantee.scaffold_markdown_deliverable"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProfileFormOpen(false)}>
              取消
            </Button>
            <Button disabled={profileFormBusy} onClick={() => void handleSaveProfile()}>
              {profileFormBusy ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
