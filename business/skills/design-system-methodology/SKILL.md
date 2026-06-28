---
name: 设计系统方法论
description: 设计系统方法论：设计token分层、组件化原则、一致性约束、可复用性与多主题支持。
---
# 设计系统方法论

> **最佳实践来源**：建立设计系统和组件库，前端工程化2025最佳实践

## 何时启用

- `task_type` 为 `coding`、`system-design`、`architecture-review`
- 用户要求"设计系统""组件库""Design Token""UI规范"

## 核心架构

### 1. 设计系统三层模型

| 层 | 内容 | 变更频率 |
|----|------|----------|
| 原则层 | 设计理念、品牌调性、可访问性标准 | 极低 |
| Token 层 | 颜色、间距、字号、圆角、阴影、动画 | 低 |
| 组件层 | 按钮、表单、卡片、导航、模态框 | 中 |

### 2. Design Token 分层

```
Global Token（全局令牌）
  ├── Alias Token（语义令牌）
  │   ├── Component Token（组件令牌）
  │   └── 主题覆盖
  └── 暗色/亮色/品牌变体
```

**Token 分类**：

| 类型 | 示例 | 说明 |
|------|------|------|
| 颜色 | `color-primary-500` | 主色调，含明暗阶 |
| 间距 | `space-4` | 4px 基准网格 |
| 字号 | `font-size-md` | 响应式字号 |
| 圆角 | `radius-md` | 统一圆角语言 |
| 阴影 | `shadow-card` | 层级感 |
| 动画 | `duration-fast` | 交互反馈 |

### 3. 组件化原则

**组件五准则**：
1. **自包含**：不依赖外部状态，通过 props 接收数据
2. **可组合**：小组件组合成大组件，不反向依赖
3. **可配置**：通过 props/插槽实现配置化，减少变体数量
4. **可文档化**：每个组件有 Storybook 式示例
5. **一致性**：同类组件 API 风格统一

**组件分类**：

| 类型 | 示例 | 数量目标 |
|------|------|----------|
| 原子组件 | Button、Input、Icon | 15-20 |
| 分子组件 | FormField、SearchBar | 10-15 |
| 有机体 | Header、Card、Table | 8-12 |
| 模板 | PageLayout、DashboardLayout | 4-6 |

### 4. 一致性约束

| 约束 | 规则 |
|------|------|
| 颜色 | 只用 Token，禁止硬编码 hex |
| 间距 | 4px 网格，禁止任意值 |
| 字号 | 限定 6-8 级，禁止任意值 |
| 圆角 | 限定 3-4 级 |
| 动画 | 限定 3-4 种 duration |
| 命名 | 统一命名规范（BEM/kebab-case） |

### 5. 工程化基建

- **类型系统**：TypeScript，组件 Props 类型导出
- **构建优化**：代码分割、Tree-shaking、按需加载
- **质量门禁**：ESLint + Prettier + Stylelint，CI 集成
- **文档**：Storybook 组件目录 + Markdown 用法说明
- **测试**：组件单元测试 + 视觉回归测试

## 质量红线

- 禁止硬编码颜色/间距/字号 — 须用 Token
- 禁止组件反向依赖 — 子组件不引用父组件
- 禁止无文档的组件 — 须有 Storybook 示例
- 禁止忽略可访问性 — 须满足 WCAG 2.1 AA

## Gate 检查清单

- [ ] Token 分层清晰（Global → Alias → Component）
- [ ] 组件分类完整（原子/分子/有机体/模板）
- [ ] 一致性约束有明确规则表
- [ ] 含工程化基建方案（TS/ESLint/Storybook）
- [ ] 含可访问性标准（WCAG 2.1 AA）
- [ ] 含多主题支持方案
