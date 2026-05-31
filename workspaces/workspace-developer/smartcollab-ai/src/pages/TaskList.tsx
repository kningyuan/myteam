// 智协AI - 任务列表页面

import React, { useState, useMemo } from 'react';
import { MainLayout } from '../components/layout';
import { Card, Badge, Button, StatusIndicator, ProgressBar } from '../ui';
import { useAppStore } from '../store/appStore';
import { 
  Search, Filter, Plus, LayoutList, LayoutGrid,
  CheckCircle2, Clock, AlertCircle, MoreVertical,
  Bot, User, Calendar, Tag
} from 'lucide-react';
import { Task, TaskStatus, Priority } from '../types';

// ============ 任务卡片 ============

interface TaskCardProps {
  task: Task;
  onView?: (task: Task) => void;
  onEdit?: (task: Task) => void;
  onDelete?: (task: Task) => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onView, onEdit, onDelete }) => {
  const statusConfig: Record<TaskStatus, { label: string; variant: 'success' | 'warning' | 'info' | 'error' | 'default'; icon: React.ReactNode }> = {
    pending: { label: '待处理', variant: 'default', icon: <Clock className="w-4 h-4" /> },
    in_progress: { label: '进行中', variant: 'info', icon: <Clock className="w-4 h-4 animate-spin-slow" /> },
    completed: { label: '已完成', variant: 'success', icon: <CheckCircle2 className="w-4 h-4" /> },
    failed: { label: '失败', variant: 'error', icon: <AlertCircle className="w-4 h-4" /> },
    waiting_for_input: { label: '等待输入', variant: 'warning', icon: <Clock className="w-4 h-4" /> },
  };
  
  const priorityConfig: Record<Priority, { label: string; variant: 'warning' | 'error' | 'info' | 'default' }> = {
    low: { label: '低', variant: 'default' },
    medium: { label: '中', variant: 'info' },
    high: { label: '高', variant: 'warning' },
    urgent: { label: '紧急', variant: 'error' },
  };
  
  const typeIcons = {
    meeting: '🎤',
    qa: '💬',
    document: '📝',
    agent: '⚡',
    custom: '📋',
  };
  
  const status = statusConfig[task.status];
  const priority = priorityConfig[task.priority];
  
  return (
    <Card className="hover:border-indigo-500/50 transition-colors">
      <div className="flex items-start gap-4">
        {/* 类型图标 */}
        <div className="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center text-xl">
          {task.aiExecutor ? <Bot className="w-5 h-5 text-indigo-400" /> : typeIcons[task.type]}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="font-medium text-slate-100 truncate">{task.name}</h4>
            <div className="flex items-center gap-1">
              {task.aiExecutor && (
                <Badge variant="info" size="sm">AI执行</Badge>
              )}
              <Badge variant={priority.variant} size="sm">{priority.label}</Badge>
            </div>
          </div>
          
          <p className="text-sm text-slate-400 mt-1 line-clamp-2">
            {task.description}
          </p>
          
          {/* 进度条（AI任务） */}
          {task.aiExecutor && task.aiSteps && (
            <div className="mt-3">
              <ProgressBar value={task.progress} showValue={true} size="sm" />
              {task.aiSteps && (
                <p className="text-xs text-slate-500 mt-1">
                  步骤: {task.aiSteps.filter(s => s.status === 'completed').length}/{task.aiSteps.length}
                </p>
              )}
            </div>
          )}
          
          {/* 元信息 */}
          <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
            <div className="flex items-center gap-1">
              {task.assignee ? (
                <>
                  <User className="w-3 h-3" />
                  <span>{task.assignee.name}</span>
                </>
              ) : (
                <>
                  <Bot className="w-3 h-3 text-indigo-400" />
                  <span>AI执行</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              <span>{new Date(task.createdAt).toLocaleDateString('zh-CN')}</span>
            </div>
            {task.tags && task.tags.length > 0 && (
              <div className="flex items-center gap-1">
                <Tag className="w-3 h-3" />
                <span>{task.tags.join(', ')}</span>
              </div>
            )}
          </div>
        </div>
        
        {/* 状态和操作 */}
        <div className="flex flex-col items-end gap-2">
          <StatusIndicator 
            status={task.status === 'completed' ? 'success' : 
                    task.status === 'in_progress' ? 'running' : 
                    task.status === 'failed' ? 'error' : 'pending'}
            label={status.label}
            size="sm"
          />
          
          <div className="flex items-center gap-1">
            {onView && (
              <Button variant="ghost" size="sm" onClick={() => onView(task)}>
                查看
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300">
                删除
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};

// ============ 任务列表页面 ============

const TaskListPage: React.FC = () => {
  const { tasks, addTask, updateTask } = useAppStore();
  
  // 状态过滤
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  
  // 过滤和搜索任务
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      if (statusFilter !== 'all' && task.status !== statusFilter) return false;
      if (searchQuery && !task.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [tasks, statusFilter, searchQuery]);
  
  // 模拟数据（如果没有真实数据）
  const displayTasks = tasks.length > 0 ? tasks : [
    {
      id: '1',
      name: '产品PRD撰写',
      description: '完成Q2产品规划PRD文档，包含功能规格、用户故事、验收标准',
      type: 'document' as const,
      status: 'completed' as const,
      priority: 'high' as const,
      progress: 100,
      assignee: { id: 'u1', name: '张三', role: 'member' as const },
      aiExecutor: false,
      createdAt: '2026-05-16T10:00:00Z',
      updatedAt: '2026-05-16T22:50:00Z',
      completedAt: '2026-05-16T22:50:00Z',
      tags: ['产品', '文档'],
    },
    {
      id: '2',
      name: '市场调研分析',
      description: '收集AI团队协作工具市场数据，分析竞品优劣势',
      type: 'qa' as const,
      status: 'pending' as const,
      priority: 'medium' as const,
      progress: 0,
      assignee: { id: 'u2', name: '李四', role: 'member' as const },
      aiExecutor: false,
      createdAt: '2026-05-16T14:00:00Z',
      updatedAt: '2026-05-16T14:00:00Z',
      tags: ['调研', '竞品'],
    },
    {
      id: '3',
      name: 'AI执行: 自动创建任务并通知成员',
      description: '跨应用任务自动完成，创建任务后自动通知相关成员',
      type: 'agent' as const,
      status: 'in_progress' as const,
      priority: 'high' as const,
      progress: 60,
      aiExecutor: true,
      aiSteps: [
        { id: 's1', name: '创建任务记录', status: 'completed' },
        { id: 's2', name: '发送通知消息', status: 'running' },
        { id: 's3', name: '更新任务状态', status: 'pending' },
      ],
      createdAt: '2026-05-17T01:00:00Z',
      updatedAt: '2026-05-17T01:30:00Z',
      tags: ['AI执行', '自动化'],
    },
  ];
  
  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">任务列表</h1>
            <p className="text-slate-400 mt-1">
              共 {displayTasks.length} 个任务 · {displayTasks.filter(t => t.status === 'in_progress').length} 个进行中
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary">
              <Plus className="w-4 h-4 mr-1" />
              新建任务
            </Button>
            <Button>
              <Bot className="w-4 h-4 mr-1" />
              +AI执行
            </Button>
          </div>
        </div>
        
        {/* 筛选和搜索 */}
        <Card padding="sm" className="mb-4">
          <div className="flex items-center gap-4">
            {/* 状态筛选 */}
            <div className="flex items-center gap-1">
              {(['all', 'pending', 'in_progress', 'completed'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    statusFilter === status
                      ? 'bg-indigo-900/50 text-indigo-400'
                      : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                  }`}
                >
                  {status === 'all' ? '全部' : status === 'pending' ? '待处理' : status === 'in_progress' ? '进行中' : '已完成'}
                </button>
              ))}
            </div>
            
            {/* 搜索框 */}
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="搜索任务..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full md:w-64 bg-slate-700 border border-slate-600 rounded-lg pl-9 pr-4 py-1.5 text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            {/* 视图切换 */}
            <div className="flex items-center gap-1 border-l border-slate-700 pl-4">
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}
              >
                <LayoutList className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
          </div>
        </Card>
        
        {/* 任务列表 */}
        <div className={viewMode === 'list' ? 'space-y-3' : 'grid grid-cols-1 md:grid-cols-2 gap-4'}>
          {displayTasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
        
        {displayTasks.length === 0 && (
          <Card className="text-center py-12">
            <Search className="w-12 h-12 mx-auto text-slate-600 mb-3" />
            <p className="text-slate-400">未找到匹配的任务</p>
          </Card>
        )}
      </div>
    </MainLayout>
  );
};

export default TaskListPage;