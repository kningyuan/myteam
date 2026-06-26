import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type WorkflowDetail = {
  id?: string
  name?: string
  display_name?: string
  description?: string
  version?: string
  tasks?: {
    id: string
    name?: string
    agent?: string
    task_type?: string
    template_id?: string
    dependencies?: string[]
    loop?: string
    description?: string
  }[]
  loops?: Record<string, unknown>[]
  roster?: string[]
  options?: {
    review_enabled?: boolean
    split_enabled?: boolean
    parallel_enabled?: boolean
    max_parallel?: number
  }
}

export type WorkflowSummary = {
  id: string
  name?: string
  display_name?: string
  description?: string
  version?: string
  task_count?: number
  roster?: string[]
  operated_at?: string
}

/** 工作流 UI 展示名（优先 name，回退 id）。 */
export function workflowDisplayName(w: {
  name?: string
  display_name?: string
  id: string
}): string {
  return (w.name || w.display_name || w.id).trim()
}

export type DeliveryTemplateSummary = {
  id: string
  display_name?: string
  task_types?: string[]
  description?: string
  default_for?: string
  sections?: Array<string | { name: string; description?: string }>
  operated_at?: string
}

export type DeliveryTemplateDetail = DeliveryTemplateSummary & {
  yaml?: string
  template?: DeliveryTemplateSummary
}

export type OutcomeKind = {
  id: string
  label: string
  form_label_zh?: string
  gate_algorithm?: string
  summary?: string
  covers?: string[]
  examples?: string[]
}

export type TaskTypeSummary = {
  task_type: string
  display_name?: string
  outcome_kind: string
  outcome_form_label?: string
  gate_algorithm?: string
  gate_checks?: string[]
  required_sections?: string[]
  sections?: { name: string; description?: string }[]
  operated_at?: string
}

export type SkillLibraryItem = {
  id: string
  kind?: "skill" | "category"
  name?: string
  description?: string
  path?: string
  updated_at?: number
  line_count?: number
  group_id?: string
  category_dir?: string
  member_count?: number
  members?: SkillGroupMember[]
  content?: string
  body?: string
  task_type?: string
  is_draft?: boolean
  is_mountable?: boolean
  is_symlink?: boolean
  link_target?: string
  sections?: SkillSection[]
  tree?: SkillTreeNode[]
  files?: SkillFileRef[]
}

export type SkillGroupMember = {
  id: string
  name?: string
  description?: string
}

export type SkillGroup = {
  id: string
  name?: string
  description?: string
  vendor_skills_root?: string
  storage_dir?: string
  members: SkillGroupMember[]
  is_group?: boolean
}

export type SkillSection = {
  id: string
  title: string
  level?: number
  content?: string
}

export type SkillFileRef = {
  path: string
  name?: string
  kind?: string
  size?: number
}

export type SkillTreeNode = {
  name: string
  path: string
  type: "file" | "dir"
  kind?: string
  size?: number
  children?: SkillTreeNode[]
}

export type SkillFileContent = SkillFileRef & {
  exists?: boolean
  content?: string
}

export type SkillDraftSummary = {
  id: string
  path?: string
  task_type?: string
  project_id?: string
  task_id?: string
  agent?: string
  description?: string
  has_production_skill?: boolean
  production_skill_path?: string | null
  updated_at?: number
}

export type SkillDraftDetail = SkillDraftSummary & {
  content?: string
}

export type SkillDraftDiff = {
  draft_id: string
  task_type?: string
  draft_path?: string
  production_path?: string | null
  draft?: string
  production?: string
  draft_lines?: number
  production_lines?: number
}

export type SkillMatrixAudit = {
  registered_task_types?: number
  catalog_task_types?: number
  skill_router_dirs?: number
  draft_count?: number
  missing_router_skill_md?: string[]
  in_skill_dir_not_catalog?: string[]
}

export async function listWorkflows(): Promise<WorkflowSummary[]> {
  const data = await hubFetch<{ workflows: WorkflowSummary[] }>("/api/workflows")
  return data.workflows ?? []
}

export async function getWorkflow(workflowId: string): Promise<WorkflowDetail> {
  const data = await hubFetch<{ workflow?: WorkflowDetail }>(
    `/api/workflows/${encodeURIComponent(workflowId)}`,
  )
  return data.workflow ?? {}
}

