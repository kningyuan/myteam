# myteam 快速开始

> **目标**：从零到跑通第一个编排项目，5 分钟内完成。

## 前置条件

- Python 3.10+
- 已安装 [opencode CLI](https://opencode.ai) 或 [Claude Code CLI](https://claude.ai/code)
  - 确保已登录（`opencode --version` 或 `claude --version` 正常输出）
- 已克隆 myteam 仓库并进入项目根目录

## 第一步：初始化

确保所有 agent 的工作空间已创建：

```bash
cd myteam
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
venv/bin/python3 backend/common/run_kernel.py --init
```

输出示例：

```
📦 初始化 12 个 agent workspace…
  ✓ main（项目协调专家）— 已创建
  ✓ researcher（调研专家）— 已创建
  …（其余 agent）
✅ 所有 12 个 workspace 已就绪，无需创建。
```

## 第二步：运行 Demo

用一条命令启动 demo 项目：

```bash
venv/bin/python3 backend/common/run_kernel.py --demo
```

Demo 会自动：
1. 生成一个项目 ID（`demo-YYYYMMDD-HHMMSS`）
2. 使用预设的 goal：「调研 AI 编码工具 Cursor、Claude Code、GitHub Copilot 的市场定位和核心功能」
3. 由 main agent 组队、拆任务，串行驱动执行
4. 运行结束后输出进度摘要

## 第三步：查看结果

执行完成后，终端会显示任务完成状态：

```
🏁 Demo 完成 — 状态：completed
📊 任务进度：2/2 完成
  ✔ research(researcher) → completed
  ✔ strategy(product) → completed
```

交付物文件位于 `business/tasks/project/demo-*/` 目录下。

也可以启动 Hub 通过浏览器查看：

```bash
./run.sh start
# 访问 http://localhost:8765 → 点击「项目」标签
```

## 运行自己的项目

```bash
venv/bin/python3 backend/common/run_kernel.py my-project \
  --goal "你的目标描述" \
  --mode one_shot \
  --budget 100000
```

参数说明：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `project_id` | 项目唯一标识（必填，非 demo 模式） | — |
| `--goal` | 项目目标描述 | `""` |
| `--mode` | `one_shot`（单次）或 `recurring`（周期） | `one_shot` |
| `--budget` | token 预算上限 | 无限制 |
| `--backend` | CLI 后端：`opencode` 或 `claude` | `opencode` |
| `--review` | 开启同行评审 | 关闭 |
| `--split` | 开启任务递归拆分 | 关闭 |

## 断点续跑

如果项目因故中断（如网络问题、token 耗尽），可以续跑：

```bash
venv/bin/python3 backend/common/run_kernel.py my-project \
  --goal "..."     # 续跑时 goal 必须与首次一致
```

系统会自动回收已完成的任务，从中断点继续。

## 遇到问题？

- 首次运行前先执行 `--init`
- 确认 CLI 后端已安装并登录：`opencode --version`
- 查看错误输出中的中文提示，按指引操作
- 完整故障排查见 [故障排查指南](troubleshooting.md)