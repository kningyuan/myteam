# MyTeam · Design System

> 基于 huashu-design 顾问流程，在现有 Discord 三栏布局上做精致化升级。只改视觉，不改功能。

## 方向

- **气质**：专业协作工作台 — 信息密度高、层级清晰、克制动效
- **反 slop**：无紫粉渐变、无左 border accent、无 emoji 装饰、无 Inter/Roboto
- **保留**：Discord 式 rail / list / main 结构、品牌 indigo `#5865f2`

## 字体

| 用途 | 字体 |
|------|------|
| 标题 / 数字 | Bricolage Grotesque |
| 正文 / UI | DM Sans |
| 等宽 | ui-monospace |

## 色彩（深色默认）

- **Sidebar** `#1a1b1f` — 最深层
- **List / Card** `#232428` — 中间层
- **Main** `#2b2d31` — 内容区
- **Brand** `#5865f2` — 主操作 / 激活态
- **Border** `rgba(255,255,255,0.08)` —  subtle 分隔

## 圆角 & 阴影

- sm `6px` · md `8px` · lg `12px` · xl `16px`
- 卡片用 `--shadow-sm`，悬浮用 `--shadow-md`，禁止大面积 glow

## 交互

- 过渡 `0.15s ease`（背景、颜色、边框）
- `:focus-visible` 使用 brand ring，不用 outline:none 裸奔
- List 激活项保持品牌色填充（Discord 惯例）
