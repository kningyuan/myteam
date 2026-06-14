import { useCallback, useEffect, useRef, useState } from "react"
import { subscribeResource, type ResourceKey } from "@/lib/dataRefresh"

export function useResourceQuery<T>(
  resourceKey: ResourceKey,
  fetcher: () => Promise<T>,
  initial: T,
): { data: T; loading: boolean; error: string; reload: () => void } {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const reload = useCallback(() => {
    setLoading(true)
    setError("")
    fetcherRef
      .current()
      .then((next) => {
        setData(next)
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "加载失败")
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    reload()
    return subscribeResource(resourceKey, reload)
  }, [resourceKey, reload])

  return { data, loading, error, reload }
}

/** mutation 触发 invalidate 时执行 callback（用于详情页与列表同步）。 */
export function useOnResourceInvalidate(resourceKey: ResourceKey, callback: () => void): void {
  const cbRef = useRef(callback)
  cbRef.current = callback
  useEffect(() => {
    return subscribeResource(resourceKey, () => cbRef.current())
  }, [resourceKey])
}
