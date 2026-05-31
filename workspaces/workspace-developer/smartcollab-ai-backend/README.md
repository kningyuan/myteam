# SmartCollab AI Backend

智协AI后端服务 - 任务调度引擎、状态管理、通知系统

## 功能模块

### 1. 任务调度引擎 (`src/scheduler/`)
- 任务创建、排队、执行
- 优先级管理（urgent > high > medium > low）
- 超时控制
- 依赖管理
- 并发控制

### 2. 状态管理 (`src/store/`)
- 任务状态持久化
- 状态变更监听
- 状态查询

### 3. 通知系统 (`src/notification/`)
- Telegram 通知
- 状态变更通知
- 错误告警
- 任务超时提醒

## API 端点

### 任务 API
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/tasks` | 创建任务 |
| GET | `/api/tasks/:taskId` | 获取任务 |
| GET | `/api/tasks` | 查询任务列表 |
| PATCH | `/api/tasks/:taskId` | 更新任务 |
| DELETE | `/api/tasks/:taskId` | 删除任务 |
| POST | `/api/tasks/:taskId/start` | 启动任务 |
| POST | `/api/tasks/:taskId/complete` | 完成任务 |
| PATCH | `/api/tasks/:taskId/steps/:stepId` | 更新 AI 步骤 |

### 调度器 API
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/scheduler/stats` | 获取统计信息 |
| GET | `/api/scheduler/next` | 获取下一个可执行任务 |

### 通知 API
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/notifications` | 获取通知列表 |
| PATCH | `/api/notifications/:id/read` | 标记已读 |
| POST | `/api/notifications` | 发送通知 |

### 系统 API
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |

## 环境变量

```bash
PORT=3001
LOG_LEVEL=info
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 开发

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
npm start
```
