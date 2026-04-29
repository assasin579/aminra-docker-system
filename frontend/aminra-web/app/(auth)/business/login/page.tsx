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
        <div className="inline-grid place-items-center w-16 h-16 rounded-2xl mb-4"
          style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 8px 24px rgba(10,31,68,0.12)' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aminra-mark.png" alt="" className="w-11 h-11 object-contain" />
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/aminra-wordmark-navy.png" alt="AMINRA" className="h-7 mx-auto object-contain" />
        <p className="mt-3 text-sm" style={{ color: '#6B7280' }}>
          Đăng nhập doanh nghiệp để bắt đầu hành trình chứng nhận Halal
        </p>
      </div>

      {/* Card */}
      <div className="rounded-2xl p-8 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Email công ty</label>
            <input
              type="email" required autoFocus
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="cong ty@example.com"
              className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0A1F44' }}
              onFocus={e => (e.target.style.borderColor = '#0A1F44')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Mật khẩu</label>
            <input
              type="password" required
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0A1F44' }}
              onFocus={e => (e.target.style.borderColor = '#0A1F44')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer select-none min-h-[32px]">
              <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}
                className="w-5 h-5 rounded border-gray-300 text-[#0A1F44] focus:ring-[#0A1F44]" />
              <span className="text-sm" style={{ color: '#6B7280' }}>Ghi nhớ đăng nhập</span>
            </label>
            <Link href="/forgot-password" className="text-sm font-medium" style={{ color: '#0A1F44' }}>
              Quên mật khẩu?
            </Link>
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
              {error}
            </p>
          )}

          <button
            type="submit" disabled={loading || !email || !password}
            className="btn-lift w-full py-3 rounded-xl font-semibold text-sm"
            style={{
              background: loading || !email || !password ? '#E2E8F0' : '#0A1F44',
              color: loading || !email || !password ? '#6B7280' : 'white',
              cursor: loading || !email || !password ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #E2E8F0' }}>
          <p className="text-sm" style={{ color: '#6B7280' }}>
            Chưa có tài khoản?{' '}
            <Link href="/business/register" className="inline-flex items-center min-h-[32px] font-medium transition-colors" style={{ color: '#0A1F44' }}>
              Đăng ký ngay
            </Link>
          </p>
        </div>
      </div>

      {/* Footer link */}
      <p className="text-center mt-6 text-xs" style={{ color: '#94A3B8' }}>
        Là tổ chức cấp chứng nhận?{' '}
        <Link href="/provider/login" className="inline-flex items-center min-h-[32px] transition-colors" style={{ color: '#6B7280' }}>
          Đăng nhập tại đây
        </Link>
      </p>
    </div>
  );
}
