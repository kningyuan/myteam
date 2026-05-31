import React, { useEffect, useState } from 'react';
import { KanbanColumn, Task, TaskStatus } from '../../types';
import { api } from '../../services/api';

const statusColors: Record<TaskStatus, string> = {
  pending: 'border-slate-500',
  in_progress: 'border-amber-500',
  waiting_for_input: 'border-blue-500',
  completed: 'border-emerald-500',
  failed: 'border-red-500',
};

const statusHeaderColors: Record<TaskStatus, string> = {
  pending: 'bg-slate-500/10 text-slate-300',
  in_progress: 'bg-amber-500/10 text-amber-300',
  waiting_for_input: 'bg-blue-500/10 text-blue-300',
  completed: 'bg-emerald-500/10 text-emerald-300',
  failed: 'bg-red-500/10 text-red-300',
};

const priorityBadge: Record<string, string> = {
  urgent: 'bg-red-500/20 text-red-300',
  high: 'bg-orange-500/20 text-orange-300',
  medium: 'bg-blue-500/20 text-blue-300',
  low: 'bg-slate-500/20 text-slate-400',
};

function TaskCard({ task }: { task: Task }) {
  return (
    <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg p-3 mb-2 hover:border-indigo-500/50 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-sm font-medium text-slate-100 truncate">{task.name}</h4>
        {task.priority && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${priorityBadge[task.priority]}`}>
            {task.priority}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-400 line-clamp-2 mb-2">{task.description}</p>
      <div className="flex items-center justify-between">
        {task.assignee && (
          <span className="text-[10px] text-indigo-400">@{task.assignee}</span>
        )}
        {task.deadline && (
          <span className="text-[10px] text-slate-500">
            {new Date(task.deadline).toLocaleDateString('zh-CN')}
          </span>
        )}
      </div>
    </div>
  );
}

export default function KanbanBoard() {
  const [board, setBoard] = useState<KanbanColumn[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.kanban.getKanban().then(res => {
      setBoard(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">任务看板</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">按状态查看和跟踪所有任务</p>
      </div>

      <div className="grid grid-cols-5 gap-4">
        {board.map(column => (
          <div key={column.status} className={`border-t-2 ${statusColors[column.status]} rounded-lg`}>
            <div className={`p-3 ${statusHeaderColors[column.status]} rounded-t-lg`}>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{column.label}</h3>
                <span className="text-xs bg-white/10 px-2 py-0.5 rounded-full">{column.count}</span>
              </div>
            </div>
            <div className="p-2 min-h-[200px]">
              {column.tasks.map(task => (
                <TaskCard key={task.id} task={task} />
              ))}
              {column.count === 0 && (
                <div className="text-center text-xs text-slate-600 py-8">暂无任务</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
