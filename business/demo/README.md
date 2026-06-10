# myteam Demo 项目

本目录包含 myteam 编排内核的 Demo 配置，用于快速体验核心功能。

## 使用方法

```bash
# 方式一：CLI
cd <myteam_root>
export MYTEAM_ROOT="$PWD" PYTHONPATH="$PWD/backend"
venv/bin/python3 backend/common/run_kernel.py --init
venv/bin/python3 backend/common/run_kernel.py --demo

# 方式二：Hub（浏览器）
# 1. ./run.sh start
# 2. 打开 http://localhost:8765
# 3. 首页 →「初始化 Agent」→「运行 Demo」
```

## 目录结构

```
business/demo/
├── README.md              ← 本文件
├── goal.txt               ← Demo 目标（首行为 goal，# 开头为注释）
└── agents_config.json     ← Demo 使用的 Agent 配置（main + research）
```

## 定制 Demo

1. 编辑 `goal.txt` 修改目标
2. 编辑 `agents_config.json` 增减 Agent
3. 运行 `--demo` 或 Hub 首页「运行 Demo」
