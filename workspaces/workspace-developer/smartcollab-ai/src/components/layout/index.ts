// 智协AI - 布局组件

import React from 'react';
import { useAppStore } from '../../store/appStore';
import { Bell, Menu, User, Settings, LogOut, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../ui';

// ============ Header 顶部导航栏 ============

export const Header: React.FC = () => {
  const { toggleSidebar, notificationCount, currentUser } = useAppStore();
  
  return (
    <header className="h-16 bg-slate-800 border-b border-slate-700 flex items-center justify-between px-4 sticky top-0 z-40">
      {/* 左侧：Logo + 菜单按钮 */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSidebar}
          className="text-slate-400 hover:text-white"
        >
          <Menu className="w-5 h-5" />
        </Button>
        
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">智协</span>
          </div>
          <span className="font-semibold text-lg text-white hidden sm:block">
            智协AI
          </span>
        </div>
      </div>
      
      {/* 中间：全局搜索 */}
      <div className="flex-1 max-w-xl mx-4 hidden md:block">
        <div className="relative">
          <input
            type="text"
            placeholder="搜索任务、文档、知识库..."
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 bg-slate-600 px-1.5 py-0.5 rounded">
            ⌘K
          </kbd>
        </div>
      </div>
      
      {/* 右侧：用户操作 */}
      <div className="flex items-center gap-2">
        {/* 通知 */}
        <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-400 hover:text-white relative"
          >
            <Bell className="w-5 h-5" />
            {notificationCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
                {notificationCount}
              </span>
            )}
          </Button>
        </div>
        
        {/* 用户菜单 */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-700">
          <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-cyan-500 rounded-full flex items-center justify-center">
            {currentUser?.avatar ? (
              <img src={currentUser.avatar} alt={currentUser.name} className="w-8 h-8 rounded-full" />
            ) : (
              <User className="w-4 h-4 text-white" />
            )}
          </div>
          <div className="hidden lg:block text-sm">
            <div className="text-slate-200 font-medium">{currentUser?.name || '用户'}</div>
            <div className="text-slate-500 text-xs">{currentUser?.role || 'member'}</div>
          </div>
        </div>
        
        {/* 设置 */}
        <Button variant="ghost" size="sm" className="text-slate-400 hover:text-white">
          <Settings className="w-5 h-5" />
        </Button>
      </div>
    </header>
  );
};

// ============ Sidebar 侧边栏 ============

interface SidebarProps {
  collapsed?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed }) => {
  const { sidebarCollapsed } = useAppStore();
  
  const navItems = [
    { icon: '📊', label: '工作台', active: true },
    { icon: '📋', label: '任务列表', count: 12 },
    { icon: '🎤', label: '会议助手', badge: 'live' },
    { icon: '💬', label: '智能问答', count: 5 },
    { icon: '📝', label: '文档中心', count: 23 },
    { icon: '⚡', label: 'AI执行', active: true },
    { icon: '📈', label: '数据分析' },
    { icon: '⚙️', label: '系统设置' },
  ];
  
  return (
    <aside className={`bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-300 ${
      sidebarCollapsed ? 'w-16' : 'w-64'
    }`}>
      {/* 导航菜单 */}
      <nav className="flex-1 py-4 px-2">
        <div className="space-y-1">
          {navItems.map((item, index) => (
            <a
              key={index}
              href="#"
              className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                item.active
                  ? 'bg-indigo-900/50 text-indigo-400'
                  : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
              } ${sidebarCollapsed ? 'justify-center' : ''}`}
            >
              <span className="text-lg">{item.icon}</span>
              {!sidebarCollapsed && (
                <>
                  <span className="flex-1 text-sm font-medium">{item.label}</span>
                  {item.count && (
                    <span className="text-xs bg-slate-700 px-1.5 py-0.5 rounded">
                      {item.count}
                    </span>
                  )}
                  {item.badge === 'live' && (
                    <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                  )}
                </>
              )}
            </a>
          ))}
        </div>
      </nav>
      
      {/* 底部：AI用量 */}
      {!sidebarCollapsed && (
        <div className="p-4 border-t border-slate-700">
          <div className="text-xs text-slate-500 mb-2">AI用量</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 w-1/4" />
            </div>
            <span className="text-xs text-slate-400">12/500</span>
          </div>
        </div>
      )}
    </aside>
  );
};

// ============ MainLayout 主布局 ============

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-slate-900 flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};