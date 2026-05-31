import React, { useState } from 'react';
import { useAppStore } from '../../store/appStore';
import { Bot, GitBranch, LayoutDashboard, Activity, BarChart3, Settings, ChevronLeft, ChevronRight, Bell, HelpCircle, LogOut } from 'lucide-react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: '项目总览' },
  { path: '/workflows', icon: GitBranch, label: '工作流' },
  { path: '/agents', icon: Bot, label: 'Agents' },
  { path: '/activity', icon: Activity, label: '执行记录' },
  { path: '/dashboard', icon: BarChart3, label: '看板' },
  { path: '/settings', icon: Settings, label: '设置' },
];

export default function MainLayout() {
  const { sidebarCollapsed, toggleSidebar, currentUser, unreadCount, logout } = useAppStore();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="h-screen flex overflow-hidden bg-[var(--color-bg)]">
      {/* Sidebar */}
      <aside className={`flex-shrink-0 bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)] flex flex-col transition-all duration-200 ${sidebarCollapsed ? 'w-16' : 'w-60'}`}>
        {/* Logo */}
        <div className="h-14 flex items-center gap-3 px-4 border-b border-[var(--color-border)]">
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-xs">S</span>
          </div>
          {!sidebarCollapsed && <span className="font-semibold text-[var(--color-text-primary)]">SmartCollab</span>}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-500/10 text-indigo-400 border-l-[3px] border-indigo-500'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]'
                } ${sidebarCollapsed ? 'justify-center border-l-0' : ''}`}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="border-t border-[var(--color-border)] p-2 space-y-1">
          <button className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors ${sidebarCollapsed ? 'justify-center' : ''}`}>
            <HelpCircle className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && <span>帮助/反馈</span>}
          </button>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className="h-8 flex items-center justify-center border-t border-[var(--color-border)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] flex-shrink-0">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[var(--color-text-tertiary)]">SmartCollab</span>
            <span className="text-[var(--color-text-tertiary)]">/</span>
            <span className="text-[var(--color-text-primary)] font-medium">
              {navItems.find((i) => i.path === location.pathname)?.label || '页面'}
            </span>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors">
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center font-medium">
                  {unreadCount}
                </span>
              )}
            </button>
            <div className="flex items-center gap-2 pl-3 border-l border-[var(--color-border)]">
              <div className="w-7 h-7 bg-indigo-500 rounded-full flex items-center justify-center text-xs font-medium text-white">
                {currentUser?.name?.[0] || 'U'}
              </div>
              <span className="text-sm text-[var(--color-text-primary)] hidden sm:block">{currentUser?.name}</span>
            </div>
            <button onClick={logout} className="p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-red-400 transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}