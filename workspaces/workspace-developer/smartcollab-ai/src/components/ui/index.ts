// 智协AI - UI 基础组件

import React from 'react';
import { Loader2, Check, X, AlertCircle, Info } from 'lucide-react';

// ============ Button 按钮 ============

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  leftIcon,
  rightIcon,
  className = '',
  children,
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variantStyles = {
    primary: 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500',
    secondary: 'bg-slate-700 hover:bg-slate-600 text-slate-100 focus:ring-slate-500',
    ghost: 'bg-transparent hover:bg-slate-800 text-slate-300 focus:ring-slate-500',
    danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500',
  };
  
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-6 py-3 text-base gap-2.5',
  };
  
  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {!loading && leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
      {children}
      {!loading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </button>
  );
};

// ============ Card 卡片 ============

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
}) => {
  const paddingStyles = {
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
  };
  
  return (
    <div className={`bg-slate-800 border border-slate-700 rounded-xl ${paddingStyles[padding]} ${className}`}>
      {children}
    </div>
  );
};

// ============ Badge 徽章 ============

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
}) => {
  const variantStyles = {
    default: 'bg-slate-700 text-slate-300',
    success: 'bg-emerald-900/50 text-emerald-400 border border-emerald-700/50',
    warning: 'bg-amber-900/50 text-amber-400 border border-amber-700/50',
    error: 'bg-red-900/50 text-red-400 border border-red-700/50',
    info: 'bg-blue-900/50 text-blue-400 border border-blue-700/50',
  };
  
  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };
  
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}>
      {children}
    </span>
  );
};

// ============ StatusIndicator 状态指示器 ============

interface StatusIndicatorProps {
  status: 'success' | 'running' | 'pending' | 'error' | 'idle';
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  size = 'md',
}) => {
  const statusConfig = {
    success: { color: 'bg-emerald-500', pulse: false, icon: Check },
    running: { color: 'bg-indigo-500', pulse: true, icon: Loader2 },
    pending: { color: 'bg-amber-500', pulse: false, icon: Info },
    error: { color: 'bg-red-500', pulse: false, icon: X },
    idle: { color: 'bg-slate-500', pulse: false, icon: null },
  };
  
  const config = statusConfig[status];
  const sizeClasses = size === 'sm' ? 'w-2 h-2' : 'w-3 h-3';
  
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex-shrink-0">
        {config.icon && <config.icon className={`${sizeClasses} ${config.color}`} />}
        {!config.icon && (
          <span className={`block rounded-full ${sizeClasses} ${config.color}`} />
        )}
        {config.pulse && (
          <span className={`absolute inset-0 rounded-full ${config.color} animate-ping opacity-75`} />
        )}
      </span>
      {label && <span className="text-sm text-slate-300">{label}</span>}
    </span>
  );
};

// ============ ProgressBar 进度条 ============

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  className?: string;
  color?: 'indigo' | 'emerald' | 'amber' | 'red';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  label,
  showValue = true,
  className = '',
  color = 'indigo',
}) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  const colorStyles = {
    indigo: 'bg-indigo-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };
  
  return (
    <div className={`w-full ${className}`}>
      {(label || showValue) && (
        <div className="flex justify-between items-center mb-1.5">
          {label && <span className="text-sm text-slate-400">{label}</span>}
          {showValue && <span className="text-sm font-medium text-slate-300">{Math.round(percentage)}%</span>}
        </div>
      )}
      <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full ${colorStyles[color]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

// ============ Skeleton 骨架屏 ============

interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  className?: string;
  width?: string | number;
  height?: string | number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'text',
  className = '',
  width,
  height,
}) => {
  const baseStyles = 'animate-pulse bg-slate-700 rounded';
  
  const variantStyles = {
    text: 'h-4 rounded',
    circular: 'rounded-full',
    rectangular: 'rounded',
  };
  
  const style = {
    width: width ? (typeof width === 'number' ? `${width}px` : width) : undefined,
    height: height ? (typeof height === 'number' ? `${height}px` : height) : undefined,
  };
  
  return (
    <div className={`${baseStyles} ${variantStyles[variant]} ${className}`} style={style} />
  );
};

// ============ Tooltip 提示 ============

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  children,
  position = 'top',
}) => {
  const positionStyles = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };
  
  return (
    <div className="group relative inline-block">
      {children}
      <div className={`absolute hidden group-hover:block z-50 px-2 py-1 text-xs text-white bg-slate-900 rounded shadow-lg ${positionStyles[position]} whitespace-nowrap`}>
        {content}
        <div className={`absolute w-2 h-2 bg-slate-900 transform rotate-45 ${
          position === 'top' ? 'bottom-[-4px] left-1/2 -translate-x-1/2' :
          position === 'bottom' ? 'top-[-4px] left-1/2 -translate-x-1/2' :
          position === 'left' ? 'right-[-4px] top-1/2 -translate-y-1/2' :
          'left-[-4px] top-1/2 -translate-y-1/2'
        }`} />
      </div>
    </div>
  );
};