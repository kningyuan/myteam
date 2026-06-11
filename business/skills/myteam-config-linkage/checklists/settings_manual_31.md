# 设置页手动验证清单（qa 交付物附录）

对每一项：**改值 → 保存 → 刷新页面 → 确认回显 → 记录 PASS/FAIL**

## /api/config（9 项）

- [ ] set-port
- [ ] set-default-backend / set-default-model
- [ ] set-cli-path
- [ ] set-price
- [ ] set-debug
- [ ] set-audit-log / set-audit-log-max-bytes
- [ ] set-default-review
- [ ] set-model-aliases（OpenCode）

## /api/skill-config — process_defaults（11 项）

- [ ] set-default-budget
- [ ] set-max-gate-retries
- [ ] set-soft-idle / set-hard-idle / set-max-cycles
- [ ] set-parallel-default / set-max-parallel / set-max-concurrent-projects
- [ ] set-split-default
- [ ] set-budget-degrade-threshold / backend / model

## /api/skill-config — 其它（10 项）

- [ ] set-hub-url
- [ ] set-use-project-group / set-enable-telegram
- [ ] set-auto-group / include-main / name-prefix
- [ ] set-poll-interval / ack / task / agent-msg / team-config / task-plan timeouts
- [ ] set-max-retries

## 新建项目弹窗

- [ ] np-budget 默认 = process_defaults.default_project_budget
- [ ] np-review 默认 = system.default_review
- [ ] np-split 默认 = process_defaults.split_enabled
