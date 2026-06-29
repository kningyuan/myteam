# myteam 前端 UI 设计评审报告

> 评审日期：2026-06-29  
> 评审范围：`frontend/src/` 下全部 UI 组件、布局、样式、对话框、交互  
> 技术栈：React 18 + TypeScript + Tailwind CSS v4 + Radix UI + shadcn/ui 风格组件

---

## 一、整体架构与布局

### 布局模式

采用 Discord 式三栏布局（Rail Nav → List Column → Main Content），由 `DiscordShell` 统一承载。这是一个成熟且适合管理后台/工具型产品的选择。

### 优点

- 三栏职责划分清晰：Rail 导航（60px）→ 列表面板（可拖拽调宽，220-480px）→ 主内容区
- `ResizableColumn` 组件允许用户自由调节列宽，宽度持久化到 localStorage，体验好
- `WelcomePane` 空状态引导到位，有 radial-gradient 微光背景和图标装饰
- 全局 overflow: hidden 防止页面级滚动，各区域独立滚动，体验流畅

### 问题与建议

#### 1. 两套 Shell 共存，入口不一致

- `AppShell.tsx` 和 `DiscordShell.tsx` 两套布局并行存在，但只有 `DiscordShell` 在路由中被实际使用（Dashboard 使用 DiscordShell，AppShell 实际被废弃但仍保留）
- AppShell 中 sidebar 宽度 `w-[72px]` / `md:w-56` 与 DiscordShell 的 `--rail-width: 60px` + `--list-width: 300px` 完全不同，增加维护负担
- **建议：** 删除 `AppShell.tsx`，避免后续开发者困惑

#### 2. 主内容区缺少最大宽度约束的一致性

- Dashboard 用 `max-w-6xl`（约 72rem），但 ChatSection、ProjectsSection 等主内容区直接填满剩余宽度
- Dashboard 内容窄但 Chat 内容宽，页面切换时视觉跳变明显
- **建议：** 统一各页面内容区最大宽度约束，或在不需要限制的页面（如 Chat）明确不限制

#### 3. 底部没有 footer

- 整个应用无版权、版本号或帮助链接，底部空白
- **建议：** 在 Rail 底部或主内容底部添加简洁的版本/帮助信息

---

## 二、字体排版

### 字体栈

- 标题：`"Bricolage Grotesque", "PingFang SC", "Microsoft YaHei", sans-serif`
- 正文：`"DM Sans", "PingFang SC", "Microsoft YaHei", ui-sans-serif, system-ui, sans-serif`
- 代码：`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`

### 优点

- 标题与正文字体分离，层级清晰
- h1/h2/h3 统一使用 `var(--font-display)` + `letter-spacing: -0.03em`，视觉一致性好
- 中文回退字体 PingFang SC → Microsoft YaHei 覆盖 macOS / Windows

### 问题与建议

#### 1. Google Fonts 加载方式不确定

- `index.css` 中声明了 Bricolage Grotesque 和 DM Sans，但未看到 `<link>` 标签或 `@import` 引入
- 如果没有实际加载，会 fallback 到 PingFang SC / system-ui，导致设计意图丢失
- **建议：** 在 `index.html` 中添加 Google Fonts `<link>` 或确认已通过其他方式加载

#### 2. 字号层级过多，缺乏系统感

- `stat-card-value: 2rem`、`page-title: 1.75rem`、`workspace-header-bar h1: 20px`、`section-heading: 0.875rem`、`list-item-name: 14px`、`list-item-sub: 12px`、`activity-*: 10-11px` 等
- 最小字号到 `9px`（`.group-msg-fold-toggle`），在低分辨率屏幕上可能难以辨认
- **建议：** 定义 3-4 级字号 scale（如 `text-xs: 12px, text-sm: 14px, text-base: 16px, text-lg: 18px, text-xl: 24px`），减少随意取值

#### 3. font-weight 使用 650 这个非标准值

- 多处使用 `font-weight: 650`（如 `.page-title`、`.stat-card-value`、`.list-header`）
- 650 在大多数字体中不存在为独立字重，会 fallback 到 600 或 700，渲染行为不确定
- **建议：** 统一使用 `600`（semibold）或 `700`（bold）

