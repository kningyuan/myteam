import { useEffect, useRef, type CSSProperties, type ReactNode } from "react"
import { cn } from "@/lib/utils"

export function ResizableColumn({
  width,
  onWidthChange,
  minWidth,
  maxWidth,
  handleSide = "right",
  className,
  style,
  children,
}: {
  width: number
  onWidthChange: (width: number) => void
  minWidth: number
  maxWidth: number
  handleSide?: "left" | "right"
  className?: string
  style?: CSSProperties
  children: ReactNode
}) {
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  useEffect(() => {
    function onMove(event: MouseEvent) {
      if (!dragRef.current) return
      const delta =
        handleSide === "right"
          ? event.clientX - dragRef.current.startX
          : dragRef.current.startX - event.clientX
      onWidthChange(dragRef.current.startWidth + delta)
    }

    function onUp() {
      dragRef.current = null
      document.body.classList.remove("col-resizing")
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
      document.body.classList.remove("col-resizing")
    }
  }, [handleSide, onWidthChange])

  function onHandleDown(event: React.MouseEvent) {
    event.preventDefault()
    dragRef.current = { startX: event.clientX, startWidth: width }
    document.body.classList.add("col-resizing")
  }

  return (
    <div
      className={cn("resizable-column", className)}
      style={{
        width,
        minWidth,
        maxWidth,
        flexShrink: 0,
        ...style,
      }}
    >
      {children}
      <div
        className={cn(
          "resize-handle",
          handleSide === "left" ? "resize-handle-left" : "resize-handle-right",
        )}
        role="separator"
        aria-orientation="vertical"
        aria-label="拖动调节宽度"
        onMouseDown={onHandleDown}
      />
    </div>
  )
}
