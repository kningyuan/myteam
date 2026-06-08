# 故障排查指南

> 遇到问题？按错误现象查找对应解决方案。

---

## 运行相关

### 找不到 agent workspace

**错误现象**：
```
找不到 agent「researcher」的工作空间。请确认 business/workspaces/workspace-researcher/ 存在。
```

**可能原因**：首次运行前未执行 workspace 初始化。

**解决步骤**：
1. 执行初始化：`python backend/common/run_kernel.py --init`
2. 确认输出中包含所有需要的 agent
3. 重新运行项目

---

### CLI 后端无法启动

**错误现象**：
```
CLI 后端执行失败（exit code 1）。请确认 CLI（opencode/claude）安装正确且已登录。
```

**可能原因**：
1. opencode/claude 未安装
2. 未登录或 token 过期
3. CLI 路径配置不正确

**解决步骤**：
1. 检查 CLI 是否安装：`opencode --version` 或 `claude --version`
2. 确认登录状态：重新执行 `opencode login` 或 `claude login`
3. 检查配置：查看 `config/system_config.json` 中的 `cli_path` 设置
4. 环境变量覆盖：`export OPENCODE_CLI_PATH=/path/to/opencode`

---

### 缺少配置文件

**错误现象**：
```
缺少配置文件 business/config/xxx.json。可执行 --init 生成默认配置。
```

**可能原因**：配置文件被删除或项目未正确初始化。

**解决步骤**：
1. 确保在项目根目录运行（`MYTEAM_ROOT` 正确设置）
2. 检查 `business/config/` 目录是否存在
3. 如果缺失，从 git 恢复：`git checkout -- business/config/`

---

### 项目不完整（无任务数据）

**错误现象**：
```
项目没有任务数据，可能是不完整的中断状态。
```

**可能原因**：项目在 team_config 或 task_plan 阶段中途中断。

**解决步骤**：
1. 确认项目 ID 正确
2. 查看项目状态：`python -c "from common.store import Store; s=Store(); print(s.get_project('项目ID'))"`
3. 如果数据不完整，可能需要重建项目

---

## 编排执行

### main agent 分配了非法 agent

**错误现象**：
```
编排规划失败：main 分配了名册外的 agent「xxx」。
```

**可能原因**：agents_registry.json 配置不全或 goal 描述引起 main 错误分配。

**解决步骤**：
1. 检查 `business/config/agents_registry.json` 中是否包含该 agent
2. 确认 agent 的 task_types 配置正确
3. 如果 agent 不存在，可以通过 `--init` 创建，或手动添加到 registry

---

### 任务门禁不通过

**错误现象**：任务状态变为 `failed`，原因包含 gate check 相关内容。

**可能原因**：交付物缺少必需章节、必需内容或字数不足。

**解决步骤**：
1. 查看失败原因中的具体缺失项
2. 检查 `business/templates/templates.yaml` 中对应 task_type 的 check_rules
3. 任务会自动重试（如有剩余次数），无需人工干预

---

### 项目卡住不动

**错误现象**：终端长时间无输出，项目状态为 `in_progress`。

**可能原因**：
1. agent 执行耗时较长
2. 看门狗未触发（在 soft_idle 阈值内）
3. CLI 后端进程挂起

**解决步骤**：
1. 耐心等待看门狗自动处理（soft_idle 120s → hard_idle 300s）
2. 终端会输出告警：`⚠ agent「xxx」已 120s 无响应`
3. 如果看门狗未自动恢复，手动取消：新终端执行：
   ```bash
   python -c "from common.store import Store; s=Store(); s.set_project_status('项目ID', 'cancelled')"
   ```

---

### Agent 输出乱码或格式异常

**错误现象**：交付物内容不符合预期格式。

**可能原因**：LLM 输出不稳定或 CLI 版本不兼容。

**解决步骤**：
1. 重试项目（断点续跑会自动跳过已完成任务）
2. 检查 CLI 版本是否最新
3. 如持续异常，尝试切换后端：`--backend claude`

---

## Hub 相关

### Hub 无法启动

**错误现象**：`./run.sh start` 报错。

**可能原因**：
1. 端口被占用（默认 8765）
2. Python 依赖缺失

**解决步骤**：
1. 检查端口：`lsof -i :8765`
2. 修改端口：编辑 `config/system_config.json` 中的 `port` 字段
3. 安装依赖：`pip install -r requirements.txt`
4. 查看日志：`./run.sh start` 会打印详细错误信息

---

### Hub 无法看到项目

**错误现象**：Hub 项目页面显示「暂无项目」或数据为空。

**可能原因**：
1. 项目由 Hub 直接启动的（会存在 `business/tasks/project/` 下）
2. Hub 和 `run_kernel` 读取同一个 SQLite 数据库

**解决步骤**：
1. 确认数据库文件 `business/tasks/state.db` 存在
2. 刷新 Hub 页面
3. 如果使用 docker，确认挂载了正确的 `business/` 目录

---

## 通用

### 所有操作都报「未知错误」

**错误现象**：没有任何明确指引的通用错误。

**解决步骤**：
1. 检查 `business/tasks/project/{project_id}/` 的日志文件
2. 确认 `MYTEAM_ROOT` 和 `PYTHONPATH` 设置正确
3. 收集信息后提交 issue（附上 business/tasks/project/ 目录）