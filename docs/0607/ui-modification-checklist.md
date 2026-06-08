# myteam UI 修改清单

> 基于 2026-06-07 代码审计整理（frontend/ `index.html` + `style.css` + `app.js`）
> 状态：□ 待处理  ◔ 进行中  ✓ 已完成  — 不处理
> 
> **最后更新：2026-06-07 — P0(5/5) ✓  P1(5/5) ✓  CSS 模块化 ✓  JS 模块化 ✓  Bug 修复：init() 未调用 ✓**

---

## P0 — 功能缺陷 / 合规阻塞 ✓ 全部完成

- [✓] **移动端侧栏删除按钮不可用** — `.s-del` 的 `opacity: 0` 仅响应 hover，移动端无法触发
  - 修复：`@media (max-width: 820px)` 下 `.sidebar-item .s-del { opacity: 1 }`
  - 文件：`style.css` / `pages.css`

- [✓] **移动端消息复制按钮不可用** — `.msg-copy` 初始 `opacity: 0`，移动端无 hover
  - 修复：`@media (max-width: 820px)` 下 `.msg-copy { opacity: 0.7 }`
  - 文件：`style.css` / `pages.css`

- [✓] **浅色主题 tertiary 文字对比度不足 AA** — `#64748b` 在 `#ffffff` 上约 3.8:1 < 4.5:1
  - 修复：`[data-theme="light"] { --text-tertiary: #475569 }`
  - 文件：`style.css`

- [✓] **搜索弹窗定位错位** — `.search-results` 定位不跟随滚动
  - 修复：`.sidebar-search { position: sticky; top: 0; z-index: 1 }`
  - 文件：`layout.css`

- [✓] **首页空状态按钮类名未定义** — 空状态按钮使用 `class="btn btn-outline"`，但 `.btn-outline` 无对应 CSS
  - 修复：新增 `.btn-outline` 样式
  - 文件：`components.css`

---

## P1 — 布局安全 / 样式脆断 ✓ 全部完成

- [✓] **项目子标签栏窄屏无横向滚动** — `.project-subnav` 在 <820px 视口下 6 个 tab 会挤在一起
  - 修复：`@media (max-width: 820px) { .project-subnav { overflow-x: auto; gap: 0; } .project-subnav .ptab { flex-shrink: 0; } }`
  - 文件：`pages.css`

- [✓] **任务列表行固定列宽溢出风险** — `.task-row` 用固定列宽
  - 修复：`.task-id, .task-tokens { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }`
  - 文件：`pages.css`

- [✓] **空状态伪元素与动态内容冲突** — `.empty::before` 固定插入 📭
  - 修复：新增 `.empty.no-icon::before { display: none }`
  - 文件：`pages.css`

- [✓] **more-dropdown / theme-dropdown 用 fixed 定位** — 固定在视口而非触发元素附近
  - 部分修复：JS 已通过 `getBoundingClientRect` 动态计算 `top/right`
  - 文件：`app.js`（原有实现已含此逻辑）

- [✓] **theme-dropdown HTML 位置在 body 末尾但 style 引用固定定位** — 需确保 z-index
  - 修复：统一 `z-index: 999999`
  - 文件：`components.css`

---

## 工程债：CSS 模块化 ✓ 已完成

| 文件 | 行数 | 职责 |
|------|:----:|------|
| `tokens.css` | 89 | 设计令牌（仅变量） |
| `layout.css` | 95 | 布局系统：nav、sidebar、content、responsive |
| `components.css` | 140 | 组件：buttons、modals、forms、toast、dropdowns |
| `pages.css` | 393 | 各页面样式：dashboard、chat、group、project、management、settings |
| `style.css` | 113 | 入口：reset、变量、light theme、responsive overrides |
| **合计** | **830** | 从原 1545 行精简 46% |

---

## 工程债：JS 模块化 ✓ 已完成

| 文件 | 行数 | 职责 |
|------|:----:|------|
| `ui-core.js` | 644 | S 状态、DOM 引用、工具函数、icons、toast、confirm、消息渲染 |
| `chat.js` | 311 | Agent 对话、私聊、流式、归档 |
| `group.js` | 328 | 群组对话、@mention、群组管理 |
| `project.js` | 612 | 项目详情、DAG、交付物、执行树、成本 |
| `manage.js` | 165 | Agent 列表、管理表格、创建 Agent |
| `settings.js` | 98 | 设置面板 |
| `dashboard.js` | 31 | 首页看板 |
| `app.js` | 252 | 入口：init、switchTab、event listeners |
| **合计** | **2441** | 从原 3602 行精简 32% |

---

## 剩余待处理（P2+）

## P2 — 可读性与视觉一致性

- [ ] **10px 字号多处使用，低于舒适阅读阈值**
  - `--text-xs: 10px` → 建议全局最小字号统一到 11px
  - 受影响位置：`.s-sub`、`.msg-time`、`.field-hint`、`.activity-meta`、`.step-tokens`
  - 文件：`tokens.css` line 31 / `style.css` 各引用处

