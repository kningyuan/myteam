# lib/api — 后端 API 客户端

按领域拆分的 HTTP 客户端 + SSE 解析。`index.ts` 为 barrel re-export，是向后兼容的公共 API 出口。

## 核心文件

- `client.ts` — `hubFetch` / SSE 流解析（`readStreamWithAbort`、`parseSseDataLines`）
- `agents.ts` / `chat.ts` / `groups.ts` / `projects.ts` / `workflows.ts` / `mcp.ts` / `preferences.ts` / `prompts.ts` / `execute.ts` / `config.ts` — 各领域接口与类型

## 依赖关系

无内部依赖（最底层）。被依赖：`lib/ports/*`、`hooks/*`、`sections/*`、`components/*`。

## 测试

暂无。`client.ts` 的 SSE 解析逻辑适合后续补单测。
