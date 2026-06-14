import {
  cancelAgentChat,
  getAgentChatMessages,
  sendAgentChat,
} from "@/lib/api/chat"
import type { ChatPort } from "./ChatPort"

/** Default ChatPort — delegates to Hub REST via `@/lib/api/chat`. */
export const hubChatPort: ChatPort = {
  listMessages: getAgentChatMessages,
  streamChat: sendAgentChat,
  cancelChat: cancelAgentChat,
}
