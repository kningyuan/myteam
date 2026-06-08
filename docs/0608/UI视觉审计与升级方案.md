# myteam UI 视觉审计与升级方案

> **日期**：2026-06-08  
> **范围**：`frontend/`（`index.html` + `tokens.css` / `layout.css` / `components.css` / `pages.css` / `style.css` + 各 `*.js` 渲染逻辑）  
> **方法**：源码静态审计 + 设计 Token 对照 + 与 `docs/0608/三问题诊断与升级方案.md` 交叉核对  
> **阅读对象**：UI/前端实施者、产品评审  
> **关联文档**：[三问题诊断与升级方案.md](./三问题诊断与升级方案.md)（功能/数据流 bug）、[交付评审方案-chat-dag-token.md](./交付评审方案-chat-dag-token.md)（并发/DAG/Token 交付）

---

## 0. 结论先行（TL;DR）

myteam Hub UI **骨架清晰**（顶栏 + 上下文侧栏 + 主内容区），已具备设计 Token 拆分、深浅主题、SVG 图标系统、聊天/项目/管理多 Tab 结构，整体方向是「深色开发者工具 + 毛玻璃 Arc 风」。

当前主要短板不在「有没有页面」，而在 **设计系统落地不完整**：

| 维度 | 现状评分 | 核心问题 |
|------|----------|----------|
| 布局与信息架构 | 7/10 | 结构合理；窄屏/表格/DAG 横向溢出体验差 |
| 配色与主题 | 6/10 | Token 有，但多处硬编码色、DAG/时间线脱离 Token |
| 字体与层级 | 5/10 | 字号偏小且层级扁平；`--text-xs`/`--text-sm` 定义冲突 |
| 按钮与对齐 | 6/10 | 组件类齐全，但空态按钮类名错误、侧栏标题区对齐不一 |
| 内容格式化 | 5/10 | Markdown 可用；数字/状态/长文本/emoji 混用不统一 |
| 样式工程化 | 4/10 | **大量 JS 引用的 class 无对应 CSS**（见 §3.6） |

**建议**：不做大重写，走 **「设计系统补全 + 高 ROI 视觉债清理」** 小版本，与功能修复 PR 并行但文件边界分开（CSS/组件 vs chat/project bug）。

---

## 1. 现状架构速览

### 1.1 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  #top-nav  汉堡 | Logo | 6 Tab | 主题 | 状态徽章              │
├──────────┬──────────────────────────────────────────────────┤
│ #sidebar │  #content（按 Tab 切换）                           │
│ 260px    │  home / chat / groups / projects / agents / settings│
│ 上下文列表│  主工作区（聊天、项目 DAG、管理表格等）              │
└──────────┴──────────────────────────────────────────────────┘
```

- **顶栏高度** 56px，Tab 使用渐变激活态（`--gradient-brand`）。
- **侧栏** 260px 固定宽；`<820px` 抽屉 + 遮罩。
- **主内容** 各 Tab 独立 `tab-content`，聊天/群组为全高 flex 列（header → messages → input）。

### 1.2 样式文件职责（已拆分，但仍有重复）

| 文件 | 职责 |
|------|------|
| `tokens.css` | 设计变量（色、字、间距、圆角、阴影） |
| `layout.css` | 全局布局、导航、侧栏、响应式 |
| `components.css` | 按钮、表单、Modal、Toast、徽章 |
| `pages.css` | 各 Tab 页面样式（聊天、项目、管理、设置） |
| `style.css` | Reset + **再次定义一套 `:root` Token** + 浅色主题补丁 + 窄屏覆盖 |

**问题**：`style.css` 与 `tokens.css` **双份 Token**，且存在不一致（见 §2.2）。

### 1.3 品牌与视觉语言

- **主色**：Indigo `#6366f1` → Violet 渐变（偏 Vercel/Linear 系）。
- **背景**：深色 `#0a0a0f` 基底 + 毛玻璃 elevated 层。
- **语义色**：success `#10b981`、warning `#f59e0b`、error `#ef4444`、info `#3b82f6`。
- **图标**：内联 SVG `data-icon` 系统（`ui-core.js`），风格统一。
- **装饰**：Logo、欢迎页、管理标题、事件标签大量 **emoji**（🤖💬📋🛠️），与线性图标系统 **视觉语言分裂**。