- [ ] **侧栏搜索输入框字号偏小** — 12px vs base 13px
  - 改法：`.sidebar-search input { font-size: 13px }`
  - 文件：`style.css` line 872-875

- [ ] **聊天消息在宽屏下最大宽度受限** — `.message.agent { max-width: 82% }` 在 >1440px 上显得窄
  - 改法：`max-width: min(90%, 900px)` 或媒体查询加宽
  - 文件：`style.css` line 326-328（及 407）

- [ ] **`.btn-sm` 样式双语义** — sidebar-title 中为 32px 正方形（`width:32px; padding:0`），add-member-row 中为自动宽度文字按钮（`width:auto`）
  - 改法：区分两个变体 `.btn-sm-icon` 和 `.btn-sm`，或通过上下文选择器控制
  - 文件：`style.css` line 1234-1243

- [ ] **浅色主题毛玻璃效果几乎不可见**
  - 改法：`[data-theme="light"] { --glass-bg: rgba(255,255,255,0.9); --glass-border: rgba(15,23,42,0.06); }`
  - 文件：`style.css` line 963-982

---

## P3 — 交互体验优化

- [ ] **消息历史加载完无视觉反馈** — `loadDmHistory` 成功后 DOM 被全量替换，可能丢失滚动位置
  - 改法：diff 更新而非 innerHTML 全量重建，保存并恢复 scrollTop
  - 文件：`app.js` line 2039-2061

- [ ] **实时更新缺少"有新数据"视觉提示** — SSE 推送新事件时屏幕无变化告知用户
  - 改法：新增内容闪烁动画（淡黄闪光 2s）：`.exec-node.new-data { animation: flash-new 2s }`
  - 文件：`style.css`（需新增 `@keyframes`）/ `app.js`

- [ ] **搜索栏缺少一键清除按钮** — 输入内容后需手动全删
  - 改法：input type="search" 自带 `×`，或添加自定义清除按钮
  - 文件：`index.html` line 46-49（`type="search"` 已设，浏览器应显示清除——检查是否被 CSS 覆盖）

- [ ] **可折叠面板缺少 aria 状态** — `.thinking-section` 折叠切换时未同步 `aria-expanded`
  - 改法：JS 中 toggle 时同步设置 `aria-expanded="true/false"`
  - 文件：`style.css` line 469-476 / `app.js` 相关行（无对应切换函数，需补充）

- [ ] **对话搜索结果显示"无匹配归档"的交互** — 当前显示为不可点击的 search-item，点击无反馈
  - 改法：改为 hint 文本或禁用态，避免用户误以为是可点击结果
  - 文件：`app.js` line 570-585

- [ ] **侧栏 active 指示条在 hover 时被替代** — `.sidebar-item.active::before` 的 primary 色条在 hover 时被 `border-color: var(--primary)` 替代，色条效果冗余
  - 改法：决定只用 hover 边框或 left bar，二选一
  - 文件：`style.css` line 709-751

---

## P4 — 信息架构微调

- [ ] **项目详情 6 个子 Tab 可精简**
  - 当前：概览 / DAG / 执行过程 / 时间线 / 交付物 / 成本
  - 建议：合并"时间线"到"执行过程"（时间维 vs 树维，同一数据不同视图），合并"成本"到"概览"（概览底部已有成本摘要）
  - 文件：`index.html` line 202-271 / `app.js` line 963-972

- [ ] **Agent 管理表格列过多** — 7+ 列在 <=1280px 下溢出
  - 改法：关键列（名称/状态/后端/模型）固定前置，次要列隐藏 + 展开按钮
  - 文件：`app.js`（表格渲染逻辑）

- [ ] **设置页卡片密度不均** — 部分卡片只有 1-2 字段（如"协作引擎"节），大块空白
  - 改法：合并稀疏卡片，或改用单列紧凑布局
  - 文件：`index.html` line 311-412 / `style.css` line 674-705

---

## P5 — 代码维护性

- [ ] **CSS 重复声明** — `.chat-actions` 定义 2 次（line 283 / 1276），`.deliverable-body` 定义多次（line 1214 / 1382）
  - 改法：合并去重

- [ ] **未定义的 CSS 变量引用** — `var(--mono)`、`var(--accent)`、`var(--bg-secondary)` 出现但未在 tokens 中定义
  - 改法：替换为正式 token 或添加定义

- [ ] **图标系统 `hidrateIcons` 拼写错误** — 应为 `hydrateIcons`，函数名 `hydrateIcons` 正确但调用处 `hidrateIcons`（无 h）
  - 改法：统一拼写
  - 文件：`app.js` line 2001-2007

---

## 修改优先级速览

```
P0 ████████░░ 5 项  功能缺陷 / 合规
P1 ██████░░░░ 5 项  布局安全 / 脆断
P2 █████░░░░░ 5 项  可读性与视觉
P3 ████░░░░░░ 6 项  交互体验
P4 ███░░░░░░░ 3 项  信息架构
P5 ██░░░░░░░░ 3 项  维护性
```

**建议执行顺序**：P0 → P1 → P3 → P2 → P4 → P5，先修功能缺陷再打磨视觉。
