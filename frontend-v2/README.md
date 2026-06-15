# Hub 2.0（React + Vite + shadcn 风格组件）

默认生产 UI。经典版 `frontend/` 已归档（源码保留，默认不再对外提供）。

## 开发

```bash
# 终端 1：Hub API
cd .. && ./run.sh start

# 终端 2：Vite dev（proxy /api → 8765）
cd frontend-v2 && npm install && npm run dev
# 打开 http://localhost:5173/v2/
```

## 生产构建

```bash
npm run build
cd .. && ./run.sh restart
# 打开 http://127.0.0.1:8765/  （自动进入 /v2/）
```

Hub 在 `frontend-v2/dist` 存在时：`/` 302 → `/v2/`，并挂载 `/v2` SPA。

临时恢复经典版：`MYTEAM_V1_UI=1 ./run.sh start`，访问 http://127.0.0.1:8765/classic/
