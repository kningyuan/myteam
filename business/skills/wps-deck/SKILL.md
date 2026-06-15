---
name: "WPS 演示文稿"
description: WPS 演示文稿增强 — 加载项 + RPC 套模板/图表；不可用时 fallback python-pptx。
workflows:
  - 产品独立交付
agents:
  - product
---
# wps-deck — WPS 演示文稿 Skill

**适用**：`deck-build` 任务；需 **真实 .pptx** 且优先 WPS 模板/绘图能力时。

Agent **先读**：`business/skills/product-operations/SKILL.md`  
本包为 **WPS 增强路径**；统一入口仍是 `product-operations/scripts/build_deck.sh`。

## 环境（首次必做）

1. 安装 [WPS Office](https://www.wps.cn/)（Mac / Windows）
2. 加载项：`business/skills/wps-deck/addin/` — 见 `addin/README.md`
3. 启动 RPC：`cd addin && wpsjs debug`（或部署后的 HTTP 服务）
4. 探活：

```bash
bash business/skills/wps-deck/scripts/check_wps_ready.sh
# 0=就绪  1=WPS未安装  2=RPC未启动（走 python 兜底）
```

## 执行步骤

1. 填写 `deck_brief.yaml`（模板见 product-operations/templates/）
2. 生成：

```bash
bash business/skills/wps-deck/scripts/wps_build_deck.sh \
  /path/to/deck_brief.yaml \
  /path/to/deliverable/deck.pptx
```

3. 失败时 **不要伪造文件** — 改跑：

```bash
bash business/skills/product-operations/scripts/build_deck.sh \
  /path/to/deck_brief.yaml \
  /path/to/deliverable/deck.pptx
```

4. Gate 前：

```bash
python3 business/skills/product-operations/scripts/verify_deck.py \
  /path/to/deck.pptx --deliverable /path/to/t-deck_deliverable.md
```

## 直接操作 WPS（不是 MCP）

```text
Agent 跑 wps_beautify.sh / build_deck.sh
        │
        ▼
node wps_call.js beautifyDeck '{...}'     ← Skill 脚本
        │
        ▼
WpsInvoke.InvokeAsHttp  →  127.0.0.1:58890  ← WPS 本地服务（非 19074）
        │
        ▼
WPS 演示 加载项 JS：beautifyDeck()  ← 模板/主题/字体（真实 WPS 工具）
        │
        ▼
保存 deck.pptx
```

**不需要 MCP。** 需要的是：

1. **WPS 已安装**
2. **加载项已注册**（一次性）：

```bash
bash business/skills/wps-deck/scripts/install_addin_mac.sh
# 完全退出 WPS 后重新打开
```

3. **npm 依赖**：

```bash
cd business/skills/wps-deck && npm install
```

4. **探活**：

```bash
bash business/skills/wps-deck/scripts/check_wps_ready.sh   # exit 0 = 可直接调 WPS
node business/skills/wps-deck/scripts/wps_call.js health
```

## Mac 个人版限制（实测 2025-06）

| 项 | Windows / WPS 专业版 | Mac 个人版 |
|----|---------------------|------------|
| 58890 本地服务 | ✅ 通常可用 | ⚠️ **常无法启动**（[社区反馈](https://bbs.wps.cn/topic/58735)） |
| 加载项在线调试 | ✅ | ✅ `wpsjs debug`（3889 起，占用则 3890…） |
| 脚本直连 beautifyDeck | ✅ | ❌ 需 58890；不可用时 **自动 python 兜底** |
| 手动 WPS 美化 | ✅ | ✅ `open -a wpsoffice deck.pptx` + 加载项 Ribbon |

Mac 上若 `node wps_call.js health` 报 `ECONNREFUSED 58890`：

1. 终端 A：`bash business/skills/wps-deck/scripts/start_wps_debug.sh`（保持运行）
2. 记下实际端口（如 3890），同步 publish.xml：  
   `WPS_DEBUG_PORT=3890 bash business/skills/wps-deck/scripts/install_addin_mac.sh`
3. 完全退出并重启 WPS；在 **演示** 中打开 pptx，看 Ribbon 是否出现 **myteam** 选项卡
4. 仍无 58890 → 接受 python fallback；或换 **Windows / WPS 专业版（内置 JSAPI）** 跑 WPS 直连

尝试唤起中继（不一定成功）：

```bash
open "ksoWPSCloudSvr://start=RelayHttpServer&serverId=myteam-test"
curl -X POST http://127.0.0.1:58890/version -d '{"serverId":"myteam-test"}'
```

## RPC 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `WPS_ADDIN_NAME` | `myteam-wps-deck` | publish.xml 中的加载项名 |
| `WPS_DEBUG_PORT` | `3889` | wpsjs debug 端口（install 脚本写 publish.xml） |
| `WPS_HTTP_BASE` | `http://127.0.0.1:58890` | WpsInvoke 本地服务 |

## 红线

- 禁止 RPC 未就绪时假装「已用 WPS 生成」。
- 禁止跳过 verify_deck。
- Mac 上 **单实例 WPS**：并行 deck 任务须串行或仅用 python 兜底。
