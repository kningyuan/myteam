# 系统架构方法论 Skill — 验证说明

> **日期**：2026-06-14  
> **Skill 路径**：
> - Cursor：`.cursor/skills/system-architecture-methodology/SKILL.md`
> - myteam 编排：`business/skills/system-architecture-methodology/SKILL.md`

---

## 来源（可直接复用的公开 skill）

| 来源 | 用途 | 是否整包采用 |
|------|------|--------------|
| [awesome-cursor-skills / architecture-decision-records](https://github.com/spencerpauly/awesome-cursor-skills) | ADR 模板与流程 | ✅ 裁剪并入 |
| [wshobson/agents / architecture-patterns](https://github.com/wshobson/agents) | Hexagonal / Ports 选型 | ✅ 概念并入 |
| [arc42-documentation](https://github.com/gitaroktato/opencode-agents) | 12 章完整架构文档 | ❌ 过重，未整包采用 |
| [C4 full workflow](https://github.com/sickn33/antigravity-awesome-skills) | 四层 bottom-up | ❌ 过重；仅 Context+Container |

**结论**：没有「一键安装就完美适配 myteam」的单一 skill；采用 **合成精简版**，并对齐 `templates.yaml` 的 `trade-off` Gate。

---

## 已配置内容

1. 方法论 skill（Cursor + myteam 双份入口）
2. `system-design` / `architecture-review` 强制先读方法论
3. ADR 目录 `docs/decisions/` + 示范 **ADR-001**（StoreBackend 决策）

---

## 如何验证效果

### A. 在 Cursor 里（你现在）

对新开对话说：

> 用 system-architecture-methodology，评审 myteam Hub API 是否应继续拆 routes，输出 trade-off 和 ADR 草稿。

**期望**：agent 自动加载 skill，输出含约束表、≥2 方案、trade-off 矩阵、Mermaid C4，而非直接给「应该拆」。

### B. 在 myteam 编排里

让 `arch` 跑一个 `system-design` 任务，检查交付物是否含：

- `问题与约束`
- 含 **trade-off** 关键词（Gate `must_include`）
- 引用 ADR 编号或内嵌 ADR 小节

### C. 对照示范 ADR

见 [`docs/decisions/001-store-backend-port.md`](./001-store-backend-port.md) — 用方法论对 **已做决策** 补全理论依据，证明「不是凭想象」。

---

## 预期提升 vs 不提升

| 会提升 | 不会自动提升 |
|--------|--------------|
| 决策有记录、可质疑 | 第一次就选最优架构 |
| 模式选择与约束对齐 | 无真实负载时的性能预测 |
| Gate 可验的结构完整性 | 产品优先级判断 |

---

## 下一步（可选）

- 为 `docs/decisions/002-hub-api-modularization.md` 补 ADR（Wave 3 routes）
- 在 `templates.yaml` 增加 `must_include: ADR` 硬规则
- 从 Cursor Marketplace 安装 [Superpower Builder](https://github.com/redhuntlabs/superpower-builder) 做 skill A/B 压测
