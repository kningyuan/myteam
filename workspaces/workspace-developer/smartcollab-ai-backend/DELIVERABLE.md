# 智协AI后端服务

后端服务实现了任务调度引擎、状态管理和通知系统三大核心模块。

## 模块说明

### 子任务 1: 任务调度引擎 ✅
- `src/scheduler/TaskScheduler.ts` - 核心调度器
- 功能：任务创建、排队、执行、优先级管理、超时控制、依赖管理

### 子任务 2: 状态管理 ✅
- `src/store/StateManager.ts` - 状态管理器
- 功能：任务状态持久化、状态变更监听、状态查询

### 子任务 3: 通知系统 ✅
- `src/notification/NotificationService.ts` - 通知服务
- 功能：Telegram 通知、状态变更通知、错误告警、任务超时提醒

## 技术栈
- Express.js - Web 框架
- TypeScript - 类型安全
- Winston - 日志系统
- UUID - 唯一ID生成
