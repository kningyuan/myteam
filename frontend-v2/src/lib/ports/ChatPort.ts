import type { ChatMessage } from "@/lib/api/chat"

/** Pluggable chat boundary — UI/hooks depend on this, not HTTP details. */
export interface ChatPort {
  listMessages(agentId: string): Promise<ChatMessage[]>

  streamChat(
    agentId: string,
    message: string,
    onChunk: (event: Record<string, unknown>) => void,
    signal?: AbortSignal,
  ): Promise<void>

  cancelChat(agentId: string): Promise<void>
}
