// 任务状态
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'waiting_for_input';

// 任务优先级
export type Priority = 'low' | 'medium' | 'high' | 'urgent';

// 任务类型
export type TaskType = 'meeting' | 'qa' | 'document' | 'agent' | 'custom';

// AI执行状态
export type AIExecutionStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed';

// 任务接口
export interface Task {
  id: string;
  name: string;
  description: string;
  type: TaskType;
  status: TaskStatus;
  priority: Priority;
  progress: number;
  assignee?: string;
  aiExecutor?: boolean;
  aiSteps?: AIStep[];
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
  tags?: string[];
  timeoutMs?: number;
  startedAt?: Date;
  dependencies?: string[];
  deadline?: Date;
  claimable?: boolean;
  comments?: TaskComment[];
}

export interface TaskComment {
  id: string;
  taskId: string;
  author: string;
  content: string;
  createdAt: Date;
  mentions?: string[];
}

export interface KanbanColumn {
  status: TaskStatus;
  label: string;
  tasks: Task[];
  count: number;
}

export interface DeadlineWarning {
  taskId: string;
  taskName: string;
  deadline: Date;
  daysRemaining: number;
  severity: 'info' | 'warning' | 'critical' | 'overdue';
}

export interface CreateCommentOptions {
  taskId: string;
  author: string;
  content: string;
  mentions?: string[];
}

// AI执行步骤
export interface AIStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  description?: string;
  startedAt?: Date;
  completedAt?: Date;
}

// 任务创建选项
export interface CreateTaskOptions {
  name: string;
  description: string;
  type: TaskType;
  priority?: Priority;
  tags?: string[];
  timeoutMs?: number;
  dependencies?: string[];
  aiExecutor?: boolean;
  deadline?: Date;
  claimable?: boolean;
}

// 任务更新选项
export interface UpdateTaskOptions {
  name?: string;
  description?: string;
  status?: TaskStatus;
  priority?: Priority;
  progress?: number;
  assignee?: string;
  tags?: string[];
}

// 任务查询选项
export interface TaskQueryOptions {
  status?: TaskStatus;
  type?: TaskType;
  priority?: Priority;
  assignee?: string;
  limit?: number;
  offset?: number;
}

// 调度器配置
export interface SchedulerConfig {
  maxConcurrentTasks: number;
  defaultTimeoutMs: number;
  retryMaxAttempts: number;
  retryDelayMs: number;
  heartbeatIntervalMs: number;
}

// ============ DAG 工作流 ============

export type WorkflowStatus = 'draft' | 'published' | 'running' | 'completed' | 'failed';
export type NodeStatus = 'idle' | 'running' | 'completed' | 'failed' | 'skipped';
export type NodeType = 'agent-task' | 'trigger' | 'condition' | 'output';

export interface WorkflowNode {
  id: string;
  type: NodeType;
  label: string;
  agentId?: string;
  status: NodeStatus;
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
}

export interface Workflow {
  id: string;
  projectId: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateWorkflowOptions {
  projectId: string;
  name: string;
  description: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
}

// ============ Agent ============

export type AgentStatus = 'online' | 'offline' | 'busy';
export type AgentRole = 'coding' | 'review' | 'testing' | 'deploy' | 'research' | 'writing' | 'custom';

export interface Agent {
  id: string;
  name: string;
  role: AgentRole;
  status: AgentStatus;
  description: string;
  apiEndpoint: string;
  avgResponseTime: number;
  successRate: number;
  projects: string[];
  createdAt: Date;
}

export interface CreateAgentOptions {
  name: string;
  role: AgentRole;
  description: string;
  apiEndpoint: string;
}

// ============ 执行记录 ============

export type ExecutionStatus = 'running' | 'completed' | 'failed' | 'paused';

export interface ExecutionRecord {
  id: string;
  workflowId: string;
  workflowName: string;
  projectName: string;
  status: ExecutionStatus;
  progress: number;
  startedAt: Date;
  completedAt?: Date;
  duration?: string;
  nodeStatuses: Record<string, NodeStatus>;
}

// ============ 项目 ============

export interface Project {
  id: string;
  name: string;
  description: string;
  workflowCount: number;
  agentCount: number;
  status: 'active' | 'archived';
  updatedAt: Date;
  createdAt: Date;
}

// ============ 看板统计 ============

export interface DashboardStats {
  running: number;
  completed: number;
  failed: number;
  avgDuration: string;
  runningDelta: number;
  completedDelta: number;
  failedDelta: number;
  avgDurationDelta: number;
}

// ============ 通知 ============

export type NotificationType = 'task_start' | 'task_complete' | 'task_failed' | 'task_timeout' | 'status_change' | 'error_alert';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  taskId?: string;
  data?: Record<string, unknown>;
  createdAt: Date;
  read: boolean;
}

export interface NotificationConfig {
  telegramBotToken?: string;
  telegramChatId?: string;
  enableEmail: boolean;
  emailSMTP?: {
    host: string;
    port: number;
    user: string;
    pass: string;
  };
}

// ============ API ============

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

// ============ WebSocket ============

export type WSEventType = 'workflow_status' | 'node_status' | 'execution_progress' | 'notification';

export interface WSEvent {
  type: WSEventType;
  data: Record<string, unknown>;
  timestamp: string;
}