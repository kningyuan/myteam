import React from 'react';
import { useAppStore } from '../store/appStore';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Grid3X3, List, FolderKanban, MoreHorizontal } from 'lucide-react';

export default function ProjectList() {
  const { projects } = useAppStore();
  const navigate = useNavigate();

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">项目总览</h1>
        <button className="h-9 px-4 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2">
          <Plus className="w-4 h-4" /> 新建项目
        </button>
      </div>

      {/* Search/filter bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
          <input type="text" placeholder="搜索项目..."
            className="w-full h-9 pl-9 pr-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent" />
        </div>
        <select className="h-9 px-3 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>最近更新</option>
          <option>名称</option>
          <option>状态</option>
        </select>
        <select className="h-9 px-3 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>全部状态</option>
          <option>活跃</option>
          <option>已归档</option>
        </select>
        <div className="flex border border-[var(--color-border)] rounded-lg overflow-hidden">
          <button className="p-2 bg-indigo-500/10 text-indigo-400"><Grid3X3 className="w-4 h-4" /></button>
          <button className="p-2 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"><List className="w-4 h-4" /></button>
        </div>
      </div>

      {/* Project grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((project) => (
          <div key={project.id} onClick={() => navigate('/workflows')}
            className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-5 cursor-pointer hover:border-indigo-500/50 transition-all duration-200 group">
            <div className="flex items-start justify-between mb-4">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
                <FolderKanban className="w-5 h-5 text-white" />
              </div>
              <button className="opacity-0 group-hover:opacity-100 p-1 rounded text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] transition-all"
                onClick={(e) => e.stopPropagation()}>
                <MoreHorizontal className="w-4 h-4" />
              </button>
            </div>
            <h3 className="font-semibold text-[var(--color-text-primary)] mb-1">{project.name}</h3>
            <p className="text-sm text-[var(--color-text-secondary)] mb-4 line-clamp-2">{project.description}</p>
            <div className="flex items-center gap-4 text-xs text-[var(--color-text-tertiary)]">
              <span>{project.workflowCount} 个工作流</span>
              <span>{project.agentCount} 个 Agent</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}