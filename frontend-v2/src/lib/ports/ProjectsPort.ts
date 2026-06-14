import type { ProjectDetail, ProjectSummary } from "@/lib/api/projects"

/** Pluggable projects boundary — pages/hooks depend on this, not HTTP details. */
export interface ProjectsPort {
  listProjects(): Promise<ProjectSummary[]>

  getProject(projectId: string): Promise<ProjectDetail>

  runProject(body: {
    goal: string
    title?: string
    workflow?: string
    mode?: string
    budget?: number
    review?: boolean
    split?: boolean
  }): Promise<{ project_id: string }>
}
