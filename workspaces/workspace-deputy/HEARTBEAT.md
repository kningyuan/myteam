# HEARTBEAT.md - Deputy Agent（副协调员）

## 检查项
- [x] 检查所有项目任务队列状态
- [x] 检查正在执行的任务是否超时
- [x] 检查 Worker Agent 是否需要恢复
- [x] 检查失败任务并自动重试（已实现）
- [x] 检查任务死锁（已实现）
- [x] 检查连续超时任务（超过 3 次需告警）

## 心跳要求

**必须每 5 分钟响应一次心跳事件**，防止被 Watchdog（15 分钟无输出）终止。

### 响应格式

**正常情况**：
```
HEARTBEAT_OK
```

**异常情况**：
```
⚠️ 检测到超时任务：{task_id} (已运行 {minutes} 分钟)
正在恢复任务...
✅ 任务已恢复：{task_id} (重试 {count}/3)
```

**失败情况**：
```
❌ 任务 {task_id} 已重试 3 次，仍超时
已标记为失败，需要人工介入
```

## 心跳输出方式

### 方式 1: 日志文件（必须）
```bash
echo "[$(date '+%H:%M:%S')] Deputy HEARTBEAT: 检查完成，无超时任务" >> ~/.openclaw/workspace-deputy/logs/agent.log
```

### 方式 2: 状态文件（推荐）
```bash
cat > ~/.openclaw/workspace-deputy/state/heartbeat.json << EOF
{
  "agent_id": "deputy",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "monitoring",
  "projects_checked": {count},
  "tasks_recovered": {count},
  "errors": []
}
EOF
```

## 心跳检查点

在以下操作前后必须输出心跳：

1. ✅ **开始检查前** - "准备检查所有项目任务队列..."
2. ✅ **每个项目检查后** - "检查项目 {project_id}: idle/running"
3. ✅ **发现超时任务** - "检测到超时任务：{task_id}"
4. ✅ **恢复任务后** - "任务已恢复：{task_id} (重试 {count}/3)"
5. ✅ **检查完成** - "Heartbeat 检查完成，共检查 {count} 个项目"

## 长时间等待任务

如任务执行时间较长（>10 分钟），必须周期性输出心跳：

```python
import time
from datetime import datetime

start_time = datetime.now()
while monitoring:
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] HEARTBEAT: 监控中，已运行 {int(elapsed)} 秒...")
    time.sleep(120)  # 2 分钟
```

## Watchdog 恢复

如不幸被 Watchdog 终止（15 分钟无输出）：

1. 系统会自动重启 Deputy Agent
2. Deputy 读取最后的 heartbeat 状态
3. 恢复任务监控循环
4. 发送恢复通知到日志

```bash
# 恢复后第一条消息
echo "⚠️ Deputy 从 Watchdog 恢复" >> ~/.openclaw/workspace-deputy/logs/agent.log
echo "  最后状态：{last_state}" >> ~/.openclaw/workspace-deputy/logs/agent.log
echo "  恢复时间：$(date)" >> ~/.openclaw/workspace-deputy/logs/agent.log
```

## 心跳日志示例

```
[09:00:00] Deputy HEARTBEAT: 启动任务监控循环...
[09:00:01] Deputy HEARTBEAT: 检查项目 pro_xxx: idle
[09:00:02] Deputy HEARTBEAT: 检查项目 pro_yyy: running:task_003
[09:00:03] Deputy HEARTBEAT: 检测到超时任务：task_003 (已运行 15 分钟)
[09:00:04] Deputy HEARTBEAT: 恢复任务 task_003...
[09:00:05] Deputy HEARTBEAT: ✅ 任务已恢复：task_003 (重试 1/3)
[09:00:06] Deputy HEARTBEAT: 检查完成，共检查 5 个项目，恢复 1 个任务
```

## 监控脚本（可选）

创建外部监控脚本，检查 Deputy 心跳：

```bash
#!/bin/bash
# ~/.openclaw/scripts/monitor-deputy-heartbeat.sh

HEARTBEAT_FILE=~/.openclaw/workspace-deputy/state/heartbeat.json
THRESHOLD=1800  # 30 分钟

if [ -f "$HEARTBEAT_FILE" ]; then
    last_update=$(stat -f %m "$HEARTBEAT_FILE")
    now=$(date +%s)
    diff=$((now - last_update))
    
    if [ $diff -gt $THRESHOLD ]; then
        echo "⚠️ Deputy 心跳丢失超过 30 分钟" >> ~/.openclaw/logs/deputy-alert.log
        # 可选：重启 Deputy Agent
        # openclaw restart deputy
    fi
fi
```

---

**重要**: 心跳是 Deputy Agent 的生命线，必须严格遵守！
