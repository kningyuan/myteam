import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { listWorkflows } from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { WorkflowEditor } from "@/components/workflow/WorkflowEditor"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { Button } from "@/components/ui/button"

export function WorkflowsSection() {
  const { workflowId } = useParams()
  const navigate = useNavigate()
  const { data: workflows } = useResourceQuery("workflows", listWorkflows, [])
  const [editorDirty, setEditorDirty] = useState(false)

  const showEditor = workflowId === "new" || !!workflowId

  function navigateWorkflow(target: string) {
    if (editorDirty && !window.confirm("有未保存的修改，确定离开？")) return
    navigate(target)
  }

  return (
    <DiscordShell
      list={
        <ListColumn
          title="工作流"
          action={
            <Button size="sm" onClick={() => navigateWorkflow("/workflows/new")}>
              新建
            </Button>
          }
        >
          {workflows.map((w) => (
            <ListItemRow
              key={w.id}
              name={w.id}
              sub={`${w.task_count ?? "—"} 任务`}
              avatar={w.id}
              active={w.id === workflowId}
              onClick={() => navigateWorkflow(`/workflows/${encodeURIComponent(w.id)}`)}
            />
          ))}
        </ListColumn>
      }
    >
      {showEditor ? (
        <WorkflowEditor
          workflowId={workflowId === "new" ? null : workflowId!}
          onDirtyChange={setEditorDirty}
          onSaved={(id) => {
            setEditorDirty(false)
            navigate(`/workflows/${encodeURIComponent(id)}`, { replace: true })
          }}
          onDeleted={() => {
            setEditorDirty(false)
            navigate("/workflows")
          }}
        />
      ) : (
        <WelcomePane
          title="选择或新建工作流"
          description="左侧选择已有流程，或点击「新建」用表单编辑任务编排。"
        />
      )}
    </DiscordShell>
  )
}
