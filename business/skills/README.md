# myteam Skill 目录

本目录是 myteam 多 agent 协作平台的 **Skill Pack** 层，存放各 agent 执行具体任务所需的方法论与可执行 skill。

## 目录结构

```
business/skills/
├── catalog.yaml          # Skill 注册表（id → router 路径 → task_types）
├── categories.yaml       # Skill 分类索引
├── README.md             # 本文件
├── <skill-id>/
│   └── SKILL.md          # YAML frontmatter (name/description) + Markdown 正文
└── _pending/             # 待审批补丁（install_skill_from_url 按需创建）
```

## Skill 三层来源

| 来源 | 目录 | 许可证 | 引入方式 |
|------|------|--------|---------|
| **自研方法论** | `*-methodology/` | myteam 项目 | 原创编写 |
| **superpowers 引入** | `test-driven-development/` 等 | MIT (obra/superpowers) | 复制 SKILL.md + 适配 myteam 红线 |
| **业务 skill** | `coding/` `review/` 等 | myteam 项目 | 原创编写 |

### superpowers 引入清单（MIT，来源 https://github.com/obra/superpowers）

| skill | 用途 | 适用角色 |
|-------|------|---------|
| `test-driven-development` | TDD RED-GREEN-REFACTOR 循环 | developer, tester |
| `systematic-debugging` | 四阶段根因调试 | developer, tester |
| `verification-before-completion` | 完成前验证，证据先于断言 | 全角色 |
| `brainstorming` | 头脑风暴，实现前先设计 | product, designer, arch |
| `writing-plans` | 精确实施计划编写 | product, designer, developer |
| `requesting-code-review` | 请求代码审查 | developer, tester, arch |
| `receiving-code-review` | 接收代码审查反馈 | developer, tester |

## 新增 Skill 流程

1. **创建目录**：`business/skills/<skill-id>/SKILL.md`（YAML frontmatter `name`/`description` + Markdown）
2. **注册 catalog**：在 `catalog.yaml` 添加条目（id/task_types/router/description）
3. **注册分类**：在 `categories.yaml` 对应分类 members 添加 skill-id
4. **挂载到角色**：在 `business/config/agents_registry.json` 对应角色的 `skills` 数组添加 skill-id
5. **测试验证**：用 `run_kernel.py` 跑测试项目，确认 skill 注入生效（日志 `semantic matched N skills`）

## 注意事项

- **officecli 套件已停用**：上游 `~/skill/OfficeCLI/skills/` 软链已断开移除，相关 task_type 回退到 `presentation-design-methodology`
- **catalog 别名型 skill**：`product-planning`/`research`/`requirements` 等 router 指向共享方法论（如 `product-methodology/SKILL.md`），这是设计如此（别名复用），但不应被直接作为 skill_id 挂载到角色——角色应挂载实际有目录的 skill
- **新 task_type 须先注册 templates.yaml**：AGENTS.md 规定，Process 只识别 templates.yaml 中的 task_type，不能只写 Skill
