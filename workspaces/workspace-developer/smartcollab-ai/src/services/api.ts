// 智协AI - API 服务层

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { ApiResponse, PaginatedResponse, KanbanColumn, DeadlineWarning, BackendNotification, TaskComment, Task } from '../types';

// API基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api';

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 添加认证token（如果存在）
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // 添加请求时间戳
    config.params = {
      ...config.params,
      _t: Date.now(),
    };
    
    return config;
  },
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse<any>>) => {
    const { data } = response;
    
    if (!data.success) {
      return Promise.reject(new Error(data.error?.message || 'API请求失败'));
    }
    
    return response;
  },
  (error) => {
    console.error('Response error:', error);
    
    // 处理常见错误
    if (error.response?.status === 401) {
      // 未授权，清除token并跳转登录
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    
    return Promise.reject(error);
  }
);

// API请求方法封装
async function request<T>(
  endpoint: string,
  options?: AxiosRequestConfig
): Promise<ApiResponse<T>> {
  const response = await apiClient.get<ApiResponse<T>>(endpoint, options);
  return response.data;
}

async function postRequest<T>(
  endpoint: string,
  data?: unknown,
  options?: AxiosRequestConfig
): Promise<ApiResponse<T>> {
  const response = await apiClient.post<ApiResponse<T>>(endpoint, data, options);
  return response.data;
}

async function putRequest<T>(
  endpoint: string,
  data?: unknown,
  options?: AxiosRequestConfig
): Promise<ApiResponse<T>> {
  const response = await apiClient.put<ApiResponse<T>>(endpoint, data, options);
  return response.data;
}

async function deleteRequest<T>(
  endpoint: string,
  options?: AxiosRequestConfig
): Promise<ApiResponse<T>> {
  const response = await apiClient.delete<ApiResponse<T>>(endpoint, options);
  return response.data;
}

// ============ 任务API ============

export const taskAPI = {
  // 获取任务列表
  getTasks: (params?: { status?: string; type?: string; page?: number; pageSize?: number }) =>
    request<PaginatedResponse<Task>>('/tasks', { params }),
  
  // 获取单个任务
  getTask: (taskId: string) => request<Task>(`/tasks/${taskId}`),
  
  // 创建任务
  createTask: (data: Partial<Task>) => postRequest<Task>('/tasks', data),
  
  // 更新任务
  updateTask: (taskId: string, data: Partial<Task>) => 
    putRequest<Task>(`/tasks/${taskId}`, data),
  
  // 删除任务
  deleteTask: (taskId: string) => deleteRequest(`/tasks/${taskId}`),
  
  // 获取AI执行任务
  getAITasks: () => request<Task[]>('/tasks/ai'),
};

// ============ 会议API ============

export const meetingAPI = {
  // 获取会议列表
  getMeetings: (params?: { status?: string; page?: number }) =>
    request<PaginatedResponse<Meeting>>('/meetings', { params }),
  
  // 获取单个会议
  getMeeting: (meetingId: string) => request<Meeting>(`/meetings/${meetingId}`),
  
  // 开始会议
  startMeeting: (data: { title: string; participants?: string[] }) =>
    postRequest<Meeting>('/meetings/start', data),
  
  // 结束会议
  endMeeting: (meetingId: string) => postRequest<Meeting>(`/meetings/${meetingId}/end`),
  
  // 获取实时转录
  getTranscription: (meetingId: string) =>
    request<{ transcription: string; currentSpeaker?: string }>(`/meetings/${meetingId}/transcription`),
  
  // 生成会议纪要
  generateSummary: (meetingId: string) =>
    postRequest<MeetingSummary>(`/meetings/${meetingId}/summary`),
};

// ============ 问答API ============

