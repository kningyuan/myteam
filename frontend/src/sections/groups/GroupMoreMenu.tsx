import { useEffect, useRef, useState } from "react"
import { MoreVertical } from "lucide-react"
import { Button } from "@/components/ui/button"

export function GroupMoreMenu({
  onClear,
  onDissolve,
  onMembers,
}: {
  onClear: () => void
  onDissolve: () => void
  onMembers: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("click", onDoc)
    return () => document.removeEventListener("click", onDoc)
  }, [open])

  return (
    <div className="more-menu-wrap" ref={ref}>
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen((v) => !v)}>
        <MoreVertical className="h-4 w-4" />
      </Button>
      {open && (
        <div className="more-menu-dropdown">
          <button type="button" onClick={() => { setOpen(false); onMembers() }}>
            成员管理
          </button>
          <button type="button" onClick={() => { setOpen(false); onClear() }}>
            清空消息
          </button>
          <button type="button" className="danger" onClick={() => { setOpen(false); onDissolve() }}>
            解散群组
          </button>
        </div>
      )}
    </div>
  )
}
