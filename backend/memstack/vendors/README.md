# memstack vendors — 第三方记忆 / 知识库工程

本目录存放 **Product 层**源码：外挂记忆系统、知识库等第三方工程（git submodule、vendor copy 或安装脚本拉取）。

**架构分责**：

| 层 | 位置 | 职责 |
|----|------|------|
| **Framework** | `memstack/facade`、`protocol`、`orchestration`、`injection` | 通用交互框架 — myteam 定义 |
| **Adapter** | `memstack/kb/gbrain.py`、`l1/mem0.py` 等 | 薄翻译 — 每产品一份 |
| **Product** | **`vendors/<name>/`（本目录）** | 功能细节 — 各开源产品自管 |

**不要** 把 vendor 逻辑散落到 `common/process.py`、Framework 或 CLI adapter 里。

## 登记

在 `manifest.yaml` 中登记每个 vendor：

- id、repo、版本、安装命令  
- 对应的 memstack adapter 模块（如 `memstack.kb.gbrain`）  
- 所需环境变量  

## 推荐 vendor

| id | 用途 | adapter |
|----|------|---------|
| `gbrain` | L3 团队 KB + 图谱 | `memstack/kb/gbrain.py` |
| `mem0` | L1 工作记忆 + 偏好 | `memstack/l1/mem0.py`, `memstack/preferences/mem0.py` |

## 安装示例

```bash
# gbrain（示例，按官方文档调整）
git submodule add https://github.com/example/gbrain.git backend/memstack/vendors/gbrain

# mem0 OSS / SDK（示例）
git submodule add https://github.com/mem0ai/mem0.git backend/memstack/vendors/mem0
```

安装后更新 `manifest.yaml` 中的 `installed_version` 与 `adapter_status`。

## 原则

1. **Framework + Adapter 分责**：Framework 定 Protocol 与生命周期；Product 在 `vendors/` 实现能力；中间仅经 adapter 连接。  
2. **Agent-centric**：adapter 按 `agent_id` / `project_id` 读写，不按 CLI 类型。  
3. **可关**：vendor 不可用时不影响 Layer A 骨架运行。  
4. **不修改 vendor 源码**（除非 upstream PR）；定制放 `memstack/*/adapter` 层。  
5. **优先成熟开源**：新能力先查 OSS / SaaS，经 manifest 登记 + adapter 对接；**不自建** 向量/图谱/搜索引擎。  
6. **可扩展**：新增 Product = Protocol adapter + registry + 用例 Pass；不换 Framework / facade 签名。  
7. **自研例外**：仅当对接后 E-* / TC 仍明显不达标且无替代 vendor 时，在 memstack 内做 **最小** 补实现，并补回归用例。