export async function saveWorkflow(
  workflowId: string | null,
  body: Record<string, unknown>,
): Promise<string> {
  let id: string
  if (workflowId) {
    const data = await hubFetch<{ id?: string }>(
      `/api/workflows/${encodeURIComponent(workflowId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    )
    id = data.id ?? workflowId
  } else {
    const data = await hubFetch<{ id?: string }>("/api/workflows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    id = data.id ?? ""
  }
  invalidateResources("workflows")
  return id
}

export async function suggestWorkflow(description: string): Promise<{
  workflow?: WorkflowDetail
  pattern_label?: string
  warnings?: string[]
}> {
  return hubFetch("/api/workflows/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  })
}

export async function deleteWorkflow(workflowId: string): Promise<void> {
  await hubFetch(`/api/workflows/${encodeURIComponent(workflowId)}`, { method: "DELETE" })
  invalidateResources("workflows")
}

export async function listTaskTypes(): Promise<TaskTypeSummary[]> {
  const data = await hubFetch<{ task_types: TaskTypeSummary[] }>("/api/task-types")
  return data.task_types ?? []
}

export async function listOutcomeKinds(): Promise<OutcomeKind[]> {
  const data = await hubFetch<{ outcome_kinds: OutcomeKind[] }>("/api/task-types/outcome-kinds")
  return data.outcome_kinds ?? []
}

export async function createTaskType(body: Record<string, unknown>): Promise<void> {
  await hubFetch("/api/task-types", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("task-types")
}

export async function updateTaskType(
  taskType: string,
  body: Record<string, unknown>,
): Promise<void> {
  await hubFetch(`/api/task-types/${encodeURIComponent(taskType)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  invalidateResources("task-types")
}

export async function deleteTaskType(taskType: string): Promise<void> {
  await hubFetch(`/api/task-types/${encodeURIComponent(taskType)}`, { method: "DELETE" })
  invalidateResources("task-types")
}

export async function suggestTaskType(description: string): Promise<{
  task_type?: string
  display_name?: string
  outcome_kind?: string
  required_sections?: string[]
  pattern?: string
  outcome_catalog?: OutcomeKind[]
}> {
  return hubFetch("/api/task-types/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  })
}

export async function listDeliveryTemplates(): Promise<DeliveryTemplateSummary[]> {
  const data = await hubFetch<{ templates?: DeliveryTemplateSummary[] }>("/api/delivery-templates")
  return data.templates ?? []
}

export async function getDeliveryTemplate(templateId: string): Promise<DeliveryTemplateDetail> {
  const data = await hubFetch<{ template?: DeliveryTemplateSummary; yaml?: string }>(
    `/api/delivery-templates/${encodeURIComponent(templateId)}`,
  )
  return { ...(data.template ?? { id: templateId }), yaml: data.yaml || "" }
}

export async function saveDeliveryTemplate(
  templateId: string | null,
  body: Record<string, unknown>,
): Promise<void> {
  if (templateId) {
    await hubFetch(`/api/delivery-templates/${encodeURIComponent(templateId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  } else {
    await hubFetch("/api/delivery-templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  }
  invalidateResources("delivery-templates")
}

export async function deleteDeliveryTemplate(templateId: string): Promise<void> {
  await hubFetch(`/api/delivery-templates/${encodeURIComponent(templateId)}`, { method: "DELETE" })
  invalidateResources("delivery-templates")
}

export async function listSkillCategories(): Promise<SkillLibraryItem[]> {
  const data = await hubFetch<{ categories?: SkillLibraryItem[] }>("/api/skills/categories")
  return data.categories ?? []
}

export async function createSkillCategory(payload: {
  id: string
  name: string
  description?: string
}): Promise<SkillLibraryItem> {
  const data = await hubFetch<{ category?: SkillLibraryItem }>("/api/skills/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  invalidateResources("skill-library", "skill-groups", "skill-categories")
  if (!data.category) throw new Error("创建分类失败")
  return data.category
}

export async function updateSkillCategory(
  categoryId: string,
  payload: { name?: string; description?: string },
): Promise<SkillLibraryItem> {
  const data = await hubFetch<{ category?: SkillLibraryItem }>(
    `/api/skills/categories/${encodeURIComponent(categoryId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  )
  invalidateResources("skill-library", "skill-groups", "skill-categories")
  if (!data.category) throw new Error("更新分类失败")
  return data.category
}

export async function moveSkillToCategory(
  skillId: string,
  categoryId: string | null,
): Promise<SkillLibraryItem> {
  const data = await hubFetch<{ skill?: SkillLibraryItem }>(
    `/api/skills/library/${encodeURIComponent(skillId)}/category`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category_id: categoryId }),
    },
  )
  invalidateResources("skill-library", "skill-groups", "skill-categories")
  if (!data.skill) throw new Error("移动 Skill 失败")
  return data.skill
}

export async function listSkillLibrary(): Promise<SkillLibraryItem[]> {
  const data = await hubFetch<{ skills?: SkillLibraryItem[] }>("/api/skills/library")
  return data.skills ?? []
}

export async function listSkillGroups(): Promise<SkillGroup[]> {
  const data = await hubFetch<{ groups?: SkillGroup[] }>("/api/skills/groups")
  return data.groups ?? []
}

export async function getSkillLibraryItem(skillId: string): Promise<SkillLibraryItem> {
  return hubFetch(`/api/skills/library/${encodeURIComponent(skillId)}`)
}

export async function getSkillFile(skillId: string, path: string): Promise<SkillFileContent> {
  const q = new URLSearchParams({ path })
  return hubFetch(`/api/skills/library/${encodeURIComponent(skillId)}/file?${q}`)
}

export async function updateSkillName(skillId: string, name: string): Promise<{ success: boolean; skill?: SkillLibraryItem }> {
  const data = await hubFetch<{ success: boolean; skill?: SkillLibraryItem }>(
    `/api/skills/library/${encodeURIComponent(skillId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    },
  )
  invalidateResources("skill-library")
  return data
}

export type DeleteSkillLibraryResult = {
  success: boolean
  skill_id: string
  deleted_path?: string
  unmounted_from?: string[]
  unmounted_count?: number
}

export async function deleteSkillLibraryItem(skillId: string): Promise<DeleteSkillLibraryResult> {
  const data = await hubFetch<DeleteSkillLibraryResult>(
    `/api/skills/library/${encodeURIComponent(skillId)}`,
    { method: "DELETE" },
  )
  invalidateResources("skill-library", "skill-matrix", "agents")
  return data
}

export async function listSkillDrafts(): Promise<SkillDraftSummary[]> {
  const data = await hubFetch<{ drafts?: SkillDraftSummary[] }>("/api/skills/drafts")
  return data.drafts ?? []
}

export async function getSkillDraft(draftId: string): Promise<SkillDraftDetail> {
  return hubFetch(`/api/skills/drafts/${encodeURIComponent(draftId)}`)
}

export async function getSkillDraftDiff(draftId: string): Promise<SkillDraftDiff> {
  return hubFetch(`/api/skills/drafts/${encodeURIComponent(draftId)}/diff`)
}

export async function getSkillMatrixAudit(): Promise<SkillMatrixAudit> {
  return hubFetch("/api/skills/matrix")
}

export type SkillPendingItem = {
  pending_id: string
  project_id?: string
  task_id?: string
  task_type?: string
  agent_id?: string
  action?: string
  skill_id?: string
  notes?: string
  created_at?: string
  has_patch?: boolean
  patch_preview?: string
  patch_content?: string
}

export async function listSkillPending(): Promise<SkillPendingItem[]> {
  const data = await hubFetch<{ pending?: SkillPendingItem[] }>("/api/skills/pending")
  return data.pending ?? []
}

export async function getSkillPending(pendingId: string): Promise<SkillPendingItem> {
  return hubFetch(`/api/skills/pending/${encodeURIComponent(pendingId)}`)
}

export async function approveSkillPending(pendingId: string): Promise<{ success: boolean; applied_path?: string }> {
  return hubFetch(`/api/skills/pending/${encodeURIComponent(pendingId)}/approve`, { method: "POST" })
}

export async function rejectSkillPending(pendingId: string): Promise<{ success: boolean }> {
  return hubFetch(`/api/skills/pending/${encodeURIComponent(pendingId)}/reject`, { method: "POST" })
}

export type SkillReferenceItem = {
  path: string
  name: string
  size?: number
  updated_at?: number
}

export async function listSkillReferences(skillId: string): Promise<SkillReferenceItem[]> {
  const data = await hubFetch<{ references?: SkillReferenceItem[] }>(
    `/api/skills/library/${encodeURIComponent(skillId)}/references`,
  )
  return data.references ?? []
}
