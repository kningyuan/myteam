import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react"
import type { ProjectTask } from "@/lib/api/projects"
import { DAG_COLORS, DAG_LABELS } from "@/lib/project/project-labels"
import { Button } from "@/components/ui/button"

const SCALE_MIN = 0.35
const SCALE_MAX = 2.5
const NODE_MIN_W = 128
const NODE_MAX_W = 260
const NODE_PAD_X = 16
const NODE_PAD_Y = 10
const LABEL_LINE_H = 16
const META_LINE_H = 13
const CHAR_W_LABEL = 7.2
const CHAR_W_META = 5.8
const MAX_LABEL_CHARS_PER_LINE = 16
const MAX_META_CHARS_PER_LINE = 22

type DagNode = {
  id: string
  label: string
  meta: string
  status: string
  x: number
  y: number
  w: number
  h: number
}

type DagEdge = { from: DagNode; to: DagNode }

function lineCount(text: string, maxChars: number, maxLines: number) {
  if (!text) return 0
  return Math.min(maxLines, Math.max(1, Math.ceil(text.length / maxChars)))
}

function estimateNodeSize(label: string, meta: string) {
  const labelLines = lineCount(label, MAX_LABEL_CHARS_PER_LINE, 2)
  const metaLines = lineCount(meta, MAX_META_CHARS_PER_LINE, 2)
  const contentW = Math.max(
    Math.min(label.length, MAX_LABEL_CHARS_PER_LINE * labelLines) * CHAR_W_LABEL,
    meta ? Math.min(meta.length, MAX_META_CHARS_PER_LINE * metaLines) * CHAR_W_META : 0,
  )
  const w = Math.ceil(Math.min(NODE_MAX_W, Math.max(NODE_MIN_W, contentW + NODE_PAD_X * 2)))
  const h = Math.ceil(
    NODE_PAD_Y * 2 +
      labelLines * LABEL_LINE_H +
      (metaLines ? 4 + metaLines * META_LINE_H : 0),
  )
  return { w, h, labelLines, metaLines }
}

function layoutDag(tasks: ProjectTask[]) {
  if (!tasks.length) return { nodes: [] as DagNode[], edges: [] as DagEdge[], width: 400, height: 200 }

  const byId: Record<string, ProjectTask & { deps: string[] }> = {}
  for (const t of tasks) byId[t.id] = { ...t, deps: t.dependencies ?? [] }

  const level: Record<string, number> = {}
  const done: Record<string, boolean> = {}
  function assignLevel(id: string): number {
    if (level[id] !== undefined) return level[id]
    const t = byId[id]
    if (!t || !t.deps.length) {
      level[id] = 0
      return 0
    }
    const pl = Math.max(
      ...t.deps.map((d) => (done[d] ? level[d] + 1 : assignLevel(d) + 1)),
      0,
    )
    level[id] = pl
    done[id] = true
    return pl
  }
  for (const t of tasks) {
    try {
      assignLevel(t.id)
    } catch {
      level[t.id] = 0
    }
  }

  const layers: Record<number, string[]> = {}
  for (const [id, lv] of Object.entries(level)) {
    ;(layers[lv] ??= []).push(id)
  }

  const H_GAP = 28
  const V_GAP = 56
  const PAD = 24

  const nodes: DagNode[] = []
  const edges: DagEdge[] = []
  const layerData: {
    lv: number
    sized: ReturnType<typeof sizeTaskNode>[]
    layerW: number
    layerH: number
  }[] = []

  function sizeTaskNode(id: string) {
    const t = byId[id]
    const label = t?.name || id
    const stLabel = DAG_LABELS[t?.status || ""] || t?.status || ""
    const token = (t as ProjectTask & { token?: number }).token
    const meta = [stLabel, t?.agent, token ? `${token.toLocaleString()} tok` : ""]
      .filter(Boolean)
      .join(" · ")
    const size = estimateNodeSize(label, meta)
    return { id, t, label, meta, status: t?.status || "pending", ...size }
  }

  for (const [lvStr, ids] of Object.entries(layers).sort((a, b) => Number(a[0]) - Number(b[0]))) {
    const lv = Number(lvStr)
    const sized = ids.map(sizeTaskNode)
    const layerW = sized.reduce((sum, n, i) => sum + n.w + (i ? H_GAP : 0), 0)
    const layerH = Math.max(...sized.map((n) => n.h), 44)
    layerData.push({ lv, sized, layerW, layerH })
  }

  const width = Math.max(...layerData.map((l) => l.layerW), NODE_MIN_W) + PAD * 2
  let maxY = PAD

  for (const { lv, sized, layerW, layerH } of layerData) {
    const y = PAD + lv * (layerH + V_GAP)
    let x = (width - layerW) / 2

    for (const item of sized) {
      const node: DagNode = {
        id: item.id,
        label: item.label,
        meta: item.meta,
        status: item.status,
        x,
        y,
        w: item.w,
        h: item.h,
      }
      nodes.push(node)
      x += item.w + H_GAP
      maxY = Math.max(maxY, y + item.h)

      for (const dep of item.t?.deps ?? []) {
        const src = nodes.find((n) => n.id === dep)
        if (src) edges.push({ from: src, to: node })
      }
    }
  }

  return { nodes, edges, width, height: maxY + PAD }
}

type Props = {
  tasks: (ProjectTask & { token?: number | null })[]
  selectedId?: string
  onSelect?: (id: string) => void
}

