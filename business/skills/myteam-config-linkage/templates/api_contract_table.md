# 统一 API 契约（复制到 system-design 交付物「接口契约」）

## /api/config

| JSON path | 类型 | UI id | owner | 备注 |
|-----------|------|-------|-------|------|
| system.port | int | set-port | backend+frontend | 改端口需重启 Hub |
| system.default_backend | string | set-default-backend | frontend | |
| ... | | | | |

## /api/skill-config

| JSON path | 类型 | UI id | owner | 内核消费 |
|-----------|------|-------|-------|----------|
| process_defaults.max_gate_retries | int | set-max-gate-retries | 双方 | ProcessConfig |
| executor.task_timeout | int | set-task-timeout | backend | WatchdogConfig |
| ... | | | | |

## P0/P1 修复清单

| ID | 项 | owner | 文件 | 验证方式 |
|----|-----|-------|------|----------|
| P0-1 | | frontend / backend / 双方 | | bash run_linkage_tests.sh |
