# lib/chat — 对话与圆桌

群聊 / 圆桌讨论的纯逻辑层（无 React、无 DOM）。

## 核心文件

- `agentChatStream.ts` — Agent 对话 SSE 流解析与状态机
- `groupChatLive.ts` — 群聊实时状态聚合
- `groupDiscussionSettings.ts` — 群讨论配置解析（与 skill_config.group_discussion 对齐）
- `agentLabels.ts` — Agent 显示名 / 角色标签 / 圆桌阶段文案

## 依赖关系

依赖：`@/lib/api/*`（类型）、`@/lib/thinking`（事件归一）。
被依赖：`sections/*`、`components/chat/*`。

## 测试

```bash
npm test -- src/lib/chat
```

- `groupDiscussionSettings.test.ts` — 配置解析与边界（回退默认 / clamp / trim）
