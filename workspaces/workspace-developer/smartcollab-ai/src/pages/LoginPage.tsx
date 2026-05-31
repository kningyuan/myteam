import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { Mail, Lock, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAppStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((r) => setTimeout(r, 800));
    login({ id: 'user-1', name: '张工', email, role: 'admin' });
    navigate('/');
  };

  return (
    <div className="min-h-screen flex bg-[var(--color-bg)]">
      {/* Left: Form */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-sm">S</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-[var(--color-text-primary)]">SmartCollab</h1>
              <p className="text-sm text-[var(--color-text-secondary)]">AI 团队协作编排平台</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] mb-1">欢迎回来</h2>
          <p className="text-[var(--color-text-secondary)] text-sm mb-8">登录你的工作空间</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1.5">邮箱</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com" required
                  className="w-full h-11 pl-10 pr-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1.5">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
                <input type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="输入密码" required
                  className="w-full h-11 pl-10 pr-10 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all" />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" defaultChecked className="w-4 h-4 rounded border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-indigo-500 focus:ring-indigo-500" />
                <span className="text-[var(--color-text-secondary)]">记住我</span>
              </label>
              <button type="button" className="text-indigo-400 hover:text-indigo-300 hover:underline">忘记密码？</button>
            </div>

            <button type="submit" disabled={loading}
              className="w-full h-11 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center justify-center">
              {loading ? <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : '登录'}
            </button>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[var(--color-border)]" /></div>
              <div className="relative flex justify-center text-xs"><span className="px-3 bg-[var(--color-bg)] text-[var(--color-text-tertiary)]">或</span></div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="h-10 flex items-center justify-center gap-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                GitHub
              </button>
              <button type="button" className="h-10 flex items-center justify-center gap-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
                <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Google
              </button>
            </div>

            <p className="text-center text-sm text-[var(--color-text-secondary)]">
              还没有账号？<button type="button" className="text-indigo-400 hover:text-indigo-300 font-medium">注册</button>
            </p>
          </form>
        </div>
      </div>

      {/* Right: Decorative DAG animation */}
      <div className="hidden lg:flex flex-1 bg-[var(--color-bg-secondary)] items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 dag-grid-bg opacity-30" />
        <div className="relative w-96 h-96">
          <div className="absolute top-8 left-1/2 -translate-x-1/2 w-20 h-20 bg-indigo-500/20 border-2 border-indigo-500 rounded-xl animate-float-node flex items-center justify-center">
            <span className="text-indigo-400 text-2xl">🤖</span>
          </div>
          <svg className="absolute top-28 left-1/2 -translate-x-1/2 w-32" viewBox="0 0 128 20">
            <line x1="10" y1="10" x2="118" y2="10" stroke="#6366F1" strokeWidth="2" strokeDasharray="6 4" className="animate-dash-flow" />
            <polygon points="118,5 128,10 118,15" fill="#6366F1" />
          </svg>
          <div className="absolute top-40 left-12 w-16 h-16 bg-emerald-500/20 border-2 border-emerald-500 rounded-xl animate-float-node-delayed flex items-center justify-center">
            <span className="text-emerald-400 text-xl">⚡</span>
          </div>
          <div className="absolute top-40 right-12 w-16 h-16 bg-amber-500/20 border-2 border-amber-500 rounded-xl animate-float-node flex items-center justify-center">
            <span className="text-amber-400 text-xl">📋</span>
          </div>
          <svg className="absolute top-56 left-1/2 -translate-x-1/2 w-48" viewBox="0 0 192 20">
            <line x1="10" y1="10" x2="182" y2="10" stroke="#6366F1" strokeWidth="2" strokeDasharray="6 4" className="animate-dash-flow" />
            <polygon points="182,5 192,10 182,15" fill="#6366F1" />
          </svg>
          <div className="absolute top-64 left-1/2 -translate-x-1/2 w-24 h-24 bg-purple-500/20 border-2 border-purple-500 rounded-xl animate-float-node-delayed flex items-center justify-center">
            <span className="text-purple-400 text-3xl">🎯</span>
          </div>
        </div>
      </div>
    </div>
  );
}