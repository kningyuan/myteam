import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { TaskScheduler, WorkflowEngine, AgentRegistry, DeadlineWarningService } from './scheduler';
import { StateManager } from './store';
import { NotificationService } from './notification';
import { TaskStatus, Priority, TaskType, CreateTaskOptions, UpdateTaskOptions, NotificationType, CreateWorkflowOptions, CreateAgentOptions, AgentRole, AgentStatus } from './types';
import logger from './utils/logger';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// 初始化服务
const scheduler = new TaskScheduler({
  maxConcurrentTasks: 5,
  defaultTimeoutMs: 300000,
});

const workflowEngine = new WorkflowEngine();
const agentRegistry = new AgentRegistry();
const stateManager = new StateManager('./data/tasks.json');
const notificationService = new NotificationService({
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN,
  telegramChatId: process.env.TELEGRAM_CHAT_ID,
  enableEmail: false,
});
const deadlineWarningService = new DeadlineWarningService();

// 错误处理中间件
app.use((err: Error, req: Request, res: Response, _next: NextFunction) => {
  logger.error(`Unhandled error: ${err}`);
  res.status(500).json({
    success: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: err.message,
    },
  });
});

// ============ 任务 API ============

// 创建任务
app.post('/api/tasks', async (req: Request, res: Response) => {
  try {
    const options: CreateTaskOptions = req.body;
    
    if (!options.name || !options.description || !options.type) {
      return res.status(400).json({
        success: false,
        error: {
          code: 'INVALID_INPUT',
          message: 'name, description, and type are required',
        },
      });
    }

    const task = scheduler.createTask(options);
    
    await notificationService.notifyTaskStart(task.id, task.name);
    
    res.status(201).json({
      success: true,
      data: task,
    });
  } catch (error) {
    logger.error(`Error creating task: ${error}`);
    res.status(500).json({
      success: false,
      error: {
        code: 'CREATE_ERROR',
        message: 'Failed to create task',
      },
    });
  }
});

// 获取任务
app.get('/api/tasks/:taskId', (req: Request, res: Response) => {
  const task = scheduler.getTask(req.params.taskId as string as string);
  
  if (!task) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Task not found',
      },
    });
  }
  
  res.json({ success: true, data: task });
});

// 查询任务列表
app.get('/api/tasks', (req: Request, res: Response) => {
  const options = {
    status: req.query.status as TaskStatus | undefined,
    type: req.query.type as TaskType | undefined,
    priority: req.query.priority as Priority | undefined,
    assignee: req.query.assignee as string | undefined,
    limit: parseInt(req.query.limit as string) || 100,
    offset: parseInt(req.query.offset as string) || 0,
  };
  
  const tasks = scheduler.queryTasks(options);
  
  res.json({ success: true, data: tasks });
});

// 更新任务
app.patch('/api/tasks/:taskId', (req: Request, res: Response) => {
  const updates: UpdateTaskOptions = req.body;
  const task = scheduler.updateTask(req.params.taskId as string as string, updates);
  
  if (!task) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Task not found',
      },
    });
  }
  
  res.json({ success: true, data: task });
});

// 删除任务
app.delete('/api/tasks/:taskId', (req: Request, res: Response) => {
  const deleted = scheduler.deleteTask(req.params.taskId as string as string);
  
  if (!deleted) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Task not found',
      },
    });
  }
  
  res.json({ success: true });
});

// 启动任务
app.post('/api/tasks/:taskId/start', async (req: Request, res: Response) => {
  const task = scheduler.startTask(req.params.taskId as string as string);
  
  if (!task) {
    return res.status(400).json({
      success: false,
      error: {
        code: 'INVALID_STATE',
        message: 'Task cannot be started',
      },
    });
  }
  
  res.json({ success: true, data: task });
});

// 完成任务
app.post('/api/tasks/:taskId/complete', async (req: Request, res: Response) => {
  const { success } = req.body as { success?: boolean };
  const task = scheduler.completeTask(req.params.taskId as string as string, success !== false);
  
  if (!task) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Task not found',
      },
    });
  }
  
  await notificationService.notifyTaskComplete(
    task.id,
    task.name,
    task.status === 'completed'
  );
  
  res.json({ success: true, data: task });
});

