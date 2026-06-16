/** 跨页面资源缓存失效 — mutation 后 invalidate，列表 hook 自动重拉。 */

export type ResourceKey =
  | "groups"
  | "agents"
  | "projects"
  | "workflows"
  | "task-types"
  | "delivery-templates"
  | "skill-library"
  | "skill-matrix"
  | "skill-drafts"
  | "mcp-library"
  | "dashboard"
  | "config"

type Listener = () => void

const listeners = new Map<ResourceKey, Set<Listener>>()

const DASHBOARD_DEPS: ResourceKey[] = ["projects", "groups", "agents", "workflows"]

function expandKeys(keys: ResourceKey[]): ResourceKey[] {
  const out = new Set<ResourceKey>(keys)
  for (const key of keys) {
    if (DASHBOARD_DEPS.includes(key)) out.add("dashboard")
  }
  return [...out]
}

export function subscribeResource(key: ResourceKey, listener: Listener): () => void {
  let set = listeners.get(key)
  if (!set) {
    set = new Set()
    listeners.set(key, set)
  }
  set.add(listener)
  return () => set!.delete(listener)
}

export function invalidateResources(...keys: ResourceKey[]): void {
  if (!keys.length) return
  for (const key of expandKeys(keys)) {
    listeners.get(key)?.forEach((fn) => {
      try {
        fn()
      } catch {
        /* ignore subscriber errors */
      }
    })
  }
}
