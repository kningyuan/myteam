import React from 'react';
import { useAppStore } from '../store/appStore';
import { useNavigate } from 'react-router-dom';
import { Play, CheckCircle2, XCircle, Clock, TrendingUp, TrendingDown, Bot, GitBranch, Activity } from 'lucide-react';

export default function Dashboard() {
  const { dashboardStats, executions } = useAppStore();
  const navigate = useNavigate();

  const statCards = [
    { label: '运行中', value: dashboardStats.running, delta: dashboardStats.runningDelta, icon: Play, color: 'text-amber-400', bg: 'bg-amber-500/10' },
    { label: '已完成', value: dashboardStats.completed, delta: dashboardStats.completedDelta, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { label: '失败', value: dashboardStats.failed, delta: dashboardStats.failedDelta, icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10' },
    { label: '平均耗时', value: dashboardStats.avgDuration, delta: dashboardStats.avgDurationDelta, icon: Clock, color: 'text-indigo-400', bg: 'bg-indigo-500/10', isString: true },
  ];

  return (
    <div className="max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">实时看板</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">监控所有工作流的执行状态</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((card) => (
          <div key={card.label} className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-[var(--color-text-secondary)]">{card.label}</span>
              <div className={`w-8 h-8 rounded-lg ${card.bg} flex items-center justify-center`}>
                <card.icon className={`w-4 h-4 ${card.color}`} />
              </div>
            </div>
            <div className="text-2xl font-bold text-[var(--color-text-primary)]">{card.value}</div>
            <div className={`flex items-center gap-1 text-xs mt-1 ${card.delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {card.delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{card.delta >= 0 ? '+' : ''}{card.delta}{card.isString ? '%' : ''} 较昨日</span>
            </div>
          </div>
        ))}
      </div>

      {/* Running workflows */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">执行中的工作流</h2>
          <button className="text-sm text-indigo-400 hover:text-indigo-300">查看全部 →</button>
        </div>
        <div className="space-y-3">
          {executions.filter((e) => e.status === 'running').map((exec) => (
            <div key={exec.id} className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-5 hover:border-indigo-500/50 transition-colors cursor-pointer"
              onClick={() => navigate('/workflows')}>
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-amber-400 animate-pulse-running" />
                <span className="font-semibold text-[var(--color-text-primary)]">{exec.workflowName}</span>
                <span className="text-xs text-[var(--color-text-tertiary)]">{exec.projectName}</span>
                <span className="ml-auto text-xs text-[var(--color-text-tertiary)]">启动: {exec.startedAt ? '2m 前' : ''}</span>
              </div>
              <div className="flex items-center gap-2 mb-3">
                {Object.entries(exec.nodeStatuses).slice(0, 4).map(([nodeId, status]) => (
                  <div key={nodeId} className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium ${
                    status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                    status === 'running' ? 'bg-amber-500/20 text-amber-400 animate-pulse-running' :
                    status === 'failed' ? 'bg-red-500/20 text-red-400' :
                    'bg-slate-700 text-slate-500'
                  }`}>
                    {status === 'completed' ? '✅' : status === 'running' ? '🔄' : status === 'failed' ? '❌' : '⏸'}
                  </div>
                ))}
                {Object.keys(exec.nodeStatuses).length > 4 && (
                  <span className="text-xs text-[var(--color-text-tertiary)]">+{Object.keys(exec.nodeStatuses).length - 4}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                    style={{ width: `${exec.progress}%` }} />
                </div>
                <span className="text-xs text-[var(--color-text-secondary)] w-10 text-right">{exec.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Recent completions */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">最近完成</h2>
          <button className="text-sm text-indigo-400 hover:text-indigo-300">查看全部 →</button>
        </div>
        <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl divide-y divide-[var(--color-border)]">
          {executions.filter((e) => e.status === 'completed').map((exec) => (
            <div key={exec.id} className="flex items-center gap-4 px-5 py-3 hover:bg-[var(--color-bg-tertiary)] transition-colors cursor-pointer"
              onClick={() => navigate('/workflows')}>
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              <span className="flex-1 text-sm text-[var(--color-text-primary)]">{exec.workflowName}</span>
              <span className="text-xs text-[var(--color-text-tertiary)]">{exec.projectName}</span>
              <span className="text-xs text-[var(--color-text-tertiary)]">完成: 30s 前</span>
              <span className="text-xs text-[var(--color-text-secondary)] font-mono">{exec.duration}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}