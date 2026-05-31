import React, { useState } from 'react';
import { useAppStore } from '../store/appStore';
import { Search, Plus, MoreHorizontal, Wifi, WifiOff, Activity, Bot, Play, Settings, Edit3, X } from 'lucide-react';
import type { Agent, AgentRole } from '../types';

const roleColors: Record<AgentRole, string> = {
  coding: 'bg-blue-500/10 text-blue-400',
  review: 'bg-purple-500/10 text-purple-400',
  testing: 'bg-emerald-500/10 text-emerald-400',
  deploy: 'bg-amber-500/10 text-amber-400',
  research: 'bg-rose-500/10 text-rose-400',
  writing: 'bg-cyan-500/10 text-cyan-400',
  custom: 'bg-slate-500/10 text-slate-400',
};

const roleLabels: Record<AgentRole, string> = {
  coding: '编码 Agent',
  review: '审查 Agent',
  testing: '测试 Agent',
  deploy: '部署 Agent',
  research: '调研 Agent',
  writing: '写作 Agent',
  custom: '自定义',
};

export default function AgentPage() {
  const { agents } = useAppStore();
  const [showRegister, setShowRegister] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [roleFilter, setRoleFilter] = useState<string>('all');

  const filtered = agents.filter((a) => {
    if (statusFilter !== 'all' && a.status !== statusFilter) return false;
    if (roleFilter !== 'all' && a.role !== roleFilter) return false;
    if (searchQuery && !a.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">Agent 管理</h1>
        <button onClick={() => setShowRegister(true)}
          className="h-9 px-4 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          <Plus className="w-4 h-4" /> 注册 Agent
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="搜索 Agent..."
            className="w-full h-9 pl-9 pr-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 px-3 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option value="all">全部状态</option>
          <option value="online">在线</option>
          <option value="offline">离线</option>
          <option value="busy">忙碌</option>
        </select>
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
          className="h-9 px-3 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option value="all">全部角色</option>
          <option value="coding">编码</option>
          <option value="review">审查</option>
          <option value="testing">测试</option>
          <option value="deploy">部署</option>
          <option value="research">调研</option>
        </select>
      </div>

      {/* Agent list */}
      <div className="space-y-2">
        {filtered.map((agent) => (
          <div key={agent.id} className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-4 hover:border-indigo-500/50 transition-colors">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                {agent.name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1">
                  <h3 className="font-semibold text-[var(--color-text-primary)]">{agent.name}</h3>
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                    agent.status === 'online' ? 'bg-emerald-500/10 text-emerald-400' :
                    agent.status === 'busy' ? 'bg-amber-500/10 text-amber-400' :
                    'bg-slate-500/10 text-slate-400'
                  }`}>
                    {agent.status === 'online' ? <Wifi className="w-3 h-3" /> :
                     agent.status === 'busy' ? <Activity className="w-3 h-3" /> :
                     <WifiOff className="w-3 h-3" />}
                    {agent.status === 'online' ? '在线' : agent.status === 'busy' ? '忙碌' : '离线'}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded ${roleColors[agent.role]}`}>
                    {roleLabels[agent.role]}
                  </span>
                </div>
                <div className="text-xs text-[var(--color-text-tertiary)] space-y-0.5">
                  <div>API: {agent.apiEndpoint}</div>
                  <div className="flex items-center gap-4 mt-1">
                    <span>⏱ 平均 {agent.avgResponseTime}s</span>
                    <span>✅ 成功率 {agent.successRate}%</span>
                    <span>📁 {agent.projects.length} 个项目</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors" title="编辑">
                  <Edit3 className="w-4 h-4" />
                </button>
                <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors" title="配置">
                  <Settings className="w-4 h-4" />
                </button>
                <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-tertiary)] hover:text-emerald-400 transition-colors" title="测试">
                  <Play className="w-4 h-4" />
                </button>
                <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors">
                  <MoreHorizontal className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Register modal */}
      {showRegister && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowRegister(false)}>
          <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">注册新 Agent</h2>
              <button onClick={() => setShowRegister(false)} className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">Agent 名称</label>
                <input placeholder="输入 Agent 名称..."
                  className="w-full h-10 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">角色</label>
                <select className="w-full h-10 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option>编码 Agent</option>
                  <option>审查 Agent</option>
                  <option>测试 Agent</option>
                  <option>部署 Agent</option>
                  <option>调研 Agent</option>
                  <option>自定义</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">API 端点</label>
                <input placeholder="https://api.example.com/agent/v1"
                  className="w-full h-10 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">描述</label>
                <textarea rows={3} placeholder="Agent 的功能描述..."
                  className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
              </div>
              <button className="w-full h-10 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors">
                注册
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}