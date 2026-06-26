import { useCallback, useState } from "react"

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function readStoredWidth(key: string, fallback: number, min: number, max: number) {
  try {
    const raw = localStorage.getItem(key)
    const value = Number(raw)
    if (Number.isFinite(value) && value >= min && value <= max) return value
  } catch {
    /* ignore */
  }
  return fallback
}

export function useColumnWidth(
  storageKey: string,
  defaultWidth: number,
  minWidth: number,
  maxWidth: number,
) {
  const [width, setWidthState] = useState(() =>
    readStoredWidth(storageKey, defaultWidth, minWidth, maxWidth),
  )

  const setWidth = useCallback(
    (next: number) => {
      const clamped = clamp(next, minWidth, maxWidth)
      setWidthState(clamped)
      try {
        localStorage.setItem(storageKey, String(clamped))
      } catch {
        /* ignore */
      }
    },
    [storageKey, minWidth, maxWidth],
  )

  return { width, setWidth, minWidth, maxWidth }
}
