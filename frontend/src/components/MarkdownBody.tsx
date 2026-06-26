import { renderMarkdown } from "@/lib/markdown"
import { cn } from "@/lib/utils"

export function MarkdownBody({ content, className }: { content: string; className?: string }) {
  if (!content.trim()) {
    return <p className="text-sm text-[var(--color-muted-foreground)]">（暂无内容）</p>
  }
  return (
    <div
      className={cn("markdown-body text-sm leading-relaxed", className)}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  )
}
