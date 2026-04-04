'use client';

import { useState, useEffect } from 'react';
import { useAdminAuth } from './AdminAuthContext';

export default function AdminLoginModal({ onClose }: { onClose: () => void }) {
  const { login } = useAdminAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setLoading(true);
    setError('');
    try {
      await login(username.trim(), password);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}>
      <div className="w-full max-w-sm rounded-2xl p-6"
        style={{ background: '#111725', border: '1px solid #1e3a5f' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-white">Đăng nhập Admin</h2>
            <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>Quản lý template và tiêu chí đánh giá</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
            style={{ background: 'rgba(255,255,255,0.05)' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#94a3b8' }}>
              Tên đăng nhập
            </label>
            <input
              type="text" autoFocus autoComplete="username"
              value={username} onChange={e => setUsername(e.target.value)}
              placeholder="admin"
              className="w-full px-3 py-2.5 rounded-xl text-sm text-white outline-none transition-all"
              style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
              onBlur={e => (e.target.style.borderColor = '#1e3a5f')}
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#94a3b8' }}>
              Mật khẩu
            </label>
            <input
              type="password" autoComplete="current-password"
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2.5 rounded-xl text-sm text-white outline-none transition-all"
              style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
              onBlur={e => (e.target.style.borderColor = '#1e3a5f')}
            />
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
              {error}
            </p>
          )}

          <button type="submit" disabled={loading || !username || !password}
            className="w-full py-2.5 rounded-xl font-semibold text-sm transition-all"
            style={{
              background: loading || !username || !password ? '#1e3a5f' : '#16a34a',
              color: loading || !username || !password ? '#475569' : 'white',
              cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
            }}>
            {loading ? 'Đang xác thực…' : 'Đăng nhập'}
          </button>
        </form>
      </div>
    </div>
  );
}