// 更新 AI 步骤
app.patch('/api/tasks/:taskId/steps/:stepId', (req: Request, res: Response) => {
  const { status } = req.body as { status: 'pending' | 'running' | 'completed' | 'failed' };
  const task = scheduler.updateAIStep(req.params.taskId as string as string, req.params.stepId as string as string, status);
  
  if (!task) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Task or step not found',
      },
    });
  }
  
  res.json({ success: true, data: task });
});

// ============ 调度器 API ============

// 获取调度器统计
app.get('/api/scheduler/stats', (req: Request, res: Response) => {
  res.json({ success: true, data: scheduler.getStats() });
});

// 获取下一个可执行任务
app.get('/api/scheduler/next', (req: Request, res: Response) => {
  const task = scheduler.getNextTask();
  
  if (!task) {
    return res.json({ success: true, data: null });
  }
  
  res.json({ success: true, data: task });
});

// ============ 通知 API ============

// 获取通知列表
app.get('/api/notifications', (req: Request, res: Response) => {
  const options = {
    limit: parseInt(req.query.limit as string) || 50,
    unreadOnly: req.query.unreadOnly === 'true',
  };
  
  const notifications = notificationService.getNotifications(options);
  
  res.json({ success: true, data: notifications });
});

// 标记通知已读
app.patch('/api/notifications/:notificationId/read', (req: Request, res: Response) => {
  const marked = notificationService.markAsRead(req.params.notificationId as string as string);
  
  if (!marked) {
    return res.status(404).json({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Notification not found',
      },
    });
  }
  
  res.json({ success: true });
});

// 发送自定义通知
app.post('/api/notifications', async (req: Request, res: Response) => {
  const { type, title, message, taskId, data } = req.body as {
    type: NotificationType;
    title: string;
    message: string;
    taskId?: string;
    data?: Record<string, unknown>;
  };
  
  if (!type || !title || !message) {
    return res.status(400).json({
      success: false,
      error: {
        code: 'INVALID_INPUT',
        message: 'type, title, and message are required',
      },
    });
  }
  
  const notification = await notificationService.sendNotification(
    type,
    title,
    message,
    taskId,
    data
  );
  
  res.status(201).json({ success: true, data: notification });
});

// ============ 工作流 API ============

// 创建工作流
app.post('/api/workflows', (req: Request, res: Response) => {
  const wf = workflowEngine.createWorkflow(req.body);
  res.status(201).json({ success: true, data: wf });
});

