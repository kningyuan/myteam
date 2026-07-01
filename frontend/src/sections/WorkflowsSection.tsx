import { useState, useMemo } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { listWorkflows, workflowDisplayName } from "@/lib/api/workflows"
import { useResourceQuery } from "@/hooks/useResourceQuery"
import { sortByModifiedDesc } from "@/lib/sortByModified"
import { WorkflowEditor } from "@/components/workflow/WorkflowEditor"
import { DiscordShell, ListColumn, WelcomePane } from "@/components/layout/DiscordShell"
import { ListItemRow } from "@/components/layout/ListItemRow"
import { RunSegmentNav } from "@/components/RunSegmentNav"
import { Button } from "@/components/ui/button"

export function WorkflowsSection() {
  const { workflowId } = useParams()
  const navigate = useNavigate()
  const { data: workflows } = useResourceQuery("workflows", listWorkflows, [])
  const [editorDirty, setEditorDirty] = useState(false)

  const sortedWorkflows = useMemo(() => sortByModifiedDesc(workflows), [workflows])

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
            <Button size="sm" onClick={() => navigateWorkflow("/run/workflows/new")}>
              新建
            </Button>
          }
          tabs={<RunSegmentNav />}
        >
          {sortedWorkflows.map((w) => (
            <ListItemRow
              key={w.id}
              name={workflowDisplayName(w)}
              sub={`${w.task_count ?? "—"} 任务`}
              avatar={workflowDisplayName(w)}
              active={w.id === workflowId}
              onClick={() => navigateWorkflow(`/run/workflows/${encodeURIComponent(w.id)}`)}
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
            navigate(`/run/workflows/${encodeURIComponent(id)}`, { replace: true })
          }}
          onDeleted={() => {
            setEditorDirty(false)
            navigate("/run/workflows")
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
