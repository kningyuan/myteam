# myteam WPS 加载项（PoC）

通过 WPS JSAPI 从 `deck_brief.json` 生成演示文稿，供 Agent 经 HTTP RPC 调用。

## 前置

- Node.js ≥ 18
- WPS Office（个人版或专业版）
- 全局工具：`npm install -g wpsjs`

## 开发调试

```bash
cd business/skills/wps-deck/addin
npm install
wpsjs debug
```

`wpsjs debug` 会启动本地 HTTP 服务并打开 WPS 加载项。默认 RPC 端口见控制台输出；与 Skill 脚本对齐：

```bash
export WPS_RPC_URL=http://127.0.0.1:19074   # 按 wpsjs 实际端口修改
bash ../scripts/check_wps_ready.sh
```

## 暴露的 RPC 接口（HTTP POST JSON）

| 路径 |  body | 说明 |
|------|-------|------|
| `/health` | — | `{ "ok": true }` |
| `/build_deck` | `{ "briefPath": "...", "outputPath": "..." }` | 调 JS `buildFromBrief` |

PoC 阶段若 RPC 未实现，`build_deck.sh` 自动 fallback `python-pptx`。

## 安装到 WPS（生产）

1. `wpsjs build` 打包加载项
2. WPS → 开发工具 → 加载项管理 → 安装
3. 重启 WPS

## JS 接口函数（ribbon / RPC 共用）

见 `src/js/build_from_brief.js`：

- `buildFromBrief(briefJson)` — 新建演示、套模板、逐页插入
- `saveAs(path)` — 保存 pptx
- `exportSlideImage(path, index)` — 导出缩略图（可选）

WPS 演示 JSAPI 文档：[WPS 开放平台 - 演示](https://open.wps.cn/documents/app-integration-dev/wps365/client/wpsoffice/jsapi/addin-api/event/wpp-event)
