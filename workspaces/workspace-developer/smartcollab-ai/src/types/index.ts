// 项目
export interface Project {
  id: string;
  name: string;
  description: string;
  workflowCount: number;
  agentCount: number;
  status: 'active' | 'archived';
  updatedAt: string;
  createdAt: string;
}

// 工作流 (DAG)
export interface Workflow {
  id: string;
  projectId: string;
  name: string;
  description: string;
  status: 'draft' | 'published' | 'running' | 'completed' | 'failed';
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  createdAt: string;
  updatedAt: string;
}

// DAG 节点
export interface WorkflowNode {
  id: string;
  type: 'agent-task' | 'trigger' | 'condition' | 'output';
  label: string;
  agentId?: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'skipped';
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

// DAG 连接
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
}

// Agent
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
  createdAt: string;
}

// 执行记录
export interface ExecutionRecord {
  id: string;
  workflowId: string;
  workflowName: string;
  projectName: string;
  status: 'running' | 'completed' | 'failed' | 'paused';
  progress: number;
  startedAt: string;
  completedAt?: string;
  duration?: string;
  nodeStatuses: Record<string, 'idle' | 'running' | 'completed' | 'failed' | 'skipped'>;
}

// 看板统计
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

// 通知
export interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

// 用户
export type UserRole = 'admin' | 'member' | 'viewer';
export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: UserRole;
}

// API 响应
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'waiting_for_input';
export type Priority = 'low' | 'medium' | 'high' | 'urgent';
export type TaskType = 'meeting' | 'qa' | 'document' | 'agent' | 'custom';

export interface TaskComment {
  id: string;
  taskId: string;
  author: string;
  content: string;
  createdAt: string;
  mentions?: string[];
}

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
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  tags?: string[];
  dependencies?: string[];
  deadline?: string;
  claimable?: boolean;
  comments?: TaskComment[];
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
  deadline: string;
  daysRemaining: number;
  severity: 'info' | 'warning' | 'critical' | 'overdue';
}

export interface BackendNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  taskId?: string;
  createdAt: string;
  read: boolean;
}