import { useEffect, useReducer } from "react"
import {
  consumeRestoreDraft,
  ensureAgentChatLoaded,
  getAgentChatSnapshot,
  subscribeAgentChat,
} from "@/lib/agentChatStream"

export function useAgentChat(agentId: string) {
  const [, bump] = useReducer((x: number) => x + 1, 0)

  useEffect(() => subscribeAgentChat(agentId, bump), [agentId])

  useEffect(() => {
    void ensureAgentChatLoaded(agentId)
  }, [agentId])

  return getAgentChatSnapshot(agentId)
}

export function useRestoreDraft(agentId: string, setDraft: (v: string) => void) {
  const snap = useAgentChat(agentId)
  useEffect(() => {
    if (snap.restoreDraft) {
      setDraft(snap.restoreDraft)
      consumeRestoreDraft(agentId)
    }
  }, [agentId, snap.restoreDraft, setDraft])
}
