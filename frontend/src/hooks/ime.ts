import { useRef } from "react"
import type { CompositionEventHandler, KeyboardEvent } from "react"

/** 中文等 IME 组词期间，Enter 用于上屏而非发送消息。 */
export function useImeCompositionGuard() {
  const composingRef = useRef(false)

  const compositionProps = {
    onCompositionStart: () => {
      composingRef.current = true
    },
    onCompositionEnd: () => {
      composingRef.current = false
    },
  } satisfies {
    onCompositionStart: CompositionEventHandler
    onCompositionEnd: CompositionEventHandler
  }

  function isImeComposing(e: KeyboardEvent): boolean {
    return composingRef.current || e.nativeEvent.isComposing || e.keyCode === 229
  }

  return { compositionProps, isImeComposing }
}
