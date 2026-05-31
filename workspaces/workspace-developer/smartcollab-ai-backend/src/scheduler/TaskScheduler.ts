import { v4 as uuidv4 } from 'uuid';
import { Task, TaskStatus, Priority, TaskType, CreateTaskOptions, UpdateTaskOptions, TaskQueryOptions, AIStep, TaskComment, KanbanColumn } from '../types';
import logger from '../utils/logger';

/**
 * 任务调度引擎 - 核心调度器
 * 支持任务创建、排队、执行、优先级管理、超时控制
 */
export class TaskScheduler {
  private tasks: Map<string, Task> = new Map();
  private taskQueue: string[] = []; // 待执行任务ID队列
  private activeTasks: Map<string, Task> = new Map(); // 正在执行的任务
  private maxConcurrentTasks: number;
  private defaultTimeoutMs: number;
  private isRunning: boolean = false;

  constructor(config?: { maxConcurrentTasks?: number; defaultTimeoutMs?: number }) {
    this.maxConcurrentTasks = config?.maxConcurrentTasks ?? 5;
    this.defaultTimeoutMs = config?.defaultTimeoutMs ?? 300000; // 5分钟默认超时
  }

  /**
   * 创建新任务
   */
  createTask(options: CreateTaskOptions): Task {
    const task: Task = {
      id: `task_${uuidv4().slice(0, 8)}`,
      name: options.name,
      description: options.description,
      type: options.type,
      status: 'pending',
      priority: options.priority ?? 'medium',
      progress: 0,
      aiExecutor: options.aiExecutor ?? false,
      createdAt: new Date(),
      updatedAt: new Date(),
      tags: options.tags,
      timeoutMs: options.timeoutMs ?? this.defaultTimeoutMs,
      dependencies: options.dependencies,
      deadline: options.deadline,
      claimable: options.claimable ?? false,
      comments: [],
    };

    // 检查依赖是否满足
    if (options.dependencies && options.dependencies.length > 0) {
      const unsatisfiedDeps = options.dependencies.filter(depId => {
        const depTask = this.tasks.get(depId);
        return !depTask || depTask.status !== 'completed';
      });
      
      if (unsatisfiedDeps.length > 0) {
        logger.warn(`Task ${task.id} has unsatisfied dependencies: ${unsatisfiedDeps.join(', ')}`);
      }
    }

    this.tasks.set(task.id, task);
    this.taskQueue.push(task.id);
    logger.info(`Task created: ${task.id} - ${task.name}`);
    
    return task;
  }

  /**
   * 获取任务
   */
  getTask(taskId: string): Task | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * 查询任务列表
   */
  queryTasks(options: TaskQueryOptions): Task[] {
    let results = Array.from(this.tasks.values());

    if (options.status) {
      results = results.filter(t => t.status === options.status);
    }
    if (options.type) {
      results = results.filter(t => t.type === options.type);
    }
    if (options.priority) {
      results = results.filter(t => t.priority === options.priority);
    }
    if (options.assignee) {
      results = results.filter(t => t.assignee === options.assignee);
    }

    // 按优先级排序
    const priorityOrder: Priority[] = ['urgent', 'high', 'medium', 'low'];
    results.sort((a, b) => {
      const priorityDiff = priorityOrder.indexOf(a.priority) - priorityOrder.indexOf(b.priority);
      if (priorityDiff !== 0) return priorityDiff;
      return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
    });

    // 分页
    const offset = options.offset ?? 0;
    const limit = options.limit ?? 100;
    return results.slice(offset, offset + limit);
  }

