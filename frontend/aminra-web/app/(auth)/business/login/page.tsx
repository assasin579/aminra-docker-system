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
  const [remember, setRemember] = useState(true);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginBusiness(email.trim(), password, remember);
      router.replace('/dashboard/business');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md" data-page>
      {/* Logo */}
      <div className="text-center mb-8 animate-section">
        <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-emerald-700 mb-4">
          <span className="text-white font-bold text-2xl">A</span>
        </div>
        <h1 className="text-2xl font-bold" style={{ color: '#1A2332' }}>Chào mừng doanh nghiệp</h1>
        <p className="mt-1 text-sm" style={{ color: '#5F6F80' }}>
          Đăng nhập để bắt đầu hành trình chứng nhận Halal
        </p>
      </div>

      {/* Card */}
      <div className="rounded-2xl p-8 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Email công ty</label>
            <input
              type="email" required autoFocus
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="cong ty@example.com"
              className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }}
              onFocus={e => (e.target.style.borderColor = '#087653')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Mật khẩu</label>
            <input
              type="password" required
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }}
              onFocus={e => (e.target.style.borderColor = '#087653')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500" />
            <span className="text-sm" style={{ color: '#6B7280' }}>Ghi nhớ đăng nhập</span>
          </label>

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
              background: loading || !email || !password ? '#E2E8F0' : '#087653',
              color: loading || !email || !password ? '#5B6B7D' : 'white',
              cursor: loading || !email || !password ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #E2E8F0' }}>
          <p className="text-sm" style={{ color: '#5F6F80' }}>
            Chưa có tài khoản?{' '}
            <Link href="/business/register" className="font-medium transition-colors" style={{ color: '#087653' }}>
              Đăng ký ngay
            </Link>
          </p>
        </div>
      </div>

      {/* Footer link */}
      <p className="text-center mt-6 text-xs" style={{ color: '#94A3B8' }}>
        Là tổ chức cấp chứng nhận?{' '}
        <Link href="/provider/login" className="transition-colors" style={{ color: '#5F6F80' }}>
          Đăng nhập tại đây
        </Link>
      </p>
    </div>
  );
}
