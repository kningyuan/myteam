import { create } from 'zustand';
import type { Project, Workflow, Agent, ExecutionRecord, DashboardStats, Notification, User } from '../types';

interface AppState {
  // Auth
  isAuthenticated: boolean;
  currentUser: User | null;
  login: (user: User) => void;
  logout: () => void;

  // Projects
  projects: Project[];
  setProjects: (projects: Project[]) => void;

  // Workflows
  workflows: Workflow[];
  setWorkflows: (workflows: Workflow[]) => void;

  // Agents
  agents: Agent[];
  setAgents: (agents: Agent[]) => void;

  // Executions
  executions: ExecutionRecord[];
  setExecutions: (executions: ExecutionRecord[]) => void;

  // Dashboard Stats
  dashboardStats: DashboardStats;
  setDashboardStats: (stats: DashboardStats) => void;

  // Notifications
  notifications: Notification[];
  addNotification: (notification: Notification) => void;
  markRead: (id: string) => void;
  unreadCount: number;

  // UI
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

const mockProjects: Project[] = [
  { id: 'proj-1', name: '前端重构项目', description: '将 legacy 代码迁移到 React + TypeScript', workflowCount: 3, agentCount: 2, status: 'active', updatedAt: '2026-05-17T10:30:00Z', createdAt: '2026-05-15T08:00:00Z' },
  { id: 'proj-2', name: '内容生成流水线', description: 'AI 驱动的自动化内容生产流程', workflowCount: 1, agentCount: 4, status: 'active', updatedAt: '2026-05-17T09:15:00Z', createdAt: '2026-05-14T10:00:00Z' },
  { id: 'proj-3', name: 'API 测试流水线', description: '自动化 API 集成测试与回归', workflowCount: 5, agentCount: 3, status: 'active', updatedAt: '2026-05-16T14:20:00Z', createdAt: '2026-05-13T09:00:00Z' },
  { id: 'proj-4', name: '代码审查工作流', description: 'PR 自动审查与合并流程', workflowCount: 2, agentCount: 5, status: 'active', updatedAt: '2026-05-17T08:00:00Z', createdAt: '2026-05-12T11:00:00Z' },
];

const mockAgents: Agent[] = [
  { id: 'agent-1', name: 'Code Agent', role: 'coding', status: 'online', description: '代码生成与审查', apiEndpoint: 'https://api.example.com/code/v1', avgResponseTime: 2.3, successRate: 98.5, projects: ['proj-1', 'proj-4'], createdAt: '2026-05-10T08:00:00Z' },
  { id: 'agent-2', name: 'Review Agent', role: 'review', status: 'online', description: '代码审查与建议', apiEndpoint: 'https://api.example.com/review/v1', avgResponseTime: 5.1, successRate: 96.2, projects: ['proj-4'], createdAt: '2026-05-10T09:00:00Z' },
  { id: 'agent-3', name: 'Deploy Agent', role: 'deploy', status: 'offline', description: '自动部署与发布', apiEndpoint: 'https://api.example.com/deploy/v1', avgResponseTime: 8.7, successRate: 92.1, projects: ['proj-1'], createdAt: '2026-05-10T10:00:00Z' },
  { id: 'agent-4', name: 'Test Agent', role: 'testing', status: 'online', description: '自动化测试执行', apiEndpoint: 'https://api.example.com/test/v1', avgResponseTime: 12.4, successRate: 94.7, projects: ['proj-1', 'proj-3'], createdAt: '2026-05-10T11:00:00Z' },
  { id: 'agent-5', name: 'Research Agent', role: 'research', status: 'busy', description: '信息检索与分析', apiEndpoint: 'https://api.example.com/research/v1', avgResponseTime: 15.2, successRate: 93.8, projects: ['proj-2'], createdAt: '2026-05-10T12:00:00Z' },
];

const mockExecutions: ExecutionRecord[] = [
  { id: 'exec-1', workflowId: 'wf-1', workflowName: '代码审查工作流', projectName: '项目A', status: 'running', progress: 40, startedAt: '2026-05-17T10:00:00Z', nodeStatuses: { 'node-1': 'completed', 'node-2': 'running', 'node-3': 'idle', 'node-4': 'idle' } },
  { id: 'exec-2', workflowId: 'wf-2', workflowName: '内容生成流水线', projectName: '项目B', status: 'running', progress: 66, startedAt: '2026-05-17T09:57:00Z', nodeStatuses: { 'node-1': 'completed', 'node-2': 'completed', 'node-3': 'running' } },
  { id: 'exec-3', workflowId: 'wf-3', workflowName: '数据处理流水线', projectName: '项目C', status: 'completed', progress: 100, startedAt: '2026-05-17T09:30:00Z', completedAt: '2026-05-17T09:32:12Z', duration: '2m 12s', nodeStatuses: {} },
];

const mockStats: DashboardStats = {
  running: 3, completed: 12, failed: 1, avgDuration: '1m 23s',
  runningDelta: 2, completedDelta: 5, failedDelta: -1, avgDurationDelta: -12,
};

export const useAppStore = create<AppState>((set, get) => ({
  isAuthenticated: true,
  currentUser: { id: 'user-1', name: '张工', email: 'zhang@example.com', role: 'admin' },

  login: (user) => set({ isAuthenticated: true, currentUser: user }),
  logout: () => set({ isAuthenticated: false, currentUser: null }),

  projects: mockProjects,
  setProjects: (projects) => set({ projects }),

  workflows: [],
  setWorkflows: (workflows) => set({ workflows }),

  agents: mockAgents,
  setAgents: (agents) => set({ agents }),

  executions: mockExecutions,
  setExecutions: (executions) => set({ executions }),

  dashboardStats: mockStats,
  setDashboardStats: (stats) => set({ dashboardStats: stats }),

  notifications: [],
  unreadCount: 0,
  addNotification: (n) => set((s) => ({ notifications: [n, ...s.notifications], unreadCount: s.unreadCount + 1 })),
  markRead: (id) => set((s) => ({
    notifications: s.notifications.map((n) => n.id === id ? { ...n, read: true } : n),
    unreadCount: Math.max(0, s.unreadCount - 1),
  })),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));