---

## 2. 分维度审计

### 2.1 布局（Layout）

#### 做得好的

- 聊天区 `flex` 列 + `min-height:0` 处理滚动，消息区与输入区分离合理。
- 项目详情 `project-subnav` 子 Tab（概览/DAG/执行/时间线/交付物/成本）信息架构清楚。
- 交付物 `deliverable-layout` 双栏（文件树 + 正文），`<768px` 单列折叠。

#### 需提升

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| L1 | **管理/设置页左右 padding 不一致** | `manage-panel`/`settings-panel` 30–40px vs `home-panel` 16–24px | 跨 Tab 切换时有「宽窄跳变」感 |
| L2 | **项目任务表 `task-row` 五列 grid 无表头** | `pages.css` `.task-row` | 列含义靠猜，扫描成本高 |
| L3 | **窄屏强制横向滚动** | `style.css` `@700px` `.task-row { min-width:460px }` | 移动端只能横滑，无卡片化降级 |
| L4 | **执行树 `exec-node-head` 五列 grid 过密** | `pages.css` 140px 固定列 | 长 task_id / 标题截断严重 |
| L5 | **侧栏标题行对齐不统一** | 群组只有 `+`，项目有 badge + `+` | 视觉重心不齐 |
| L6 | **首页空态 `empty-state-guide` 无样式** | `dashboard.js` 动态 HTML | 欢迎引导呈「裸 HTML」态（见 §3.6） |
| L7 | **`context-indicator` 无 CSS** | `index.html` 有 DOM，CSS 全库无匹配 | Token 进度条要么不可见要么无样式 |

#### 布局升级建议

1. **统一内容区内边距**：定义 `--content-padding-x/y`，home/manage/settings/project-body 共用。
2. **任务列表**：桌面保留 grid + 补 **sticky 表头**；`<700px` 改为 **卡片栈**（每任务一张卡，状态/Token 用 chip）。
3. **执行过程**：首列 chevron + 标题弹性列，meta/ts 换行到第二行（mobile stack）。
4. **补全 `context-indicator`**：置于 input-area 上方，细条 4px + 右侧 `ctx-label` 11px mono。

---

### 2.2 配色（Color）

#### Token 体系

`tokens.css` 已覆盖背景层级、文本四级、语义色、玻璃态变量，浅色主题在 `[data-theme="light"]` 有覆盖。

#### 问题清单

| # | 问题 | 证据 | 建议 |
|---|------|------|------|
| C1 | **双份 Token 不同步** | `tokens.css` `--text-xs:11px`；`style.css` `--text-xs:10px` | **单一来源**：`style.css` 只 `@import tokens.css` 或只保留 reset |
| C2 | **浅色主题 tertiary = secondary** | `tokens.css` L82–83 均为 `#475569` | tertiary 应更浅（如 `#64748b`），拉开层级 |
| C3 | **Markdown 代码块硬编码 `#0d0f14`** | `pages.css` `.md-inline-code` / `.md-codeblock` | 改用 `var(--bg-code)`；浅色已有 partial override |
| C4 | **侧栏未读徽章 `#ff4444` 硬编码** | `layout.css` `.s-badge` | 改用 `var(--error)` |
| C5 | **DAG 色板独立常量** | `dag-renderer.js` `DAG_COLORS` 与 `--success`/`--info` 不完全一致 | 映射到 CSS 变量或集中 `tokens.css` 的 `--status-*` |
| C6 | **时间线色板内联** | `timeline.js` `TL_TYPE_META` 各事件 `color:'#...'` | 抽到 Token；badge 用 `color-mix` 背景 |
| C7 | **活动行/工具块大量 `rgba(255,255,255,.02)`** | `pages.css` | 浅色主题下对比不足，需 `[data-theme=light]` 对等规则 |

#### 配色升级建议

新增语义 Token：

```css
--status-completed: var(--success);
--status-running: var(--info);
--status-failed: var(--error);
--status-pending: #93c5fd; /* 或纳入 Token */
--surface-code: var(--bg-code);
--surface-glass: var(--glass-bg);
```