---

## 三、按钮系统

### 组件定义（`button.tsx`）

- 使用 `class-variance-authority` 定义 3 种变体（default / outline / ghost）+ 2 种尺寸（default / sm）
- focus-visible 使用品牌色 ring，disabled 降低透明度

### 优点

- CVA variants 设计合理，使用 CSS 变量实现主题适配
- `active:scale-[0.98]` 提供按压缩放反馈
- `asChild` 支持将按钮样式应用到 `<Link>` 等元素

### 问题与建议

#### 1. 缺少 danger/destructive 变体

- 对话框中"删除对话窗口"按钮（`.more-menu-dropdown button.danger`）使用原生 `<button>` + CSS class 而非 Button 组件
- `chat-send-stop` 直接用 `!important` 覆盖样式
- **建议：** 在 button variants 中增加 `destructive` 变体（`bg-[var(--color-danger)] text-white`），统一危险操作样式

#### 2. 尺寸选择有限

- 仅 `default (h-9)` 和 `sm (h-8)` 两种尺寸
- 对话框中多处出现 `h-7 px-2 text-xs` 的自定义尺寸按钮（如 SkillCategoryManageDialog 的编辑按钮），未走组件规范
- **建议：** 增加 `xs` 尺寸（如 `h-7 px-2 text-xs`），覆盖小按钮场景

#### 3. ghost 变体样式过于简陋

- `hover:bg-[var(--color-accent)]` 但无 hover 时的视觉层次区分
- **建议：** 增加轻微的背景过渡色或 text 变化

---

## 四、对话框（Dialog）

### 组件定义（`dialog.tsx`）

- 基于 Radix UI Dialog，Overlay 为 `bg-black/60`，Content 居中弹出
- 标准四件套：Header / Title / Footer / Description
- 关闭按钮在右上角，hover 时 opacity 变化

### 优点

- Radix Dialog 提供了良好的可访问性（focus trap、aria 属性）
- `max-h-[90vh] overflow-y-auto` 处理了长内容溢出
- 内容切换动画（data-[state=open] animate-in / animate-out）

### 问题与建议

#### 1. 对话框内部对齐不一致

- `AgentEditDialog` 中表单字段使用 `grid gap-4 py-2`，但 hint 文字用 `text-xs` 无固定颜色变量（直接写了 `hint` class）
- `SkillCategoryManageDialog` 中用 `text-xs text-[var(--color-muted-foreground)]` 作为提示，`AgentEditDialog` 也用 `hint text-xs`，需确认 `.hint` class 是否有定义
- **建议：** 统一对话框内提示文字的样式（创建 `.hint` 为 `color: var(--color-muted-foreground); font-size: 0.75rem; margin-top: 2px`）

#### 2. 缺少 DialogDescription

- `AgentEditDialog` 和 `AgentChatPanel` 中的 Config Dialog 都没有使用 `<DialogDescription>`，导致屏幕阅读器无法获取描述信息
- **建议：** 为每个 Dialog 添加 `DialogDescription`（可视觉隐藏），满足 WCAG 要求

#### 3. 表单字段间距不统一

- AgentEditDialog 各 Label-Input 间距为 `gap-4`（16px）
- SkillCategoryManageDialog 内部编辑区域间距为 `gap-2`（8px）
- **建议：** 统一对话框内表单间距为 `gap-4`

#### 4. 长列表滚动区域样式粗糙

- AgentEditDialog 中的 Skill 勾选列表和 MCP 列表使用 `max-h-56 overflow-y-auto rounded-md border p-2`，没有 ScrollArea 组件
- 多个 checkbox 列表使用原生 `<input type="checkbox">`，样式在不同浏览器表现不一
- **建议：** 使用 `ScrollArea` 包裹长列表，考虑统一 checkbox 样式组件

---

## 五、颜色系统

### 优点

