'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

export default function BusinessLoginPage() {
  const router = useRouter();
  const { loginBusiness } = useUserAuth();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginBusiness(email.trim(), password);
      router.replace('/dashboard/business');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Logo */}
      <div className="text-center mb-8">
        <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-green-600 mb-4">
          <span className="text-white font-bold text-2xl">A</span>
        </div>
        <h1 className="text-2xl font-bold text-white">Chào mừng doanh nghiệp</h1>
        <p className="text-slate-400 mt-1 text-sm">
          Đăng nhập để bắt đầu hành trình chứng nhận Halal
        </p>
      </div>

      {/* Card */}
      <div className="rounded-2xl p-8" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">Email công ty</label>
            <input
              type="email" required autoFocus
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="cong ty@example.com"
              className="w-full px-4 py-3 rounded-xl text-sm text-white outline-none transition-all"
              style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
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
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
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
              background: loading || !email || !password ? '#1e3a5f' : '#16a34a',
              color: loading || !email || !password ? '#475569' : 'white',
              cursor: loading || !email || !password ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #1e3a5f' }}>
          <p className="text-sm text-slate-400">
            Chưa có tài khoản?{' '}
            <Link href="/business/register" className="text-green-400 font-medium hover:text-green-300 transition-colors">
              Đăng ký ngay
            </Link>
          </p>
        </div>
      </div>

      {/* Footer link */}
      <p className="text-center mt-6 text-xs text-slate-600">
        Là tổ chức cấp chứng nhận?{' '}
        <Link href="/provider/login" className="text-slate-400 hover:text-white transition-colors">
          Đăng nhập tại đây
        </Link>
      </p>
    </div>
  );
}
