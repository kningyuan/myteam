import { useEffect, useState } from "react"
import { Copy, Download } from "lucide-react"
import { toast } from "sonner"
import {
  getDeliverableBundle,
  getDeliverableFile,
  type DeliverableFile,
} from "@/lib/api/projects"
import { MarkdownBody } from "@/components/MarkdownBody"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

const KIND_LABEL: Record<string, string> = {
  script: "脚本",
  doc: "文档",
  output: "产出",
  test: "测试",
  data: "数据",
  file: "文件",
}

const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  running: "运行中",
  in_progress: "运行中",
  pending: "等待中",
  failed: "失败",
}

export function ProjectDeliverablePanel({
  projectId,
  tasks,
  selectedTaskId,
  onSelectTask,
}: {
  projectId: string
  tasks: { id: string; name?: string; status?: string }[]
  selectedTaskId: string
  onSelectTask: (id: string) => void
}) {
  const [files, setFiles] = useState<DeliverableFile[]>([])
  const [content, setContent] = useState("")
  const [activePath, setActivePath] = useState("")
  const [meta, setMeta] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedTaskId) return
    setLoading(true)
    getDeliverableBundle(projectId, selectedTaskId)
      .then((bundle) => {
        const fs = bundle.files ?? []
        setFiles(fs)
        const verify = fs.find((f) => /verify\.log$/i.test(f.path || f.name || ""))
        const primary = bundle.primary?.content || bundle.content || ""
        if (primary) {
          setContent(primary)
          setActivePath("")
          setMeta(`${fs.length} 个文件 · 主文档预览`)
        } else if (verify) {
          setActivePath(verify.path)
          return getDeliverableFile(projectId, selectedTaskId, verify.path).then((f) => {
            setContent(f.content || "")
            setMeta(`Gate 校验 · ${verify.path}`)
          })
        } else if (fs[0]) {
          setActivePath(fs[0].path)
          return getDeliverableFile(projectId, selectedTaskId, fs[0].path).then((f) => {
            setContent(f.content || "")
            setMeta(`${KIND_LABEL[f.kind || ""] || "文件"} · ${fs[0].path}`)
          })
        } else {
          setContent("")
          setMeta("该任务暂无交付物")
        }
      })
      .catch((e: Error) => {
        setContent("")
        setMeta(`加载失败：${e.message}`)
      })
      .finally(() => setLoading(false))
  }, [projectId, selectedTaskId])

  async function loadFile(path: string) {
    setLoading(true)
    try {
      const f = await getDeliverableFile(projectId, selectedTaskId, path)
      if (!f.exists) {
        toast.error("文件不存在")
        return
      }
      setContent(f.content || "")
      setActivePath(path)
      setMeta(`${KIND_LABEL[f.kind || ""] || "文件"} · ${path}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }

  function copyContent() {
    if (!content) return
    navigator.clipboard.writeText(content).then(
      () => toast.success("已复制"),
      () => toast.error("复制失败"),
    )
  }

  function downloadContent() {
    if (!content) return
    const ext = activePath.includes(".") ? activePath.split(".").pop() : "md"
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = `${selectedTaskId.replace(/[^\w.-]/g, "_")}.${ext}`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const taskName = tasks.find((t) => t.id === selectedTaskId)?.name

  return (
    <div className="deliverable-workspace">
      <div className="deliverable-task-nav" role="tablist" aria-label="任务">
        {tasks.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={selectedTaskId === t.id}
            className={cn("task-chip", selectedTaskId === t.id && "active")}
            onClick={() => onSelectTask(t.id)}
          >
            <span className="task-chip-name">{t.name || t.id}</span>
            <span className="task-chip-meta">
              <span className="task-chip-id">{t.id}</span>
              {t.status && (
                <span className={`task-chip-status s-${t.status}`}>
                  {STATUS_LABEL[t.status] || t.status}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>

      <div className="deliverable-head">
        <div className="min-w-0">
          <h3 className="deliverable-title">
            {taskName || selectedTaskId}
            <span className="deliverable-title-id">{selectedTaskId}</span>
          </h3>
          <p className="deliverable-meta">{loading ? "加载中…" : meta}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="outline" disabled={!content} onClick={copyContent}>
            <Copy className="h-3.5 w-3.5" />
            复制
          </Button>
          <Button size="sm" variant="outline" disabled={!content} onClick={downloadContent}>
            <Download className="h-3.5 w-3.5" />
            下载
          </Button>
        </div>
      </div>

      <div className="deliverable-layout">
        {files.length > 0 && (
          <aside className="deliverable-files">
            <div className="deliverable-files-title">文件</div>
            <ScrollArea className="flex-1 min-h-0">
              <div className="space-y-0.5 p-2">
                {files.map((f) => (
                  <button
                    key={f.path}
                    type="button"
                    className={cn(
                      "deliverable-file",
                      activePath === f.path && "active",
                      /verify\.log$/i.test(f.path || f.name || "") && "deliverable-file-verify",
                    )}
                    onClick={() => loadFile(f.path)}
                  >
                    <span className="deliverable-file-kind">{KIND_LABEL[f.kind || ""] || "文件"}</span>
                    <span className="deliverable-file-name">{f.name || f.path}</span>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </aside>
        )}
        <ScrollArea className="deliverable-body-wrap flex-1 min-h-0">
          <div className="deliverable-body markdown-body">
            {content ? <MarkdownBody content={content} /> : <p className="hint">（无内容）</p>}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
