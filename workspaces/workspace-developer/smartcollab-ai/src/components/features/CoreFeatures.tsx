// 智协AI - 核心功能入口卡片

import React from 'react';
import { Mic, MessageSquare, FileText, Zap } from 'lucide-react';
import { Card } from '../ui';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: string;
  onClick?: () => void;
  badge?: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({
  icon,
  title,
  description,
  color,
  onClick,
  badge,
}) => {
  return (
    <Card
      className="cursor-pointer hover:border-indigo-500/50 transition-all duration-200 group"
      onClick={onClick}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-100 group-hover:text-indigo-400 transition-colors">
              {title}
            </h3>
            {badge && (
              <span className="px-1.5 py-0.5 text-xs bg-amber-900/50 text-amber-400 rounded">
                {badge}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-400 mt-1 line-clamp-2">
            {description}
          </p>
        </div>
      </div>
    </Card>
  );
};

// ============ 核心功能入口区 ============

export const CoreFeatures: React.FC = () => {
  const features = [
    {
      id: 'meeting',
      icon: <Mic className="w-6 h-6 text-white" />,
      title: '智能会议助手',
      description: '实时语音转文字，自动生成纪要和待办事项',
      color: 'bg-gradient-to-br from-indigo-500 to-purple-600',
      badge: 'P0',
    },
    {
      id: 'qa',
      icon: <MessageSquare className="w-6 h-6 text-white" />,
      title: '跨知识库问答',
      description: '自然语言提问，智能搜索文档和聊天记录',
      color: 'bg-gradient-to-br from-emerald-500 to-cyan-600',
      badge: 'P0',
    },
    {
      id: 'document',
      icon: <FileText className="w-6 h-6 text-white" />,
      title: 'AI文档生成',
      description: '快速生成PRD、报告、方案等文档初稿',
      color: 'bg-gradient-to-br from-amber-500 to-orange-600',
      badge: 'P0',
    },
    {
      id: 'agent',
      icon: <Zap className="w-6 h-6 text-white" />,
      title: 'AI Agent执行',
      description: '跨应用任务自动完成，沟通即执行',
      color: 'bg-gradient-to-br from-rose-500 to-pink-600',
      badge: 'P1',
    },
  ];
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {features.map((feature) => (
        <FeatureCard key={feature.id} {...feature} />
      ))}
    </div>
  );
};

// ============ 快捷操作区 ============

export const QuickActions: React.FC = () => {
  const actions = [
    { icon: '🎤', label: '新建会议', shortcut: 'Cmd+M' },
    { icon: '💬', label: '提问', shortcut: 'Cmd+Q' },
    { icon: '📝', label: '创建文档', shortcut: 'Cmd+N' },
    { icon: '📋', label: '创建任务', shortcut: 'Cmd+T' },
    { icon: '⚡', label: 'AI执行指令', shortcut: 'Cmd+E' },
  ];
  
  return (
    <Card padding="sm" className="mt-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">快捷操作</span>
        <span className="text-xs text-slate-500">支持快捷键</span>
      </div>
      <div className="flex gap-2 mt-3">
        {actions.map((action, index) => (
          <button
            key={index}
            className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors text-sm"
          >
            <span>{action.icon}</span>
            <span className="text-slate-200">{action.label}</span>
            <kbd className="text-xs text-slate-500 bg-slate-800 px-1 rounded">
              {action.shortcut}
            </kbd>
          </button>
        ))}
      </div>
    </Card>
  );
};

// ============ 最近活动 ============

interface RecentActivityItem {
  id: string;
  type: 'meeting' | 'qa' | 'document' | 'task' | 'agent';
  title: string;
  time: string;
  status?: 'completed' | 'in_progress' | 'pending';
}

interface RecentActivitiesProps {
  activities?: RecentActivityItem[];
}

export const RecentActivities: React.FC<RecentActivitiesProps> = ({
  activities,
}) => {
  const defaultActivities: RecentActivityItem[] = [
    { id: '1', type: 'meeting', title: '产品评审会', time: '10分钟前', status: 'completed' },
    { id: '2', type: 'qa', title: '如何设置AI执行权限？', time: '30分钟前', status: 'completed' },
    { id: '3', type: 'document', title: 'Q2产品规划PRD', time: '1小时前', status: 'in_progress' },
    { id: '4', type: 'task', title: '市场调研分析', time: '2小时前', status: 'pending' },
    { id: '5', type: 'agent', title: '自动创建任务并通知成员', time: '3小时前', status: 'completed' },
  ];
  
  const items = activities || defaultActivities;
  
  const typeIcons = {
    meeting: '📄',
    qa: '💬',
    document: '📝',
    task: '📊',
    agent: '⚡',
  };
  
  const statusColors = {
    completed: 'text-emerald-400',
    in_progress: 'text-amber-400',
    pending: 'text-slate-400',
  };
  
  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-100">最近活动</h3>
        <a href="#" className="text-sm text-indigo-400 hover:text-indigo-300">
          查看全部
        </a>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 p-2 hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer"
          >
            <span className="text-lg">{typeIcons[item.type]}</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-slate-200 truncate">{item.title}</div>
              <div className="text-xs text-slate-500">{item.time}</div>
            </div>
            {item.status && (
              <span className={`text-xs ${statusColors[item.status]}`}>
                {item.status === 'completed' && '✓'}
                {item.status === 'in_progress' && '⟳'}
                {item.status === 'pending' && '○'}
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
};