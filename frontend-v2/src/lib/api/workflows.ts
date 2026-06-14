import { invalidateResources } from "@/lib/dataRefresh"
import { hubFetch } from "./client"

export type WorkflowDetail = {
  id?: string
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
  description?: string
  version?: string
  task_count?: number
  roster?: string[]
}

export type DeliveryTemplateSummary = {
  id: string
  display_name?: string
  task_types?: string[]
  description?: string
}

export type DeliveryTemplateDetail = DeliveryTemplateSummary & {
  yaml?: string
  sections?: { name: string; description?: string }[]
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
  sections?: { name: string; description?: string }[]
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

export async function listDeliveryTemplates(): Promise<DeliveryTemplateSummary[]> {
  const data = await hubFetch<{ templates?: DeliveryTemplateSummary[] }>("/api/delivery-templates")
  return data.templates ?? []
}

export async function getDeliveryTemplate(templateId: string): Promise<DeliveryTemplateDetail> {
  const data = await hubFetch<{ template?: DeliveryTemplateDetail }>(
    `/api/delivery-templates/${encodeURIComponent(templateId)}`,
  )
  return data.template ?? { id: templateId }
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