DAG / Timeline / Status chip **统一引用**，避免「同状态不同绿」。

---

### 2.3 字体大小与排版（Typography）

#### 当前字号分布（实际使用）

| 用途 | 字号 | 评价 |
|------|------|------|
| 正文/消息/表单 | 13px (`--text-base`) | 偏紧凑，长时间阅读略累 |
| 侧栏项名称 | 14px | 合理 |
| 页面 H2 | 18–20px | 合理 |
| 辅助/时间/meta | 9–11px | **过小**，WCAG 大号文本边界模糊 |
| 执行树子项 | 10–12px 混用 | 层级靠字号区分不够 |

#### 问题

| # | 问题 | 说明 |
|---|------|------|
| T1 | `--text-xs` 与 `--text-sm` 在 tokens 中同为 11px | 层级失效 |
| T2 | `manage-panel .subtitle` **无全局 `.subtitle` 样式** | 仅 `settings-panel .subtitle` 有定义；管理页副标题可能继承正文色 |
| T3 | 表格内联 `style="font-size:10px"` | `manage.js` 工作目录列过小 |
| T4 | 中英文混排无 `line-height` 分级 | 部分区域 1.4，markdown 1.55，不统一 |
| T5 | 数字未统一 `tabular-nums` | 仅 `stat-num` 有；Token/成本列应对齐 |

#### 排版升级建议

1. **建立 Type Scale**（示例）：

   | Token | 值 | 用途 |
   |-------|-----|------|
   | `--text-xs` | 11px | 时间戳、badge |
   | `--text-sm` | 12px | 辅助说明、表头 |
   | `--text-base` | 14px | 正文（从 13 提到 14） |
   | `--text-md` | 15px | 侧栏项、聊天名 |
   | `--text-lg` | 18px | 区块标题 |

2. 全局 `body { font-size: var(--text-base); }`，减少魔法数字。
3. 成本/Token/百分比列统一 `font-variant-numeric: tabular-nums`。

---

### 2.4 字体颜色（Text Color）

#### 四级文本 Token

- `--text-primary` `#e4e4e7` — 主内容  
- `--text-secondary` `#a1a1aa` — 标签、表头  
- `--text-tertiary` `#71717a` — 辅助、placeholder  
- `--text-disabled` `#52525b` — 禁用  

#### 问题

| # | 问题 | 位置 |
|---|------|------|
| TC1 | 用户气泡白字 on 渐变 — OK；但链接在气泡内未单独定义 | 聊天 markdown |
| TC2 | `.hint` 与 `.subtitle` 都用 tertiary，与正文对比偏低 | 设置页大段说明 |
| TC3 | 状态色直接作文字色（`.task-row.status-*`）| 红/绿文字在深色底 OK，浅色需验 contrast |
| TC4 | 事件标签 emoji + 文字，颜色不可控 | `project.js` `EVENT_LABELS` |

#### 建议

- 正文说明用 `secondary`，仅 **元信息** 用 `tertiary`。
- 状态展示：**chip 背景 + 深色文字** 优于纯 colored text（已有 `.status-chip`，应推广到 task-row）。
- 链接统一 `--link: var(--info)`，visited/hover 状态补齐。

---

### 2.5 按钮位置与对齐（Buttons & Alignment）

#### 组件 inventory

| 类 | 用途 | 高度/对齐 |
|----|------|-----------|
| `btn-primary` | 主操作 | 约 36px，inline-flex 居中 |
| `btn-secondary` | 次操作 | 同 |
| `btn-icon` | 顶栏/聊天图标 | 偏小 padding，靠 hover 反馈 |
| `btn-clear` | 项目头「续跑/取消」| 12px 字，易与 `btn-icon` 混 |
| `btn-xs` | 表格内操作 | 右对齐列 |
| `#btn-send` | 发送 | 40px 高，与 textarea `align-items:flex-end` 底对齐 ✓ |

#### 问题

