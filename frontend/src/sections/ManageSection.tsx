import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { listAgents } from "@/lib/api/agents"
import { listDeliveryTemplates, listTaskTypes } from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import type { ManageTab } from "./manage/types"
import { AgentsPanel } from "./manage/AgentsPanel"
import { TaskTypesPanel } from "./manage/TaskTypesPanel"
import { TemplatesPanel } from "./manage/TemplatesPanel"
import { PromptTemplatesPanel } from "./manage/PromptTemplatesPanel"
import { DeliveryProfilesPanel } from "./manage/DeliveryProfilesPanel"
import { PreferencesPanel } from "./manage/PreferencesPanel"
import { KnowledgePanel } from "./manage/KnowledgePanel"

export function ManageSection() {
  const { tab } = useParams()
  const navigate = useNavigate()
  const activeTab = ((tab as ManageTab) || "agents") as ManageTab

  // 共享数据：保持在编排层挂载，避免切换 tab 时重复请求
  const { data: agents } = useResourceQuery("agents", listAgents, [])
  const { data: templates } = useResourceQuery("delivery-templates", listDeliveryTemplates, [])
  const { data: types } = useResourceQuery("task-types", listTaskTypes, [])

  useEffect(() => {
    if (!tab) navigate("/manage/agents", { replace: true })
  }, [tab, navigate])

  switch (activeTab) {
    case "agents":
      return <AgentsPanel agents={agents} />
    case "task-types":
      return <TaskTypesPanel types={types} />
    case "templates":
      return <TemplatesPanel templates={templates} types={types} />
    case "prompt-templates":
      return <PromptTemplatesPanel />
    case "delivery-profiles":
      return <DeliveryProfilesPanel />
    case "preferences":
      return <PreferencesPanel />
    case "knowledge":
      return <KnowledgePanel />
    default:
      return <AgentsPanel agents={agents} />
  }
}
