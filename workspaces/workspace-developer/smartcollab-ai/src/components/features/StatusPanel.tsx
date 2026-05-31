// 智协AI - 状态面板（右侧边栏）

import React, { useState } from 'react';
import { useAppStore } from '../../store/appStore';
import { Card, Badge, ProgressBar, StatusIndicator, Button } from '../ui';
import { 
  CheckCircle2, Clock, Play, Pause, Square, 
  Users, Zap, MessageSquare, FileCheck,
  ChevronDown, ChevronUp, MoreVertical
} from 'lucide-react';

// ============ 系统概览卡片 ============

export const SystemOverview: React.FC = () => {
  const { systemStatus } = useAppStore();
  
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-100">📊 系统概览</h3>
        <StatusIndicator 
          status={systemStatus.healthy ? 'success' : 'error'} 
          size="sm"
        />
      </div>
      
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center p-3 bg-slate-700/50 rounded-lg">
          <div className="text-2xl font-bold text-emerald-400">
            {systemStatus.onlineUsers}
          </div>
          <div className="text-xs text-slate-400 mt-1">在线用户</div>
        </div>
        
        <div className="text-center p-3 bg-slate-700/50 rounded-lg">
          <div className="text-2xl font-bold text-indigo-400">
            {systemStatus.totalTasks}
          </div>
          <div className="text-xs text-slate-400 mt-1">总任务数</div>
        </div>
        
        <div className="text-center p-3 bg-slate-700/50 rounded-lg">
          <div className="text-2xl font-bold text-amber-400">
            {systemStatus.completedTasks}
          </div>
          <div className="text-xs text-slate-400 mt-1">已完成</div>
        </div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className={`w-4 h-4 ${systemStatus.aiRunning ? 'text-indigo-400' : 'text-slate-500'}`} />
          <span className="text-sm text-slate-300">
            {systemStatus.aiRunning ? 'AI 运行中' : 'AI 空闲'}
          </span>
        </div>
        <Badge variant={systemStatus.aiRunning ? 'info' : 'default'} size="sm">
          {systemStatus.aiRunning ? '活跃' : '待机'}
        </Badge>
      </div>
    </Card>
  );
};

// ============ 会议状态卡片 ============

interface MeetingStatusCardProps {
  meeting?: {
    id: string;
    title: string;
    status: 'idle' | 'recording' | 'transcribing' | 'summarizing' | 'ended';
    startTime: string;
    duration?: number;
    currentSpeaker?: string;
    transcription?: string;
  };
}

export const MeetingStatusCard: React.FC<MeetingStatusCardProps> = ({ meeting }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!meeting) {
    return (
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-100">🎤 会议状态</h3>
          <Button variant="ghost" size="sm" className="text-indigo-400">
            <Play className="w-4 h-4 mr-1" />
            开始会议
          </Button>
        </div>
        <div className="text-center py-8 text-slate-500">
          <Mic className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">暂无进行中的会议</p>
        </div>
      </Card>
    );
  }
  
  const statusConfig = {
    recording: { label: '录制中', color: 'text-red-400', icon: '🔴' },
    transcribing: { label: '转写中', color: 'text-indigo-400', icon: '⟳' },
    summarizing: { label: '生成摘要', color: 'text-amber-400', icon: '⚡' },
    ended: { label: '已结束', color: 'text-slate-400', icon: '✓' },
    idle: { label: '空闲', color: 'text-slate-400', icon: '○' },
  };
  
  const config = statusConfig[meeting.status];
  
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-100">🎤 会议状态</h3>
        <Badge variant={meeting.status === 'recording' ? 'error' : 'default'} size="sm">
          {config.label}
        </Badge>
      </div>
      
      <div>
        <h4 className="font-medium text-slate-200">{meeting.title}</h4>
        <p className="text-sm text-slate-400 mt-1">
          {meeting.startTime} 
          {meeting.duration && ` (进行中 ${meeting.duration}min)`}
        </p>
      </div>
      
      {meeting.status === 'recording' && (
        <div className="mt-4 p-3 bg-slate-700/50 rounded-lg">
          <div className="flex items-center gap-2 text-sm text-red-400 animate-pulse">
            <div className="w-2 h-2 bg-red-500 rounded-full" />
            <span>🎤 实时转写中...</span>
          </div>
          {meeting.currentSpeaker && (
            <p className="text-sm text-slate-300 mt-2">
              当前发言: {meeting.currentSpeaker}
            </p>
          )}
        </div>
      )}
      
      {/* 展开详情 */}
      {expanded && meeting.transcription && (
        <div className="mt-3 p-3 bg-slate-700/30 rounded-lg max-h-40 overflow-y-auto">
          <p className="text-sm text-slate-300">{meeting.transcription}</p>
        </div>
      )}
      
      <div className="mt-4 flex items-center gap-2">
        <Button variant="secondary" size="sm">
          <FileCheck className="w-4 h-4 mr-1" />
          查看纪要
        </Button>
        {meeting.status !== 'ended' && (
          <Button variant="danger" size="sm">
            <Square className="w-4 h-4 mr-1" />
            结束会议
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </Button>
      </div>
    </Card>
  );
};

// ============ AI执行状态卡片 ============