| # | 问题 | 证据 | 严重度 |
|---|------|------|--------|
| B1 | **首页空态按钮类名错误** | `dashboard.js`: `class="btn btn-primary"` — 无 `.btn` 定义 | **高** — 按钮几乎无样式 |
| B2 | **Modal footer 主按钮在右**（确认在右）— 符合桌面习惯；但 `confirm-modal` 与业务 modal 顺序一致 ✓ | — | — |
| B3 | **设置页「保存」孤悬左下**，与双列 card 网格无视觉锚点 | `index.html` | 中 |
| B4 | **侧栏 `btn-sm-icon` 与 badge 抢位** | 项目列表标题行 | 低 |
| B5 | **`chat-actions` 中 `btn-clear` hover 变红** | 组件设计为「危险暗示」| 「打开项目/协作群组」不应 hover 变红 | **中** |
| B6 | **删除按钮 emoji 🗑 vs 线性 trash 图标** | `project.js` 侧栏删除 | 不一致 |

#### 对齐升级建议

1. 修复 `dashboard.js`：`btn btn-primary` → `btn-primary`（及 secondary/outline）。
2. 为 `btn-clear` 拆两类：`btn-ghost`（中性）/ `btn-danger-ghost`（危险 hover）。
3. 设置页底部做 **sticky action bar**：「保存设置」右对齐 + 上方 `set-status` 反馈。
4. 侧栏标题统一 pattern：`[标题] [flex spacer] [badge?] [icon button]`。

---

### 2.6 内容展示与格式化（Content Formatting）

#### 聊天消息

- 用户/agent 气泡、分组、markdown 渲染、thinking 折叠、tool fold — **功能完整**。
- `max-width: 78%` / `72ch` 限制可读性良好。
- Activity timeline（工具调用）字号 10px，**信息密度过高**。

#### 项目域

| 内容类型 | 现状 | 问题 |
|----------|------|------|
| 任务列表 | grid 行 | 无表头；status `capitalize` 对中文无效 |
| DAG | 纯 SVG | **`.dag-empty` / `.dag-svg` 无 CSS**；节点 160×44 标题易截断 |
| 时间线 | `renderTimeline` | **`.tl-*` 全套 class 无 CSS** — 极可能裸列表 |
| 成本 | 行 + 动态 bar chart | **`.cost-bar-*` 无 CSS** |
| 交付物 | markdown-body | 较好；文件树 mono 字号 OK |
| 执行树 | 折叠树 | emoji 标签 + 多级 grid，扫描难 |

#### Markdown

- 自研 `markdown.js` + `.markdown-body` 样式覆盖 h1–h4、表、引用、代码。
- 代码块背景硬编码；表格 zebra 在浅色已修，深色 OK。
- 交付物正文 `max-height: min(70vh, 520px)` — 长文档内滚合理。

#### 数字与单位

- Token：`toLocaleString()` ✓
- 人民币：`fmtYuan` 条件显示 ✓
- 相对时间：侧栏 `formatRelativeTime` ✓
- **预算条** `budgetBar` 同时出现 `tokens / budget tok · pct%` — 格式尚可，但数字未 thousand-sep 统一

#### 空态 / 加载态

- `.empty` / `.loading` 有 emoji 前缀（📭⏳）— 风格可爱但与产品专业感略冲突
- 多种空态文案质量高（有操作指引）✓

---

## 3. 关键缺陷：未样式化的 class（P0 视觉债）

以下 class 在 **JS/HTML 中被引用**，但在 `*.css` 中 **零定义**（2026-06-08 静态检索）：

| Class 前缀 | 引用位置 | 后果 |
|------------|----------|------|
| `empty-state-guide`, `empty-state-actions` | `dashboard.js` | 首页无项目时引导区/layout/按钮全失效 |
| `dag-empty`, `dag-svg`, `dag-node` | `dag-renderer.js` | DAG 图无布局/空态样式 |
| `tl-empty`, `tl-list`, `tl-item`, `tl-line`, `tl-dot`, `tl-bar`, `tl-body`, `tl-header`, `tl-badge`, `tl-time`, `tl-summary` | `timeline.js` | **时间线 Tab 基本无视觉设计** |
| `cost-bar-chart`, `cost-bar-item`, `cost-bar-label`, `cost-bar-track`, `cost-bar-fill`, `cost-bar-val` | `project.js` | 成本页柱状图无样式 |
| `context-indicator`, `ctx-bar`, `ctx-fill`, `ctx-label` | `index.html` | 上下文 Token 指示器无效 |

