import { Task, TaskStatus, UpdateTaskOptions } from '../types';
import logger from '../utils/logger';

/**
 * 状态管理器 - 任务状态持久化与查询
 */
export class StateManager {
  private stateFile: string;
  private tasks: Map<string, Task> = new Map();
  private listeners: Set<StateChangeListener> = new Set();

  constructor(stateFile: string = './data/tasks.json') {
    this.stateFile = stateFile;
  }

  /**
   * 加载状态
   */
  async load(): Promise<void> {
    try {
      // 这里简化处理，实际应读取文件
      logger.info(`StateManager loaded from ${this.stateFile}`);
    } catch (error) {
      logger.error(`Failed to load state: ${error}`);
    }
  }

  /**
   * 保存状态
   */
  async save(): Promise<void> {
    try {
      // 这里简化处理，实际应写入文件
      logger.debug('StateManager saved');
    } catch (error) {
      logger.error(`Failed to save state: ${error}`);
    }
  }

  /**
   * 更新任务状态
   */
  updateTaskStatus(taskId: string, status: TaskStatus, updates?: Partial<Task>): Task | null {
    const task = this.tasks.get(taskId);
    if (!task) {
      logger.error(`Task not found: ${taskId}`);
      return null;
    }

    const oldStatus = task.status;
    task.status = status;
    
    if (updates) {
      Object.assign(task, updates);
    }
    
    task.updatedAt = new Date();
    this.tasks.set(taskId, task);

    // 通知监听者
    this.notifyListeners({
      taskId,
      oldStatus,
      newStatus: status,
      task,
    });

    logger.info(`Task status updated: ${taskId} ${oldStatus} -> ${status}`);
    
    return task;
  }

  /**
   * 获取任务状态
   */
  getTaskStatus(taskId: string): TaskStatus | null {
    const task = this.tasks.get(taskId);
    return task?.status ?? null;
  }

  /**
   * 查询任务
   */
  queryTasks(filter?: { status?: TaskStatus; type?: string }): Task[] {
    return Array.from(this.tasks.values()).filter(task => {
      if (filter?.status && task.status !== filter.status) return false;
      if (filter?.type && task.type !== filter.type) return false;
      return true;
    });
  }

  /**
   * 添加状态变更监听器
   */
  onStateChange(listener: StateChangeListener): () => void {
    this.listeners.add(listener);
    
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * 通知所有监听者
   */
  private notifyListeners(event: StateChangeEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (error) {
        logger.error(`State change listener error: ${error}`);
      }
    }
  }

  /**
   * 添加任务
   */
  addTask(task: Task): void {
    this.tasks.set(task.id, task);
    logger.debug(`Task added to state manager: ${task.id}`);
  }

  /**
   * 移除任务
   */
  removeTask(taskId: string): boolean {
    return this.tasks.delete(taskId);
  }

  /**
   * 获取所有任务
   */
  getAllTasks(): Task[] {
    return Array.from(this.tasks.values());
  }
}

// 状态变更事件
export interface StateChangeEvent {
  taskId: string;
  oldStatus: TaskStatus;
  newStatus: TaskStatus;
  task: Task;
}

// 状态变更监听器
export type StateChangeListener = (event: StateChangeEvent) => void;

export default StateManager;