- 完善的 CSS 变量体系（约 30+ 变量），dark/light 双主题完整
- `color-mix()` 现代用法实现透明度混合（如 `color-mix(in srgb, var(--color-brand) 30%, var(--color-border))`），避免了硬编码 rgba
- 品牌色 `#6f85ff` 在深色背景上对比度充足
- badge 颜色系统（purple/blue/green/orange/gray）覆盖多种语义
- body 背景添加了微妙的 noise texture（SVG feTurbulence），增加了质感
- 主题切换带 `transition: background 0.3s var(--ease-ui), color 0.3s var(--ease-ui)` 平滑过渡

### 问题与建议

#### 1. light 主题缺少部分变量覆盖

- `--color-primary` 和 `--color-primary-foreground` 在 `[data-theme="light"]` 中没有重定义
- `--color-brand` 也没有被 light 主题覆盖（默认 #6f85ff 在浅色背景可能不够醒目）
- **建议：** 补全 light 主题中缺失的变量，特别是 `--color-primary`、`--color-brand`

#### 2. 部分硬编码颜色值

- `.badge-purple` 等使用 `!important` + 硬编码 `rgba()` 值，在 light 主题下可能不协调
- `.chat-send-stop` 用 `#ec5b59` 而非 `var(--color-danger)`（其本身定义 `--color-danger: #e9585c`，两者不完全一致）
- `.group-msg-bubble.own` 中 `rgba(111, 133, 255, 0.15)` 硬编码
- **建议：** 统一使用 CSS 变量，去除硬编码颜色值和 `!important`

#### 3. focus-visible ring 在某些输入框不一致

- `Input` 组件用 `focus-visible:ring-[3px] ring-[var(--color-brand)]/25`
- `Select` 用 `focus:ring-2 ring-[var(--color-brand)]/40`
- `Textarea` 用 `focus-visible:ring-2 ring-[var(--color-brand)]/40`
- 三者 ring 宽度和透明度不同
- **建议：** 统一所有输入组件的 focus ring 样式

---

## 六、细节与交互

### 优点

- 主题切换带旋转动画（`.theme-toggle-icon` transform rotate），体验细腻
- Rail logo hover 有 `border-radius` + `transform` + `box-shadow` 三重过渡，类似 Discord 风格
- 列表项 active 状态使用品牌色填充 + 白色文字，视觉层次分明
- `content-fade-in` 入场动画（opacity + translateY）简洁有效
- 可拖拽列宽 + resize cursor 反馈（`body.col-resizing * { cursor: col-resize !important }`）
- 搜索框使用 SVG 背景图标 + pill 形状，focus 时边框高亮，体验好

### 问题与建议

#### 1. 原生 confirm/alert 与自定义 Dialog 混用

- `AgentChatPanel` 中 `handleClear` 和 `handleArchive` 使用 `window.confirm()`
- 其他地方使用 Sonner toast + 自定义 Dialog
- **建议：** 统一使用自定义确认 Dialog，避免原生 confirm 破坏沉浸感

#### 2. MoreMenu 组件缺少无障碍支持

- 自定义下拉菜单（非 Radix DropdownMenu），没有 ARIA 角色、keyboard navigation、focus trap
- 仅用 `document.addEventListener("click")` 关闭，escape 键无法关闭
- **建议：** 使用 Radix DropdownMenu 或至少添加 `role="menu"`、`role="menuitem"` 和 keyboard handler

#### 3. 列表项删除按钮始终可见

- `.list-item-del` 设置了 `opacity: 1`，而非 hover 时才显示
- CSS 中有 `.list-item:hover .list-item-del { opacity: 1 }` 但初始值就是 1，hover 规则无效
- **建议：** 初始设为 `opacity: 0`，hover 时过渡到 `opacity: 1`

#### 4. checkbox 未自定义样式

- AgentEditDialog、SkillCategoryManageDialog 等大量使用原生 `<input type="checkbox">`
- 在深色背景下，原生 checkbox 可能显示为系统默认浅色样式，与应用风格不协调
- **建议：** 创建自定义 Checkbox 组件或用 CSS `appearance: none` + 自定义样式

#### 5. scrollbar 样式只处理了 WebKit

