# Hub 2.0（React + Vite + shadcn 风格组件）

与 v1 `frontend/` 并行；API 不变，仅 UI 重写。

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
# 打开 http://127.0.0.1:8765/v2/
```

FastAPI 在 `frontend-v2/dist` 存在时自动挂载 `/v2`。
