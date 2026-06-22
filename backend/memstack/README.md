# memstack — 记忆与知识库（Layer B / QEL）

**开箱即用**：默认 `sqlite` L1 + `sqlite` KB，无需 vendor / API key。  
可选升级：`mem0`（`pip install -r requirements-memstack.txt` + `MEM0_API_KEY`）、`gbrain` vendor。

**验证**：[docs/MEMSTACK_MODULE_TEST_REPORT.md](../../docs/MEMSTACK_MODULE_TEST_REPORT.md)  
**本地 smoke**：`cd backend && PYTHONPATH=. python memstack/smoke.py`

## 架构：Framework + Adapter + Product

```text
Framework（facade / protocol / orchestration / injection）
        ↓
Adapter（sqlite / mem0 / gbrain …）
        ↓
Product（store.memory 表 / Mem0 SaaS / gbrain vendor）
```

## 默认可用能力（enabled=true 时）

| 能力 | 默认后端 | 行为 |
|------|----------|------|
| L1 工作记忆 | **sqlite** | 多轮 after_turn → before_turn 召回 |
| 团队 KB | **sqlite** | write / search / promote ledger |
| 偏好 | **static** | 读 `config/USER.md` |
| 经验注入 | orchestration | 同类 task_type ledger → execute prompt |
| gbrain 配置 | 降级 sqlite | 无 vendor 仍可读写的 `kb://gbrain/` ref |

## 配置

`config/skill_config.json` → `memstack` 段：

```json
{
  "memstack": {
    "enabled": true,
    "kb_backend": "sqlite",
    "l1_backend": "sqlite",
    "preferences_backend": "static",
    "inject_top_k": 3
  }
}
```

`agent_memory.backend` 仍兼容；未设 `l1_backend` 时 fallback 到 `agent_memory.backend`。

## 目录

```text
memstack/
├── facade.py
├── smoke.py           ← 本地可用性验证
├── kb/                sqlite（默认）+ gbrain（可降级）
├── l1/                sqlite（默认）+ native + mem0
├── preferences/       static + mem0
├── orchestration/     experience, anysearch
├── injection/
└── vendors/
```

## 可选 Mem0

```bash
pip install -r requirements-memstack.txt
export MEM0_API_KEY=...
# skill_config: "l1_backend": "mem0"
```

无 key 时 mem0 adapter **自动降级 sqlite L1**，不 crash。
