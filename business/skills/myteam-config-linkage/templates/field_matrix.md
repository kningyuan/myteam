# 配置项全景清单（复制到交付物「关键发现」）

| UI 控件 id | 显示名称 | API 域 | JSON path | GET 端点 | PUT 端点 | loadSettings | saveSettings | 后端消费点 | 是否生效 |
|------------|----------|--------|-----------|----------|----------|--------------|--------------|------------|----------|
| set-port | 端口 | system | system.port | /api/config | /api/config | | | hub 启动 | |
| set-default-backend | 默认后端 | system | system.default_backend | /api/config | /api/config | | | agent_transport | |
| ... | | | | | | | | | |

**填写说明**

- 运行 `bash business/skills/myteam-config-linkage/scripts/scan_config_inventory.sh` 获取控件列表起点
- 「是否生效」须追到 `kernel_config` / `skill_settings` / `server.py` 读取点，不能只看 UI
