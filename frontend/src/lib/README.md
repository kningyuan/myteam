# lib — 前端纯逻辑层

跨页面共享的纯函数 / 工具，不含 React 组件。按领域子目录组织：

- `api/` — 后端 API 客户端（`index.ts` 为 barrel 出口）
- `chat/` — 对话与圆桌逻辑
- `project/` — 项目编排视图派生
- `ports/` — 后端端口抽象（ChatPort / ProjectsPort，切换 hub 数据源）

## 根目录文件（跨领域单例，不归属任一领域）

- `utils.ts` — shadcn `cn()` 类名合并（被所有 `components/ui/*` 引用）
- `theme.tsx` — 主题 Provider（dark/light）
- `thinking.ts` — 思考流事件归一（被 chat 与 project 共用）
- `markdown.ts` — GFM 子集 Markdown 渲染
- `dataRefresh.ts` — 跨页面资源缓存失效总线
- `sortByModified.ts` — 通用「最近修改在前」排序
- `api.ts` — **deprecated** re-export shim，等导入迁移完后移除

## 测试

```bash
npm test            # 全部
npm test -- src/lib # 仅 lib
```

每个领域子目录有 README 说明其文件清单与依赖。
