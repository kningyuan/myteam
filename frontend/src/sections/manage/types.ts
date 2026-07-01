export type ManageTab =
  | "agents"
  | "preferences"
  | "task-types"
  | "templates"
  | "prompt-templates"
  | "delivery-profiles"
  | "knowledge"

export type AgentWorkspaceFileName = "IDENTITY.md" | "SOUL.md" | "AGENTS.md"

export type ConfigFileKey =
  | { scope: "shared"; filename: string }
  | { scope: "workspace"; filename: AgentWorkspaceFileName }
