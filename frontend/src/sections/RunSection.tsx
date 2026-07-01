import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { WorkflowsSection } from "./WorkflowsSection"
import { ExecuteSection } from "./ExecuteSection"

export type RunTab = "workflows" | "single"

export function RunSection() {
  const { tab } = useParams()
  const navigate = useNavigate()
  const activeTab = ((tab as RunTab) || "workflows") as RunTab

  useEffect(() => {
    if (!tab) navigate("/run/workflows", { replace: true })
  }, [tab, navigate])

  if (activeTab === "single") return <ExecuteSection />
  return <WorkflowsSection />
}
