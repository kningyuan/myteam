import { ChevronRight, File, Folder } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import type { SkillTreeNode } from "@/lib/api/workflows"
import { cn } from "@/lib/utils"

function parentPaths(filePath: string): string[] {
  const parts = filePath.split("/").filter(Boolean)
  if (parts.length <= 1) return []
  const out: string[] = []
  for (let i = 1; i < parts.length; i += 1) {
    out.push(parts.slice(0, i).join("/"))
  }
  return out
}

function TreeNode({
  node,
  depth,
  activePath,
  expanded,
  onToggleDir,
  onSelectFile,
}: {
  node: SkillTreeNode
  depth: number
  activePath: string
  expanded: Set<string>
  onToggleDir: (path: string) => void
  onSelectFile: (path: string) => void
}) {
  const isDir = node.type === "dir"
  const isOpen = isDir && expanded.has(node.path)
  const isActive = !isDir && activePath === node.path

  if (isDir) {
    return (
      <div>
        <button
          type="button"
          className={cn("skill-tree-row", isOpen && "skill-tree-row-open")}
          style={{ paddingLeft: `${8 + depth * 14}px` }}
          onClick={() => onToggleDir(node.path)}
        >
          <ChevronRight className={cn("skill-tree-chevron", isOpen && "skill-tree-chevron-open")} />
          <Folder className="skill-tree-icon" />
          <span className="skill-tree-name">{node.name}</span>
        </button>
        {isOpen ? (
          <div>
            {(node.children ?? []).map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                activePath={activePath}
                expanded={expanded}
                onToggleDir={onToggleDir}
                onSelectFile={onSelectFile}
              />
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <button
      type="button"
      className={cn("skill-tree-row skill-tree-file", isActive && "active")}
      style={{ paddingLeft: `${22 + depth * 14}px` }}
      onClick={() => onSelectFile(node.path)}
    >
      <File className="skill-tree-icon" />
      <span className="skill-tree-name">{node.name}</span>
    </button>
  )
}

export function SkillFileTree({
  tree,
  activePath,
  defaultPath,
  onSelectFile,
}: {
  tree: SkillTreeNode[]
  activePath: string
  defaultPath?: string
  onSelectFile: (path: string) => void
}) {
  const initialExpanded = useMemo(() => {
    const set = new Set<string>()
    if (defaultPath) {
      for (const p of parentPaths(defaultPath)) set.add(p)
    }
    return set
  }, [defaultPath])

  const [expanded, setExpanded] = useState(initialExpanded)

  useEffect(() => {
    setExpanded(initialExpanded)
  }, [initialExpanded, tree])

  function toggleDir(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  if (!tree.length) {
    return <p className="hint p-2 text-xs">暂无文件</p>
  }

  return (
    <div className="skill-tree">
      {tree.map((node) => (
        <TreeNode
          key={node.path}
          node={node}
          depth={0}
          activePath={activePath}
          expanded={expanded}
          onToggleDir={toggleDir}
          onSelectFile={onSelectFile}
        />
      ))}
    </div>
  )
}
