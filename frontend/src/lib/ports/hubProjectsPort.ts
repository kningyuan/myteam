import { getProject, listProjects, runProject } from "@/lib/api/projects"
import type { ProjectsPort } from "./ProjectsPort"

/** Default ProjectsPort — delegates to Hub REST via `@/lib/api/projects`. */
export const hubProjectsPort: ProjectsPort = {
  listProjects,
  getProject,
  runProject,
}