export function ProjectDag({ tasks, selectedId, onSelect }: Props) {
  const markerId = useId().replace(/:/g, "")
  const wrapRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 12, y: 12 })
  const [userZoom, setUserZoom] = useState(false)
  const panRef = useRef<{ dragging: boolean; sx: number; sy: number; px: number; py: number }>({
    dragging: false,
    sx: 0,
    sy: 0,
    px: 0,
    py: 0,
  })

  const { nodes, edges, width, height } = useMemo(() => layoutDag(tasks), [tasks])

  const fitToView = useCallback(() => {
    const wrap = wrapRef.current
    if (!wrap || !width || !height) return
    const vw = wrap.clientWidth
    const vh = wrap.clientHeight
    if (vw < 16 || vh < 16) return
    const pad = 20
    const sx = (vw - pad) / width
    const sy = (vh - pad) / height
    const next = Math.min(1.25, Math.max(SCALE_MIN, Math.min(sx, sy)))
    setScale(next)
    setPan({ x: Math.max(8, (vw - width * next) / 2), y: Math.max(8, (vh - height * next) / 2) })
  }, [width, height])

  useEffect(() => {
    if (!userZoom) fitToView()
  }, [fitToView, userZoom, tasks.length])

  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap) return
    const ro = new ResizeObserver(() => {
      if (!userZoom) fitToView()
    })
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [fitToView, userZoom])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const s = panRef.current
      if (!s.dragging) return
      setPan({ x: s.px + (e.clientX - s.sx), y: s.py + (e.clientY - s.sy) })
    }
    const onUp = () => {
      panRef.current.dragging = false
      wrapRef.current?.classList.remove("dag-panning")
    }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
  }, [])

  if (!tasks.length) {
    return <div className="dag-empty">暂无任务</div>
  }

  return (
    <div className="dag-container">
      <div className="dag-toolbar">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2"
          onClick={() => {
            setUserZoom(true)
            setScale((s) => Math.min(SCALE_MAX, s + 0.15))
          }}
        >
          +
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2"
          onClick={() => {
            setUserZoom(true)
            setScale((s) => Math.max(SCALE_MIN, s - 0.15))
          }}
        >
          −
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          onClick={() => {
            setUserZoom(true)
            setScale(1)
            setPan({ x: 12, y: 12 })
          }}
        >
          1:1
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          onClick={() => {
            setUserZoom(false)
            fitToView()
          }}
        >
          适应
        </Button>
        <span className="dag-zoom-label">{Math.round(scale * 100)}%</span>
      </div>
      <div
        ref={wrapRef}
        className="dag-stage-wrap"
        onMouseDown={(e) => {
          if (e.button !== 0 || (e.target as HTMLElement).closest(".dag-node")) return
          panRef.current = { dragging: true, sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y }
          wrapRef.current?.classList.add("dag-panning")
        }}
        onWheel={(e) => {
          e.preventDefault()
          setUserZoom(true)
          setScale((s) => Math.min(SCALE_MAX, Math.max(SCALE_MIN, s + (e.deltaY > 0 ? -0.1 : 0.1))))
        }}
      >
        <div
          className="dag-stage"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }}
        >
          <svg
            viewBox={`0 0 ${width} ${height}`}
            width={width}
            height={height}
            className="dag-svg"
            role="img"
            aria-label="任务依赖图"
          >
            <defs>
              <marker
                id={markerId}
                viewBox="0 0 10 10"
                refX="10"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto"
              >
                <path d="M0 0L10 5L0 10z" fill="var(--color-muted-foreground)" />
              </marker>
            </defs>
            {edges.map((e, i) => {
              const x1 = e.from.x + e.from.w
              const y1 = e.from.y + e.from.h / 2
              const x2 = e.to.x
              const y2 = e.to.y + e.to.h / 2
              const cy = (y1 + y2) / 2
              const d = `M${x1},${y1} Q${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${cy} T${x2},${y2}`
              return (
                <path
                  key={i}
                  className="dag-edge"
                  d={d}
                  fill="none"
                  stroke="var(--color-muted-foreground)"
                  strokeWidth={1.5}
                  markerEnd={`url(#${markerId})`}
                />
              )
            })}
            {nodes.map((n) => {
              const color = DAG_COLORS[n.status] || DAG_COLORS.pending
              const selected = n.id === selectedId
              return (
                <g
                  key={n.id}
                  className={`dag-node status-${n.status}${selected ? " dag-selected" : ""}`}
                  onClick={() => onSelect?.(n.id)}
                  style={{ cursor: onSelect ? "pointer" : "default" }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault()
                      onSelect?.(n.id)
                    }
                  }}
                >
                  <rect
                    className="dag-node-bg"
                    x={n.x}
                    y={n.y}
                    width={n.w}
                    height={n.h}
                    rx={8}
                    fill={color}
                    stroke={selected ? "#fff" : color}
                    strokeWidth={selected ? 3 : 2}
                  />
                  <title>{`${n.label} · ${n.meta}`}</title>
                  <foreignObject x={n.x} y={n.y} width={n.w} height={n.h}>
                    <div className="dag-node-inner">
                      <div className="dag-node-label">{n.label}</div>
                      {n.meta && <div className="dag-node-meta">{n.meta}</div>}
                    </div>
                  </foreignObject>
                </g>
              )
            })}
          </svg>
        </div>
      </div>
    </div>
  )
}
