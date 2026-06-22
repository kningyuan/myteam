import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { DashboardPage } from "@/pages/DashboardPage"
import { SettingsSection } from "@/sections/SettingsSection"
import { ChatSection } from "@/sections/ChatSection"
import { GroupsSection } from "@/sections/GroupsSection"
import { ManageSection } from "@/sections/ManageSection"
import { ProjectsSection } from "@/sections/ProjectsSection"
import { WorkflowsSection } from "@/sections/WorkflowsSection"
import { SkillsSection } from "@/sections/SkillsSection"
import { ExecuteSection } from "@/sections/ExecuteSection"
import { McpSection } from "@/sections/McpSection"
import { DiscordShell } from "@/components/layout/DiscordShell"

function DashboardRoute() {
  return (
    <DiscordShell>
      <div className="discord-main-scroll">
        <DashboardPage />
      </div>
    </DiscordShell>
  )
}

function SettingsRoute() {
  return <SettingsSection />
}

export default function App() {
  return (
    <BrowserRouter basename="/v2">
      <Routes>
        <Route index element={<DashboardRoute />} />
        <Route path="chat" element={<ChatSection />} />
        <Route path="chat/:agentId" element={<ChatSection />} />
        <Route path="groups" element={<GroupsSection />} />
        <Route path="groups/:groupId" element={<GroupsSection />} />
        <Route path="projects" element={<ProjectsSection />} />
        <Route path="projects/:projectId" element={<ProjectsSection />} />
        <Route path="execute" element={<ExecuteSection />} />
        <Route path="execute/:projectId/:taskId" element={<ExecuteSection />} />
        <Route path="manage" element={<ManageSection />} />
        <Route path="manage/:tab" element={<ManageSection />} />
        <Route path="manage/:tab/:itemId" element={<ManageSection />} />
        <Route path="workflows" element={<WorkflowsSection />} />
        <Route path="workflows/:workflowId" element={<WorkflowsSection />} />
        <Route path="skills" element={<SkillsSection />} />
        <Route path="skills/:skillId" element={<SkillsSection />} />
        <Route path="mcp" element={<McpSection />} />
        <Route path="mcp/:serverId" element={<McpSection />} />
        <Route path="settings" element={<SettingsRoute />} />
        <Route path="settings/:section" element={<SettingsRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
