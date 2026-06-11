---
name: myteam-config-linkage
description: myteam 系统升级 workflow 共享包 — Web 设置页 ↔ /api/config ↔ /api/skill-config ↔ 内核 runtime 贯通。
workflows:
  - myteam系统升级
---

# myteam-config-linkage — 配置贯通共享 Skill

**适用 workflow**：`myteam系统升级` 及一切「设置 Tab ↔ 双 API ↔ 内核」类任务。

各 step 的 `task_type` Skill 会引用本包；执行前 **先读本文件**，再读对应 task_type 的 `SKILL.md`。

## 范围与红线

| 在范围内 | 禁止 |
|---------|------|
| `frontend/settings.js`、`index.html`、`app.js` | 改 `Process` / `AgentPort` 调度 |
| `backend/store/`、`backend/hub/api/server.py`（config API） | 改 `backend/common/process.py` 语义 |
| `backend/common/kernel_config.py`、`skill_settings.py` | 提交 `config/*.json`、`business/workspaces/` |
| `backend/common/tests/test_*linkage*`、`test_settings_config_contract.py` | 无测试宣称完成 |

## 双 API 数据流

```text
GET/PUT /api/config        → config/system_config.json  （system.*、backends.*）
GET/PUT /api/skill-config  → config/skill_config.json   （executor、process_defaults、notifications…）
skill_config PUT 后        → reload_skill_settings()      → 下一项目 kernel 读新值
```

## 必跑脚本（交付前）

在 **myteam 仓库根目录**执行：

```bash
# 全量回归（qa / 验收前）
bash business/skills/myteam-config-linkage/scripts/run_config_regression.sh

# 开发中快速验证（developer / frontend 改代码后）
bash business/skills/myteam-config-linkage/scripts/run_linkage_tests.sh

# 字段矩阵静态扫描（research / 评审前）
bash business/skills/myteam-config-linkage/scripts/scan_config_inventory.sh
python3 business/skills/myteam-config-linkage/scripts/verify_config_contract.py
```

退出码 `0` = 通过；非零须写入交付物 **失败项**，禁止报「全部通过」。

## 模板

- 字段矩阵：`templates/field_matrix.md`
- API 契约表：`templates/api_contract_table.md`
- 设置页 31 项手验：`checklists/settings_manual_31.md`

## 与 workflow 步骤的对应

| 步骤 | 主要脚本/模板 |
|------|--------------|
| t-inventory | `scan_config_inventory.sh` + field_matrix 模板 |
| t-fe-contract | `verify_config_contract.py` + field_matrix |
| t-plan | api_contract_table 模板 |
| t-fix-be / t-fix-fe | `run_linkage_tests.sh` |
| t-test | `run_config_regression.sh` + settings_manual_31 |
| t-accept | 对照 t-plan P0/P1 清单逐项打勾 |
