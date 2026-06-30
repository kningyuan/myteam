import type { AgentWorkspaceFileName, ConfigFileKey } from "./types"

export const AGENT_WORKSPACE_FILES: AgentWorkspaceFileName[] = ["IDENTITY.md", "SOUL.md"]

export const AGENT_FILE_LABELS: Record<AgentWorkspaceFileName, string> = {
  "IDENTITY.md": "身份定义",
  "SOUL.md": "人格风格",
}

export function configFileId(key: ConfigFileKey): string {
  return key.scope === "shared" ? `shared:${key.filename}` : `ws:${key.filename}`
}