**这是当前 UI 最大的「半成品」信号** — 功能代码先写，样式未跟进。

---

## 4. 可访问性（WCAG AA 快检）

| 项 | 状态 | 说明 |
|----|------|------|
| Focus 可见 | 部分 ✓ | `:focus-visible` 全局 2px primary outline |
| 文本对比度 | 待验 | 11px tertiary on `#0a0a0f` 可能低于 4.5:1 |
| 纯图标按钮 | 部分 ✓ | 多数有 `title`/`aria-label`；侧栏删除仅 icon |
| 键盘导航 | 未系统验证 | Tab 顺序、Modal trap 需手测 |
| 动效 | `prefers-reduced-motion` 未处理 | hover transform 较多 |
| Emoji 装饰 | 无替代文本 | 屏幕阅读器会读 emoji 名 |

---

## 5. 升级方案（分阶段）

### Phase 0 — 补洞（0.5–1 天，P0）

**目标**：消除「裸 HTML」模块，零架构变动。

| ID | 任务 | 文件 |
|----|------|------|
| UI-0a | 补全 §3 所列全部缺失 CSS | 新建 `views.css` 或写入 `pages.css` |
| UI-0b | 修复 `dashboard.js` 按钮类名 `btn btn-*` → `btn-*` | `dashboard.js` |
| UI-0c | 合并 Token：`style.css` 删除重复 `:root`，只保留 reset + theme overrides | `style.css`, `tokens.css` |
| UI-0d | `context-indicator` 最小可用样式 + 与 `chat.js` 联动验证 | `pages.css`, `chat.js` |

**验收**：首页空态、项目 DAG/时间线/成本图、上下文条在深色/浅色下均可见且不乱版。

---

### Phase 1 — 设计系统收敛（1–2 天，P1）

| ID | 任务 |
|----|------|
| UI-1a | 统一 `--content-padding-*`、全局 `.subtitle`、`.hint` 层级 |
| UI-1b | 状态色统一到 `--status-*`；改 `dag-renderer.js` / `timeline.js` 读 CSS 变量（或导出常量表与 Token 对齐） |
| UI-1c | 字号 scale 调整：`--text-base` 14px；表内禁止 `<10px` |
| UI-1d | 按钮语义拆分：`btn-clear` → `btn-ghost` / `btn-danger-ghost` |
| UI-1e | 硬编码色清扫：`#0d0f14`、`#ff4444`、step-tool `#111` → Token |

---

### Phase 2 — 布局与格式化体验（2–3 天，P1–P2）

| ID | 任务 |
|----|------|
| UI-2a | 任务列表：表头 + 移动端卡片化 |
| UI-2b | 执行树：responsive stack；减少 emoji 事件标签，改 icon + 文字 |
| UI-2c | 设置页 sticky 保存栏；管理页表格列宽策略（模型 truncate + tooltip） |
| UI-2d | 侧栏/顶栏 emoji → SVG avatar 或字母缩写块（与 `getAvatar` 统一） |
| UI-2e | 数字列 `tabular-nums`；状态改 chip 而非纯文字色 |
| UI-2f | `prefers-reduced-motion`；补充 aria-label |

---

### Phase 3 — 打磨（可选，P2）

- 空态插图统一（SVG spot illustration，去 emoji）
- DAG 节点 hover、缩放、选中联动任务列表
- 时间线日期分组（日分隔符，复用聊天 `date-sep`）
- 交付物目录树键盘导航
- 考虑引入 **单一** 等宽字体栈 Web font（仅管理/代码区）

---

## 6. 建议 PR 切分

与功能修复解耦，便于 review：

```
PR-UI-0  缺失 CSS + dashboard 按钮类名 + Token 去重
PR-UI-1  配色/字号/按钮语义收敛
PR-UI-2  任务列表 & 执行树 responsive + 设置页 action bar
```

**勿与** `PR-1 DAG 字段 bug` / `PR-3 多 Agent 并发` 混在同一 diff，减少回归面。

---

## 7. 验收清单（UI 专项）

### 视觉一致性