export const qaAPI = {
  // 智能问答
  askQuestion: (question: string, context?: string) =>
    postRequest<QAResponse>('/qa/ask', { question, context }),
  
  // 获取问答历史
  getHistory: (params?: { limit?: number }) =>
    request<QAConversation[]>('/qa/history', { params }),
  
  // 清除历史
  clearHistory: () => deleteRequest('/qa/history'),
  
  // 搜索知识库
  searchKnowledge: (query: string, params?: { limit?: number; types?: string[] }) =>
    request<KnowledgeSearchResult>('/qa/search', { params: { q: query, ...params } }),
};

// ============ 文档API ============

export const documentAPI = {
  // 生成文档
  generateDocument: (data: { type: string; template?: string; content?: string }) =>
    postRequest<Document>('/documents/generate', data),
  
  // 获取文档列表
  getDocuments: (params?: { type?: string; page?: number }) =>
    request<PaginatedResponse<Document>>('/documents', { params }),
  
  // 获取单个文档
  getDocument: (docId: string) => request<Document>(`/documents/${docId}`),
  
  // 更新文档
  updateDocument: (docId: string, data: Partial<Document>) =>
    putRequest<Document>(`/documents/${docId}`, data),
  
  // 导出文档
  exportDocument: (docId: string, format: 'markdown' | 'word' | 'pdf') =>
    request<Blob>(`/documents/${docId}/export?format=${format}`),
};

// ============ 系统API ============

export const systemAPI = {
  // 获取系统状态
  getStatus: () => request<SystemStatus>('/system/status'),
  
  // 获取AI执行状态
  getAIStatus: () => request<AIExecutionState>('/system/ai-status'),
  
  // 获取在线用户
  getOnlineUsers: () => request<User[]>('/system/users'),
};

// ============ 协作流程 API ============

export const kanbanAPI = {
  getKanban: () => request<KanbanColumn[]>('/kanban'),
};

export const warningAPI = {
  getDeadlineWarnings: () => request<DeadlineWarning[]>('/warnings/deadline'),
};

export const claimAPI = {
  claimTask: (taskId: string, claimant: string) => postRequest<Task>(`/tasks/${taskId}/claim`, { claimant }),
  getClaimable: () => request<Task[]>('/tasks/claimable'),
};

export const commentAPI = {
  getComments: (taskId: string) => request<TaskComment[]>(`/tasks/${taskId}/comments`),
  addComment: (taskId: string, data: { author: string; content: string; mentions?: string[] }) =>
    postRequest<TaskComment>(`/tasks/${taskId}/comments`, data),
};

export const notificationAPI = {
  getNotifications: () => request<{ data: BackendNotification[]; unread: number }>('/notifications'),
  markAsRead: (notifId: string) => postRequest(`/notifications/${notifId}/read`),
};

// ============ 类型定义（API响应相关） ============

interface Task {
  id: string;
  name: string;
  status: string;
  // ... 其他字段
}

interface Meeting {
  id: string;
  title: string;
  // ... 其他字段
}

interface MeetingSummary {
  keyPoints: string[];
  decisions: string[];
  actionItems: ActionItem[];
}

interface ActionItem {
  id: string;
  content: string;
  assignee?: string;
  status: string;
}

interface QAResponse {
  answer: string;
  sources: QASource[];
  confidence: number;
}

interface QASource {
  id: string;
  title: string;
  type: string;
  snippet: string;
  url?: string;
  relevance: number;
}

interface QAConversation {
  id: string;
  question: string;
  answer: string;
  timestamp: string;
}

interface KnowledgeSearchResult {
  results: QASource[];
  total: number;
}

interface Document {
  id: string;
  title: string;
  type: string;
  content?: string;
  createdAt: string;
}

interface SystemStatus {
  healthy: boolean;
  aiRunning: boolean;
  onlineUsers: number;
}

interface AIExecutionState {
  status: 'idle' | 'running' | 'paused' | 'completed';
  currentTask?: string;
  progress: number;
  currentStep?: string;
}

// 导出axios实例（用于自定义请求）
export { apiClient };

// 导出默认
export default apiClient;