interface AIExecutionCardProps {
  task?: {
    id: string;
    name: string;
    progress: number;
    currentStep?: string;
    totalSteps?: number;
    estimatedTime?: string;
    status: 'idle' | 'running' | 'paused' | 'completed' | 'failed';
  };
}

export const AIExecutionCard: React.FC<AIExecutionCardProps> = ({ task }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!task) {
    return (
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-100">⚡ AI执行状态</h3>
          <Button variant="ghost" size="sm" className="text-indigo-400">
            新建执行
          </Button>
        </div>
        <div className="text-center py-8 text-slate-500">
          <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">暂无进行中的 AI 执行任务</p>
        </div>
      </Card>
    );
  }
  
  const statusConfig = {
    running: { label: '执行中', color: 'text-indigo-400', variant: 'info' as const },
    paused: { label: '已暂停', color: 'text-amber-400', variant: 'warning' as const },
    completed: { label: '已完成', color: 'text-emerald-400', variant: 'success' as const },
    failed: { label: '失败', color: 'text-red-400', variant: 'error' as const },
    idle: { label: '空闲', color: 'text-slate-400', variant: 'default' as const },
  };
  
  const config = statusConfig[task.status];
  
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-100">⚡ AI执行状态</h3>
        <Badge variant={config.variant} size="sm">{config.label}</Badge>
      </div>
      
      <div>
        <h4 className="font-medium text-slate-200">{task.name}</h4>
        <p className="text-sm text-slate-400 mt-1">
          {task.currentStep || '执行中...'}
        </p>
      </div>
      
      <div className="mt-4">
        <ProgressBar
          value={task.progress}
          label="执行进度"
          color={task.status === 'failed' ? 'red' : 'indigo'}
        />
        
        {task.totalSteps && (
          <p className="text-xs text-slate-500 mt-1">
            {task.currentStep ? `${task.currentStep} · ` : ''}
            步骤 {Math.round(task.progress / (100 / task.totalSteps))}/{task.totalSteps}
            {task.estimatedTime && ` · 预计 ${task.estimatedTime}`}
          </p>
        )}
      </div>
      
      {/* 展开步骤详情 */}
      {expanded && task.totalSteps && (
        <div className="mt-3 space-y-2">
          {[...Array(task.totalSteps)].map((_, i) => {
            const stepProgress = (i + 1) * (100 / task.totalSteps);
            const stepStatus = 
              stepProgress < task.progress ? 'completed' :
              stepProgress === task.progress ? 'running' : 'pending';
            
            return (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  stepStatus === 'completed' ? 'bg-emerald-900/50 text-emerald-400' :
                  stepStatus === 'running' ? 'bg-indigo-900/50 text-indigo-400 animate-pulse-ai' :
                  'bg-slate-700 text-slate-500'
                }`}>
                  {stepStatus === 'completed' ? '✓' : stepStatus === 'running' ? '⟳' : i + 1}
                </span>
                <span className={stepStatus === 'pending' ? 'text-slate-500' : 'text-slate-300'}>
                  步骤 {i + 1}
                </span>
              </div>
            );
          })}
        </div>
      )}
      
      <div className="mt-4 flex items-center gap-2">
        {task.status === 'running' && (
          <>
            <Button variant="warning" size="sm">
              <Pause className="w-4 h-4 mr-1" />
              暂停
            </Button>
            <Button variant="danger" size="sm">
              取消
            </Button>
          </>
        )}
        <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
          {expanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </Button>
      </div>
    </Card>
  );
};

// ============ 待办事项卡片 ============

export const ActionItemsCard: React.FC = () => {
  const { actionItems } = useAppStore();
  
  const items = actionItems.length > 0 ? actionItems : [
    { id: '1', content: '完成产品PRD评审', assignee: '张三', status: 'pending' as const, dueDate: '今天' },
    { id: '2', content: '回复客户邮件', assignee: '李四', status: 'completed' as const, dueDate: '昨天' },
    { id: '3', content: '更新项目进度', assignee: '王五', status: 'pending' as const, dueDate: '明天' },
  ];
  
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-100">📝 待办事项</h3>
        <Button variant="ghost" size="sm" className="text-indigo-400">
          查看全部
        </Button>
      </div>
      
      <div className="space-y-2">
        {items.slice(0, 3).map((item) => (
          <div
            key={item.id}
            className="flex items-start gap-3 p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <button className="flex-shrink-0 mt-0.5">
              {item.status === 'completed' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <div className="w-4 h-4 rounded border-2 border-slate-500" />
              )}
            </button>
            <div className="flex-1 min-w-0">
              <p className={`text-sm ${item.status === 'completed' ? 'text-slate-500 line-through' : 'text-slate-200'}`}>
                {item.content}
              </p>
              <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                {item.assignee && <span>👤 {item.assignee}</span>}
                {item.dueDate && <span>📅 {item.dueDate}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

// ============ 完整状态面板 ============

export const StatusPanel: React.FC = () => {
  return (
    <div className="space-y-4">
      <SystemOverview />
      <MeetingStatusCard />
      <AIExecutionCard />
      <ActionItemsCard />
    </div>
  );
};

// 导入图标
import { Mic } from 'lucide-react';