- [ ] 深色/浅色切换后，代码块、滚动条、表格 zebra、玻璃边框均正常
- [ ] 同一状态（running/completed/failed）在 chip、DAG、时间线、任务行 **色相一致**
- [ ] 全站无 `<10px` 正文（meta 时间戳除外且仍 ≥11px）
- [ ] 无 `btn btn-primary` 等无效类名

### 布局

- [ ] 375px / 820px / 1440px 三档无横向滚动（除刻意保留的宽表降级前）
- [ ] 聊天输入区与发送按钮底对齐；Modal 按钮右对齐一致
- [ ] 首页空态、项目 welcome、聊天 welcome 视觉权重一致

### 格式化

- [ ] Token ≥1000 有千分位；人民币与 Token 对齐
- [ ] Markdown 表格/代码在交付物与聊天气泡内样式一致
- [ ] 任务 status 显示中文标签（非 capitalize 英文）

### 可访问性

- [ ] Focus ring 在所有可交互元素可见
- [ ] 图标按钮均有 accessible name
- [ ] tertiary 文本对比度 ≥4.5:1（抽样 WebAIM）

---

## 8. 与功能升级方案的边界

| 话题 | 本文档（UI） | 三问题诊断（功能） |
|------|--------------|-------------------|
| DAG 空白 | 补 `dag-*` CSS；节点排版 | 修 `task_id` 字段 bug |
| 时间线空白 | 补 `tl-*` CSS | 同上 + 数据映射 |
| Token 显示 0 | 成本 bar 样式、数字格式 | claude parser / agent_port |
| 切换 Agent 断流 | 侧栏 running 指示器（可选） | `streams` 多路复用 |

UI 修复 **不能替代** 功能修复；两者叠加后项目 Tab 才能达到「可用且好看」。

---

## 9. 优先级总表

| 优先级 | 项 | 工时 | 用户感知 |
|--------|-----|------|----------|
| **P0** | 缺失 CSS 补全 + 首页按钮类名 | 0.5–1d | 极高 |
| **P0** | Token 双份合并 | 0.25d | 低（减维护债） |
| **P1** | 状态色/字号/按钮语义统一 | 1–2d | 高 |
| **P1** | 任务列表表头 + 移动卡片化 | 1d | 高 |
| **P1** | `btn-clear` 误用危险态 | 0.25d | 中 |
| **P2** | Emoji → 图标系统 | 1d | 中 |
| **P2** | a11y / reduced-motion | 0.5d | 中 |

---

## 10. 附录：关键文件索引

| 路径 | UI 相关职责 |
|------|-------------|
| `frontend/index.html` | 结构、Tab、Modal、内联 style 残留 |
| `frontend/tokens.css` | 设计 Token 权威源（建议） |
| `frontend/layout.css` | 导航/侧栏/响应式 |
| `frontend/components.css` | 按钮/表单/Toast |
| `frontend/pages.css` | 页面级样式（主战场） |
| `frontend/style.css` | Reset + 重复 Token（待瘦身） |
| `frontend/dashboard.js` | 首页统计/空态（**按钮 class bug**） |
| `frontend/dag-renderer.js` | DAG SVG（色板硬编码） |
| `frontend/timeline.js` | 时间线（**无 CSS**） |
| `frontend/project.js` | 项目/detail/成本 bar（**无 CSS**） |
| `frontend/manage.js` | 管理表格（内联字号） |

---

---

## 11. 实施记录

| 日期 | 阶段 | 状态 |
|------|------|------|
| 2026-06-08 | Phase 0（缺失 CSS、Token 去重、btn-ghost、任务表头） | ✅ 已合入 |
| 2026-06-08 | Phase 2（头像 initials、执行树响应式、任务移动卡片、context 指示器、emoji 清理） | ✅ 已合入 |
| 2026-06-08 | Phase 3（DAG 选中联动、时间线日期分组、交付物键盘导航、语义 emoji 清扫） | ✅ 已合入 |
| 2026-06-08 | Phase 4（DAG 缩放平移、交付物 Enter 打开、浅色主题对比度修补） | ✅ 已合入 |

*文档版本 v1.3 · 基于 `upgrade/continued` 分支前端静态审计 · 实施时请以实际 diff 为准更新验收项。*
