# 第三方 MCP 接入指南

> myteam 不强制自研 MCP。社区已有大量高质量 MCP 服务器，直接接入即可。
> 本文档列出常用 MCP 及接入步骤。管理面板「MCP」Tab 可一键添加。

## 一、常用第三方 MCP 推荐表

| MCP 名称 | 功能 | 安装命令 | 适用 Agent |
|:---------|:-----|:---------|:----------|
| **@modelcontextprotocol/server-filesystem** | 文件读写 | `npx -y @modelcontextprotocol/server-filesystem <path>` | research / developer / tester |
| **@modelcontextprotocol/server-brave-search** | Brave 搜索 | `npx -y @modelcontextprotocol/server-brave-search` | research / seo |
| **@modelcontextprotocol/server-puppeteer** | 浏览器自动化 / 抓取 | `npx -y @modelcontextprotocol/server-puppeteer` | research / tester |
| **@modelcontextprotocol/server-sqlite** | SQLite 查询 | `npx -y @modelcontextprotocol/server-sqlite --db-path <path>` | analyst |
| **@modelcontextprotocol/server-github** | GitHub API | `npx -y @modelcontextprotocol/server-github` | developer |
| **@modelcontextprotocol/server-fetch** | URL 抓取 | `npx -y @modelcontextprotocol/server-fetch` | research |
| **@modelcontextprotocol/server-memory** | 持久记忆 | `npx -y @modelcontextprotocol/server-memory` | 通用 |

## 二、接入步骤

### 方式 A：管理面板一键添加（推荐）

1. 打开 Hub → 「MCP」Tab
2. 点击「新增 MCP」
3. 填写：server_id / name / command / environment（API Key 等）
4. 保存 → 在「Agent 管理」中为对应 Agent 勾选该 MCP
5. Agent 执行任务时自动加载

### 方式 B：手动编辑 mcp_registry.json

```json
{
  "version": "1.0",
  "servers": {
    "brave-search": {
      "name": "Brave 搜索",
      "description": "实时网络搜索",
      "enabled": true,
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-brave-search"],
      "environment": {
        "BRAVE_API_KEY": "<your-key>"
      }
    }
  }
}
```

### 方式 C：workflow-creator 自动配置

在 sop-to-workflow 描述中提到「需要搜索/抓取/数据库」等能力，workflow-creator 会自动建议挂载对应 MCP。

## 三、MCP 隔离原则

- 每个 Agent 的 MCP 配置独立于用户默认 CLI 的 MCP 配置
- Agent workspace 的 `.opencode/mcp.json` / `.claude/mcp.json` 由 `sync_workspace_mcp()` 自动生成
- 未在 `agents_registry.json` 中配置的 MCP 不会加载

## 四、自定义 MCP

如果社区没有需要的 MCP，可以自建：

1. 按 MCP 协议实现 stdio server（Python/Node/Go 均可）
2. 在 mcp_registry.json 注册
3. 为 Agent 挂载

详见 [MCP 官方文档](https://modelcontextprotocol.io)