- 只有 `::-webkit-scrollbar` 样式，Firefox 用户看到默认滚动条
- **建议：** 添加 `scrollbar-width: thin; scrollbar-color: var(--color-muted-foreground) transparent;`

#### 6. textarea 无自适应高度

- chat-input-bar 中 textarea 固定 `min-height: 72px` + `max-height: 180px`，但没有 auto-resize 逻辑
- 多行输入时需要手动滚动，体验不佳
- **建议：** 添加 JS auto-resize（根据 scrollHeight 自动调整高度）

---

## 七、响应式设计

### 问题与建议

#### 1. Rail 导航在移动端没有折叠/展开机制

- `--rail-width: 60px` 固定宽度，在窄屏（<768px）上占据过大比例
- 导航文字已通过 `hidden md:inline` 隐藏，但 60px rail 仍然占位
- 没有 hamburger menu 或 bottom navigation
- **建议：** 小屏幕时将 rail 收窄为图标条（~48px），或改为 bottom tab bar

#### 2. List Column 无最小宽度保护

- `--list-width: 300px` 在 `DiscordShell` 中直接使用
- 小屏时 list + main 并排显示会挤压主内容区
- **建议：** 小屏时 list column 改为 overlay/drawer 模式

---

## 八、代码质量

### 优点

- 组件拆分清晰：`ui/` 基础组件、`layout/` 布局组件、`chat/project/skills/` 业务组件
- 命名一致性好：CSS class 使用 kebab-case，组件使用 PascalCase
- `cn()` 工具函数（基于 clsx + tailwind-merge）处理 class 合并
- CSS 变量命名规范：`--color-*`、`--radius-*`、`--shadow-*`、`--ease-*`
- shadcn/ui 风格的 Radix 原语封装，可访问性基础好

### 问题

- `index.css` 文件过大（4200+ 行），建议按模块拆分（如 `layout.css`、`chat.css`、`project.css`、`workflow.css`）
- 两套 Shell 共存增加维护成本
- 部分组件内联样式与 CSS class 混用（如 `className="rounded-xl border ..."` 与预定义 CSS class 并存）

---

## 九、总结评分

| 维度       | 评分 | 说明                                                                 |
| ---------- | ---- | -------------------------------------------------------------------- |
| 整体架构   | 8/10 | Discord 三栏布局成熟，但两套 Shell 并存是技术债                       |
| 字体排版   | 7/10 | 字体选择好，但非标准 font-weight、字号层级过多                       |
| 颜色系统   | 8/10 | CSS 变量完善、双主题完整，light 主题有缺失、存在硬编码颜色           |
| 按钮系统   | 7/10 | CVA 设计合理但变体不足、danger 场景不统一                             |
| 对话框     | 7/10 | Radix 基础好，内部对齐不一致、缺 a11y 描述                            |
| 交互细节   | 7/10 | 动画细腻、resize 好用，原生 confirm 混用、无障碍待改善                |
| 响应式     | 5/10 | 桌面端体验好，移动端几乎无适配                                       |
| 代码质量   | 8/10 | 组件拆分清晰、命名一致，CSS 文件偏大（4200+ 行）                      |

**综合评分：7.1/10** — 桌面端体验扎实，细节打磨用心，主要短板在响应式适配和无障碍支持。

---

## 十、优先修复建议（按影响排序）

1. **删除废弃的 `AppShell.tsx`**，减少维护负担和新人困惑
2. **统一对话框内表单间距和提示样式**，创建 `.hint` 工具 class
3. **为 Dialog 添加 `DialogDescription`**，满足 WCAG 可访问性要求
4. **将原生 `window.confirm()` 替换为自定义确认弹窗**
5. **补全 light 主题缺失的 CSS 变量**（`--color-primary`、`--color-brand` 等）
6. **统一输入组件 focus ring 样式**（ring 宽度和透明度一致）
7. **列表删除按钮初始 opacity 改为 0**，hover 时显示
8. **统一 checkbox 样式**，创建自定义 Checkbox 组件
9. **拆分 `index.css`** 为按模块的多个 CSS 文件
10. **添加 Firefox scrollbar 样式**，统一跨浏览器滚动条体验
