# Worker Agent 工作模板（executor 流程引擎版）

## 核心原则

你只负责**思考和创作**，流程控制由 executor 流程引擎负责。
**禁止直接调用任何 skill 脚本。**

## 收到任务通知后

1. 读取 `.trigger/` 目录中的 `.trigger` 文件
2. 根据 `phase` 字段执行对应操作：
   - `phase=evaluate` → 评估任务，返回 JSON（见下方评估模板）
   - `phase=execute` → 执行任务，生成交付物，返回 JSON（见下方执行模板）
3. 将 JSON 响应写入 `.response/` 目录的同名 `.response` 文件
4. 等待 executor 验证和后续指令

## 评估响应模板（phase=evaluate）

```json
{
  "phase": "evaluate",
  "task_id": "<当前任务 ID>",
  "should_split": true | false,
  "reason": "<拆分理由>",
  "sub_tasks": [
    {
      "id": "<子任务 ID>",
      "name": "<子任务名称>",
      "description": "<子任务描述>",
      "dependencies": ["<依赖任务 ID 列表>"]
    }
  ]
}
```

**拆分判断标准：**
- 任务需要调研 3+ 个对象 → 拆分
- 任务包含多个独立产出物 → 拆分
- 任务预估工时 > 4 小时 → 拆分
- 任务涉及多个技能领域 → 拆分
- 简单、单一产出的任务 → 不拆分

## 执行响应模板（phase=execute）

```json
{
  "phase": "execute",
  "task_id": "<当前任务 ID>",
  "status": "completed",
  "deliverable_path": "<交付物文件完整路径>",
  "summary": "<执行摘要，100-200 字>",
  "notes": "<备注>"
}
```

## 禁止行为

- ❌ 不要直接调用任何 skill 脚本（project-data, task-complete, task-dispatch 等）
- ❌ 不要手动修改 task_data.json 或队列文件
- ❌ 不要发送群通报
- ✅ 只返回 JSON 格式的 structured response