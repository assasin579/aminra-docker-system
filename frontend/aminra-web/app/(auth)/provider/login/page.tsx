'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

export default function ProviderLoginPage() {
  const router = useRouter();
  const { loginProvider } = useUserAuth();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginProvider(email.trim(), password);
      router.replace('/dashboard/provider');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Header — institutional blue theme */}
      <div className="text-center mb-8">
        <div className="inline-grid place-items-center w-14 h-14 rounded-2xl mb-4"
          style={{ background: 'linear-gradient(135deg, #1d4ed8, #2563eb)' }}>
          <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white">Cổng dành cho tổ chức</h1>
        <p className="text-slate-400 mt-1 text-sm">
          Dành cho các tổ chức cấp chứng nhận Halal được công nhận
        </p>
      </div>

      <div className="rounded-2xl p-8" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
        {/* Trusted bodies badge */}
        <div className="grid items-center gap-2 mb-6 px-3 py-2 rounded-lg"
          style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
          <svg className="w-4 h-4" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs" style={{ color: '#93c5fd' }}>
            Tài khoản cần được AMINRA xét duyệt trước khi kích hoạt
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">Email tổ chức</label>
            <input
              type="email" required autoFocus
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="contact@jakim.gov.my"
              className="w-full px-4 py-3 rounded-xl text-sm text-white outline-none transition-all"
              style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}
              onFocus={e => (e.target.style.borderColor = '#3b82f6')}
              onBlur={e  => (e.target.style.borderColor = '#1e3a5f')}
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">Mật khẩu</label>
            <input
              type="password" required
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-3 rounded-xl text-sm text-white outline-none transition-all"
              style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}
              onFocus={e => (e.target.style.borderColor = '#3b82f6')}
              onBlur={e  => (e.target.style.borderColor = '#1e3a5f')}
            />
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
              {error}
            </p>
          )}

          <button
            type="submit" disabled={loading || !email || !password}
            className="w-full py-3 rounded-xl font-semibold text-sm transition-all"
            style={{
              background: loading || !email || !password ? '#1e3a5f' : 'linear-gradient(135deg, #1d4ed8, #2563eb)',
              color: loading || !email || !password ? '#475569' : 'white',
              cursor: loading || !email || !password ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #1e3a5f' }}>
          <p className="text-sm text-slate-400">
            Chưa đăng ký?{' '}
            <Link href="/provider/register" className="font-medium hover:opacity-80 transition-opacity" style={{ color: '#60a5fa' }}>
              Đăng ký tổ chức
            </Link>
          </p>
        </div>
      </div>

      <p className="text-center mt-6 text-xs text-slate-600">
        Là doanh nghiệp tìm chứng nhận?{' '}
        <Link href="/business/login" className="text-slate-400 hover:text-white transition-colors">
          Đăng nhập tại đây
        </Link>
      </p>
    </div>
  );
}