// 获取工作流
app.get('/api/workflows/:id', (req: Request, res: Response) => {
  const wf = workflowEngine.getWorkflow(req.params.id as string as string);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

// 查询工作流列表
app.get('/api/workflows', (req: Request, res: Response) => {
  const workflows = workflowEngine.listWorkflows(req.query.projectId as string);
  res.json({ success: true, data: workflows });
});

// 更新工作流
app.patch('/api/workflows/:id', (req: Request, res: Response) => {
  const wf = workflowEngine.updateWorkflow(req.params.id as string as string, req.body);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

// 删除工作流
app.delete('/api/workflows/:id', (req: Request, res: Response) => {
  const deleted = workflowEngine.deleteWorkflow(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true });
});

// 发布工作流
app.post('/api/workflows/:id/publish', (req: Request, res: Response) => {
  const wf = workflowEngine.publishWorkflow(req.params.id as string as string);
  if (!wf) return res.status(400).json({ success: false, error: { code: 'PUBLISH_FAILED', message: 'Cannot publish workflow' } });
  res.json({ success: true, data: wf });
});

// 添加节点
app.post('/api/workflows/:id/nodes', (req: Request, res: Response) => {
  const wf = workflowEngine.addNode(req.params.id as string as string, req.body);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

// 更新节点状态
app.patch('/api/workflows/:id/nodes/:nodeId/status', (req: Request, res: Response) => {
  const wf = workflowEngine.updateNodeStatus(req.params.id as string as string, req.params.nodeId as string as string, req.body.status);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow or node not found' } });
  res.json({ success: true, data: wf });
});

// 拓扑排序
app.get('/api/workflows/:id/topological-sort', (req: Request, res: Response) => {
  const order = workflowEngine.topologicalSort(req.params.id as string as string);
  if (!order) return res.status(400).json({ success: false, error: { code: 'SORT_FAILED', message: 'Workflow has cycles or not found' } });
  res.json({ success: true, data: order });
});

// 启动工作流执行
app.post('/api/workflows/:id/execute', (req: Request, res: Response) => {
  const exec = workflowEngine.startExecution(req.params.id as string as string, req.body.projectName || '');
  if (!exec) return res.status(400).json({ success: false, error: { code: 'EXEC_FAILED', message: 'Workflow not published or not found' } });
  res.json({ success: true, data: exec });
});

// 获取执行记录
app.get('/api/executions/:id', (req: Request, res: Response) => {
  const exec = workflowEngine.getExecution(req.params.id as string as string);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution not found' } });
  res.json({ success: true, data: exec });
});

// 查询执行记录列表
app.get('/api/executions', (req: Request, res: Response) => {
  const executions = workflowEngine.listExecutions(req.query.status as any);
  res.json({ success: true, data: executions });
});

// 更新执行进度
app.patch('/api/executions/:id/progress', (req: Request, res: Response) => {
  const exec = workflowEngine.updateExecutionProgress(req.params.id as string as string, req.body.nodeId, req.body.status);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution not found' } });
  res.json({ success: true, data: exec });
});

// ============ Agent API ============

// 注册 Agent
app.post('/api/agents', (req: Request, res: Response) => {
  const agent = agentRegistry.registerAgent(req.body);
  res.status(201).json({ success: true, data: agent });
});

// 获取 Agent
app.get('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.getAgent(req.params.id as string as string);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

// 查询 Agent 列表
app.get('/api/agents', (req: Request, res: Response) => {
  const filter: { status?: AgentStatus; role?: AgentRole } = {};
  if (req.query.status) filter.status = req.query.status as AgentStatus;
  if (req.query.role) filter.role = req.query.role as AgentRole;
  const agents = agentRegistry.listAgents(filter);
  res.json({ success: true, data: agents });
});

// 更新 Agent
app.patch('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.updateAgent(req.params.id as string as string, req.body);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

// 删除 Agent
app.delete('/api/agents/:id', (req: Request, res: Response) => {
  const deleted = agentRegistry.deleteAgent(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true });
});

// ============ Dashboard API ============

// 获取看板统计
app.get('/api/dashboard/stats', (req: Request, res: Response) => {
  const execStats = workflowEngine.getStats();
  const agentStats = agentRegistry.getStats();
  res.json({
    success: true,
    data: {
      running: execStats.running,
      completed: execStats.completed,
      failed: execStats.failed,
      avgDuration: '1m 23s',
      runningDelta: 2,
      completedDelta: 5,
      failedDelta: -1,
      avgDurationDelta: -12,
      agents: agentStats,
    },
  });
});

// 获取最近执行记录
app.get('/api/dashboard/recent', (req: Request, res: Response) => {
  const all = workflowEngine.listExecutions();
  const recent = all.sort((a, b) => b.startedAt.getTime() - a.startedAt.getTime()).slice(0, 10);
  res.json({ success: true, data: recent });
});

// ============ 系统 API ============

// 健康检查
app.get('/api/health', (req: Request, res: Response) => {
  res.json({
    success: true,
    data: {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      version: '1.0.0',
    },
  });
});

// ============ 工作流 API ============

app.post('/api/workflows', (req: Request, res: Response) => {
  const wf = workflowEngine.createWorkflow(req.body);
  res.status(201).json({ success: true, data: wf });
});

app.get('/api/workflows/:id', (req: Request, res: Response) => {
  const wf = workflowEngine.getWorkflow(req.params.id as string as string);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

app.get('/api/workflows', (req: Request, res: Response) => {
  const workflows = workflowEngine.listWorkflows(req.query.projectId as string);
  res.json({ success: true, data: workflows });
});

app.patch('/api/workflows/:id', (req: Request, res: Response) => {
  const wf = workflowEngine.updateWorkflow(req.params.id as string as string, req.body);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

app.delete('/api/workflows/:id', (req: Request, res: Response) => {
  const deleted = workflowEngine.deleteWorkflow(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true });
});

app.post('/api/workflows/:id/publish', (req: Request, res: Response) => {
  const wf = workflowEngine.publishWorkflow(req.params.id as string as string);
  if (!wf) return res.status(400).json({ success: false, error: { code: 'PUBLISH_FAILED', message: 'Cannot publish workflow' } });
  res.json({ success: true, data: wf });
});

app.post('/api/workflows/:id/nodes', (req: Request, res: Response) => {
  const wf = workflowEngine.addNode(req.params.id as string as string, req.body);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: wf });
});

app.patch('/api/workflows/:id/nodes/:nodeId/status', (req: Request, res: Response) => {
  const wf = workflowEngine.updateNodeStatus(req.params.id as string as string, req.params.nodeId as string as string, req.body.status);
  if (!wf) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow or node not found' } });
  res.json({ success: true, data: wf });
});

app.get('/api/workflows/:id/topological-sort', (req: Request, res: Response) => {
  const order = workflowEngine.topologicalSort(req.params.id as string as string);
  if (!order) return res.status(400).json({ success: false, error: { code: 'SORT_FAILED', message: 'Workflow has cycles or not found' } });
  res.json({ success: true, data: order });
});

app.post('/api/workflows/:id/execute', (req: Request, res: Response) => {
  const exec = workflowEngine.startExecution(req.params.id as string as string, req.body.projectName || '');
  if (!exec) return res.status(400).json({ success: false, error: { code: 'EXEC_FAILED', message: 'Workflow not published or not found' } });
  res.json({ success: true, data: exec });
});

app.get('/api/executions/:id', (req: Request, res: Response) => {
  const exec = workflowEngine.getExecution(req.params.id as string as string);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution not found' } });
  res.json({ success: true, data: exec });
});

app.get('/api/executions', (req: Request, res: Response) => {
  const executions = workflowEngine.listExecutions(req.query.status as any);
  res.json({ success: true, data: executions });
});

app.patch('/api/executions/:id/progress', (req: Request, res: Response) => {
  const exec = workflowEngine.updateExecutionProgress(req.params.id as string as string, req.body.nodeId, req.body.status);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution not found' } });
  res.json({ success: true, data: exec });
});

// ============ Agent API ============

app.post('/api/agents', (req: Request, res: Response) => {
  const agent = agentRegistry.registerAgent(req.body);
  res.status(201).json({ success: true, data: agent });
});

app.get('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.getAgent(req.params.id as string as string);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

app.get('/api/agents', (req: Request, res: Response) => {
  const filter: { status?: AgentStatus; role?: AgentRole } = {};
  if (req.query.status) filter.status = req.query.status as AgentStatus;
  if (req.query.role) filter.role = req.query.role as AgentRole;
  const agents = agentRegistry.listAgents(filter);
  res.json({ success: true, data: agents });
});

app.patch('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.updateAgent(req.params.id as string as string, req.body);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

app.delete('/api/agents/:id', (req: Request, res: Response) => {
  const deleted = agentRegistry.deleteAgent(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true });
});

// ============ Dashboard API ============

app.get('/api/dashboard/stats', (req: Request, res: Response) => {
  const execStats = workflowEngine.getStats();
  const agentStats = agentRegistry.getStats();
  res.json({
    success: true,
    data: {
      running: execStats.running,
      completed: execStats.completed,
      failed: execStats.failed,
      avgDuration: '1m 23s',
      runningDelta: 2,
      completedDelta: 5,
      failedDelta: -1,
      avgDurationDelta: -12,
      agents: agentStats,
    },
  });
});

app.get('/api/dashboard/recent', (req: Request, res: Response) => {
  const all = workflowEngine.listExecutions();
  const recent = all.sort((a, b) => b.startedAt.getTime() - a.startedAt.getTime()).slice(0, 10);
  res.json({ success: true, data: recent });
});

// ============ 工作流 API ============

// 创建工作流
app.post('/api/workflows', (req: Request, res: Response) => {
  const options: CreateWorkflowOptions = req.body;
  if (!options.name || !options.projectId) {
    return res.status(400).json({ success: false, error: { code: 'INVALID_INPUT', message: 'name and projectId are required' } });
  }
  const workflow = workflowEngine.createWorkflow(options);
  res.status(201).json({ success: true, data: workflow });
});

// 获取工作流
app.get('/api/workflows/:id', (req: Request, res: Response) => {
  const workflow = workflowEngine.getWorkflow(req.params.id as string as string);
  if (!workflow) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: workflow });
});

// 查询工作流列表
app.get('/api/workflows', (req: Request, res: Response) => {
  const workflows = workflowEngine.listWorkflows(req.query.projectId as string);
  res.json({ success: true, data: workflows });
});

// 更新工作流
app.patch('/api/workflows/:id', (req: Request, res: Response) => {
  const workflow = workflowEngine.updateWorkflow(req.params.id as string as string, req.body);
  if (!workflow) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true, data: workflow });
});

// 删除工作流
app.delete('/api/workflows/:id', (req: Request, res: Response) => {
  const deleted = workflowEngine.deleteWorkflow(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.json({ success: true });
});

// 发布工作流
app.post('/api/workflows/:id/publish', (req: Request, res: Response) => {
  const workflow = workflowEngine.publishWorkflow(req.params.id as string as string);
  if (!workflow) return res.status(400).json({ success: false, error: { code: 'PUBLISH_FAILED', message: 'Workflow cannot be published' } });
  res.json({ success: true, data: workflow });
});

// 添加节点
app.post('/api/workflows/:id/nodes', (req: Request, res: Response) => {
  const workflow = workflowEngine.addNode(req.params.id as string as string, req.body);
  if (!workflow) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow not found' } });
  res.status(201).json({ success: true, data: workflow });
});

// 更新节点状态
app.patch('/api/workflows/:id/nodes/:nodeId', (req: Request, res: Response) => {
  const { status } = req.body as { status: string };
  const workflow = workflowEngine.updateNodeStatus(req.params.id as string as string, req.params.nodeId as string as string, status as any);
  if (!workflow) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Workflow or node not found' } });
  res.json({ success: true, data: workflow });
});

// 拓扑排序
app.get('/api/workflows/:id/topological-sort', (req: Request, res: Response) => {
  const order = workflowEngine.topologicalSort(req.params.id as string as string);
  if (!order) return res.status(400).json({ success: false, error: { code: 'SORT_FAILED', message: 'Workflow has a cycle or not found' } });
  res.json({ success: true, data: order });
});

// 启动工作流执行
app.post('/api/workflows/:id/execute', (req: Request, res: Response) => {
  const { projectName } = req.body as { projectName: string };
  const exec = workflowEngine.startExecution(req.params.id as string as string, projectName || 'Default');
  if (!exec) return res.status(400).json({ success: false, error: { code: 'EXEC_FAILED', message: 'Workflow must be published first' } });
  res.status(201).json({ success: true, data: exec });
});

// 获取执行记录
app.get('/api/executions', (req: Request, res: Response) => {
  const status = req.query.status as any;
  const executions = workflowEngine.listExecutions(status);
  res.json({ success: true, data: executions });
});

app.get('/api/executions/:id', (req: Request, res: Response) => {
  const exec = workflowEngine.getExecution(req.params.id as string as string);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution not found' } });
  res.json({ success: true, data: exec });
});

// 更新执行进度
app.patch('/api/executions/:id/nodes/:nodeId', (req: Request, res: Response) => {
  const { status } = req.body as { status: string };
  const exec = workflowEngine.updateExecutionProgress(req.params.id as string as string, req.params.nodeId as string as string, status as any);
  if (!exec) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Execution or node not found' } });
  res.json({ success: true, data: exec });
});

// ============ Agent API ============

// 注册 Agent
app.post('/api/agents', (req: Request, res: Response) => {
  const options: CreateAgentOptions = req.body;
  if (!options.name || !options.apiEndpoint) {
    return res.status(400).json({ success: false, error: { code: 'INVALID_INPUT', message: 'name and apiEndpoint are required' } });
  }
  const agent = agentRegistry.registerAgent(options);
  res.status(201).json({ success: true, data: agent });
});

// 获取 Agent
app.get('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.getAgent(req.params.id as string as string);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

// 查询 Agent 列表
app.get('/api/agents', (req: Request, res: Response) => {
  const filter = {
    status: req.query.status as AgentStatus,
    role: req.query.role as AgentRole,
  };
  const agents = agentRegistry.listAgents(filter);
  res.json({ success: true, data: agents });
});

// 更新 Agent
app.patch('/api/agents/:id', (req: Request, res: Response) => {
  const agent = agentRegistry.updateAgent(req.params.id as string as string, req.body);
  if (!agent) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true, data: agent });
});

// 删除 Agent
app.delete('/api/agents/:id', (req: Request, res: Response) => {
  const deleted = agentRegistry.deleteAgent(req.params.id as string as string);
  if (!deleted) return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Agent not found' } });
  res.json({ success: true });
});

// ============ Dashboard API ============

// 获取看板统计
app.get('/api/dashboard/stats', (req: Request, res: Response) => {
  const execStats = workflowEngine.getStats();
  const agentStats = agentRegistry.getStats();
  res.json({
    success: true,
    data: {
      running: execStats.running,
      completed: execStats.completed,
      failed: execStats.failed,
      avgDuration: '1m 23s',
      runningDelta: 2,
      completedDelta: 5,
      failedDelta: -1,
      avgDurationDelta: -12,
      agents: agentStats,
    },
  });
});

// 获取执行中的工作流
app.get('/api/dashboard/running', (req: Request, res: Response) => {
  const executions = workflowEngine.listExecutions('running');
  res.json({ success: true, data: executions });
});

// 获取最近完成
app.get('/api/dashboard/recent', (req: Request, res: Response) => {
  const executions = workflowEngine.listExecutions('completed');
  res.json({ success: true, data: executions.slice(0, 10) });
});

// ============ 协作流程 API ============

// 获取看板（按状态分组）
app.get('/api/kanban', (req: Request, res: Response) => {
  const board = scheduler.getKanbanBoard();
  res.json({ success: true, data: board });
});

// 获取截止预警
app.get('/api/warnings/deadline', (req: Request, res: Response) => {
  const warnings = deadlineWarningService.checkTasks(scheduler.getAllTasks());
  res.json({ success: true, data: warnings, count: warnings.length });
});

// 认领任务
app.post('/api/tasks/:taskId/claim', (req: Request, res: Response) => {
  const { claimant } = req.body;
  if (!claimant) {
    return res.status(400).json({ success: false, error: { code: 'INVALID_INPUT', message: 'claimant is required' } });
  }
  const task = scheduler.claimTask(req.params.taskId as string, claimant);
  if (!task) {
    return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Task not found or not claimable' } });
  }
  res.json({ success: true, data: task });
});

// 添加评论
app.post('/api/tasks/:taskId/comments', (req: Request, res: Response) => {
  const { author, content, mentions } = req.body;
  if (!author || !content) {
    return res.status(400).json({ success: false, error: { code: 'INVALID_INPUT', message: 'author and content are required' } });
  }
  const comment = scheduler.addComment(req.params.taskId as string, { author, content, mentions });
  if (!comment) {
    return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Task not found' } });
  }
  res.status(201).json({ success: true, data: comment });
});

// 获取评论列表
app.get('/api/tasks/:taskId/comments', (req: Request, res: Response) => {
  const comments = scheduler.getComments(req.params.taskId as string);
  res.json({ success: true, data: comments });
});

// 获取通知列表
app.get('/api/notifications', (req: Request, res: Response) => {
  const notifications = notificationService.getNotifications();
  const unread = notifications.filter(n => !n.read).length;
  res.json({ success: true, data: notifications, unread });
});

// 标记通知已读
app.post('/api/notifications/:notifId/read', (req: Request, res: Response) => {
  const result = notificationService.markAsRead(req.params.notifId as string);
  if (!result) {
    return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Notification not found' } });
  }
  res.json({ success: true });
});

// 获取可认领任务列表
app.get('/api/tasks/claimable', (req: Request, res: Response) => {
  const claimable = scheduler.getAllTasks().filter(t => t.status === 'pending' && t.claimable && !t.assignee);
  res.json({ success: true, data: claimable });
});

// 启动服务器
app.listen(PORT, () => {
  logger.info(`SmartCollab AI Backend running on port ${PORT}`);
  scheduler.start();
});

export default app;