  /**
   * 更新任务
   */
  updateTask(taskId: string, updates: UpdateTaskOptions): Task | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      logger.error(`Task not found: ${taskId}`);
      return null;
    }

    const oldStatus = task.status;
    
    if (updates.status && updates.status !== oldStatus) {
      task.status = updates.status;
      
      // 状态流转处理
      if (updates.status === 'in_progress' && oldStatus === 'pending') {
        task.startedAt = new Date();
      } else if (updates.status === 'completed' && oldStatus === 'in_progress') {
        task.completedAt = new Date();
        task.progress = 100;
      }
    }

    if (updates.name) task.name = updates.name;
    if (updates.description) task.description = updates.description;
    if (updates.priority) task.priority = updates.priority;
    if (updates.progress !== undefined) task.progress = updates.progress;
    if (updates.assignee) task.assignee = updates.assignee;
    if (updates.tags) task.tags = updates.tags;

    task.updatedAt = new Date();
    this.tasks.set(taskId, task);
    
    logger.info(`Task updated: ${taskId} - status: ${oldStatus} -> ${task.status}`);
    
    return task;
  }

  /**
   * 删除任务
   */
  deleteTask(taskId: string): boolean {
    const task = this.tasks.get(taskId);
    if (!task) return false;

    // 如果任务正在执行，先停止
    if (this.activeTasks.has(taskId)) {
      this.activeTasks.delete(taskId);
    }

    // 从队列中移除
    const queueIndex = this.taskQueue.indexOf(taskId);
    if (queueIndex > -1) {
      this.taskQueue.splice(queueIndex, 1);
    }

    this.tasks.delete(taskId);
    logger.info(`Task deleted: ${taskId}`);
    
    return true;
  }

  /**
   * 获取下一个可执行任务
   */
  getNextTask(): Task | null {
    while (this.taskQueue.length > 0) {
      const taskId = this.taskQueue[0];
      const task = this.tasks.get(taskId);
      
      if (!task) {
        this.taskQueue.shift();
        continue;
      }

      // 检查任务是否可执行
      if (task.status !== 'pending') {
        this.taskQueue.shift();
        continue;
      }

      // 检查依赖
      if (task.dependencies && task.dependencies.length > 0) {
        const allDepsCompleted = task.dependencies.every(depId => {
          const depTask = this.tasks.get(depId);
          return depTask && depTask.status === 'completed';
        });
        
        if (!allDepsCompleted) {
          // 依赖未满足，跳过
          break;
        }
      }

      // 检查并发限制
      if (this.activeTasks.size >= this.maxConcurrentTasks) {
        return null;
      }

      return task;
    }

    return null;
  }

  /**
   * 启动任务执行
   */
  startTask(taskId: string): Task | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      logger.error(`Task not found: ${taskId}`);
      return null;
    }

    if (task.status !== 'pending') {
      logger.warn(`Task ${taskId} is not in pending status: ${task.status}`);
      return null;
    }

    // 从队列中移除
    const queueIndex = this.taskQueue.indexOf(taskId);
    if (queueIndex > -1) {
      this.taskQueue.splice(queueIndex, 1);
    }

    // 更新状态
    task.status = 'in_progress';
    task.startedAt = new Date();
    task.updatedAt = new Date();
    
    this.tasks.set(taskId, task);
    this.activeTasks.set(taskId, task);
    
    logger.info(`Task started: ${taskId} - ${task.name}`);
    
    return task;
  }

  /**
   * 完成任务
   */
  completeTask(taskId: string, success: boolean = true): Task | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      logger.error(`Task not found: ${taskId}`);
      return null;
    }

    if (!this.activeTasks.has(taskId)) {
      logger.warn(`Task ${taskId} is not active`);
    }

    this.activeTasks.delete(taskId);
    
    task.status = success ? 'completed' : 'failed';
    task.completedAt = new Date();
    task.updatedAt = new Date();
    task.progress = success ? 100 : task.progress;
    
    this.tasks.set(taskId, task);
    
    logger.info(`Task completed: ${taskId} - ${success ? 'success' : 'failed'}`);
    
    return task;
  }

  /**
   * 更新AI步骤状态
   */
  updateAIStep(taskId: string, stepId: string, status: AIStep['status']): Task | null {
    const task = this.tasks.get(taskId);
    if (!task || !task.aiSteps) {
      return null;
    }

    const step = task.aiSteps.find(s => s.id === stepId);
    if (!step) {
      return null;
    }

    step.status = status;

    if (status === 'running') {
      step.startedAt = new Date();
    } else if (status === 'completed' || status === 'failed') {
      step.completedAt = new Date();
    }

    // 更新任务进度
    const completedSteps = task.aiSteps.filter(s => s.status === 'completed').length;
    const totalSteps = task.aiSteps.length;
    task.progress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
    task.updatedAt = new Date();
    
    this.tasks.set(taskId, task);
    
    return task;
  }

  /**
   * 启动调度器
   */
  start(): void {
    if (this.isRunning) {
      logger.warn('Scheduler is already running');
      return;
    }

    this.isRunning = true;
    logger.info('Task scheduler started');
  }

  /**
   * 停止调度器
   */
  stop(): void {
    this.isRunning = false;
    logger.info('Task scheduler stopped');
  }

  /**
   * 获取系统统计信息
   */
  getStats(): {
    totalTasks: number;
    pendingTasks: number;
    activeTasks: number;
    completedTasks: number;
    failedTasks: number;
    waitingForInput: number;
    queueLength: number;
  } {
    const stats = {
      totalTasks: this.tasks.size,
      pendingTasks: 0,
      activeTasks: this.activeTasks.size,
      completedTasks: 0,
      failedTasks: 0,
      waitingForInput: 0,
      queueLength: this.taskQueue.length,
    };

    for (const task of this.tasks.values()) {
      switch (task.status) {
        case 'pending':
          stats.pendingTasks++;
          break;
        case 'completed':
          stats.completedTasks++;
          break;
        case 'failed':
          stats.failedTasks++;
          break;
        case 'waiting_for_input':
          stats.waitingForInput++;
          break;
      }
    }

    return stats;
  }

  /**
   * 检查超时任务
   */
  checkTimeouts(): string[] {
    const now = new Date();
    const timedOutTasks: string[] = [];

    for (const [taskId, task] of this.activeTasks) {
      if (!task.startedAt || !task.timeoutMs) continue;

      const elapsed = now.getTime() - task.startedAt.getTime();
      if (elapsed > task.timeoutMs) {
        logger.warn(`Task ${taskId} timed out after ${elapsed}ms`);
        timedOutTasks.push(taskId);
      }
    }

    return timedOutTasks;
  }

  getAllTasks(): Task[] {
    return Array.from(this.tasks.values());
  }

  getKanbanBoard(): KanbanColumn[] {
    const statusLabels: Record<TaskStatus, string> = {
      pending: '待处理',
      in_progress: '进行中',
      waiting_for_input: '等待输入',
      completed: '已完成',
      failed: '失败',
    };
    const statusOrder: TaskStatus[] = ['pending', 'in_progress', 'waiting_for_input', 'completed', 'failed'];

    return statusOrder.map(status => {
      const tasks = Array.from(this.tasks.values())
        .filter(t => t.status === status)
        .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
      return { status, label: statusLabels[status], tasks, count: tasks.length };
    });
  }

  claimTask(taskId: string, claimant: string): Task | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      logger.error(`Task not found: ${taskId}`);
      return null;
    }
    if (task.status !== 'pending') {
      logger.warn(`Task ${taskId} is not claimable: status=${task.status}`);
      return null;
    }
    if (task.assignee) {
      logger.warn(`Task ${taskId} already assigned to ${task.assignee}`);
      return null;
    }

    task.assignee = claimant;
    task.claimable = false;
    task.updatedAt = new Date();
    this.tasks.set(taskId, task);
    logger.info(`Task ${taskId} claimed by ${claimant}`);
    return task;
  }

  addComment(taskId: string, options: { author: string; content: string; mentions?: string[] }): TaskComment | null {
    const task = this.tasks.get(taskId);
    if (!task) return null;
    if (!task.comments) task.comments = [];

    const comment: TaskComment = {
      id: `comment_${uuidv4().slice(0, 8)}`,
      taskId,
      author: options.author,
      content: options.content,
      createdAt: new Date(),
      mentions: options.mentions,
    };
    task.comments.push(comment);
    task.updatedAt = new Date();
    this.tasks.set(taskId, task);
    return comment;
  }

  getComments(taskId: string): TaskComment[] {
    return this.tasks.get(taskId)?.comments ?? [];
  }
}

export default TaskScheduler;
