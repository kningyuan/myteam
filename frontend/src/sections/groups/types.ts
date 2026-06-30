/** 圆桌发言进度（立论/对齐/汇总等阶段） */
export type RoundtableProgress = {
  index: number
  total: number
  round?: number
  phase?: string
  facilitator?: string
}
