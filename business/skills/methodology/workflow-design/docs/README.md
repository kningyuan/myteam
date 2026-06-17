# workflow-design — 讨论文档

本目录存放 **skill 设计期的多 agent 碰撞记录**，与 `SKILL.md`（执行指引）分离。

## 用途

- 记录问题陈述、候选方案、**共识**与**未决冲突**
- 你与多个 agent 并行讨论时，各方在此 **追加观点**，避免只在聊天里重复
- 达成共识后，再 **提炼进 `SKILL.md` / `patterns/` / 内核 issue**，不直接把长篇讨论塞进 SKILL

## 协作规则

1. **只追加或改「讨论区」**，不要删对方已写结论；若推翻旧共识，在「共识变更」里说明原因与日期  
2. 每条观点标注 **作者**（如 `Claude`、`Auto`）与 **日期**  
3. 用固定结构：`问题` → `方案` → `共识` → `冲突/TBD` → `待落地`  
4. 一方把 TBD 算清或做了实验，移到「已决」并链到 PR/提交  
5. `SKILL.md` 只保留 **可执行的短规则**；细节论证留在本目录

## 文件索引

| 文件 | 主题 | 状态 |
|------|------|------|
| [context-propagation.md](./context-propagation.md) | 同 agent 多 step 的上下文与 token | 讨论中 |

## 与 SKILL.md 的关系

```
讨论 docs/*.md  →  达成共识  →  精简写入 SKILL.md / patterns / checklist
                     ↓
              需改内核 → 单独 issue，不在 SKILL 里假装已实现
```
