'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

type TokenStatus = 'verifying' | 'valid' | 'invalid';

export default function ResetPasswordPage() {
  const router = useRouter();
  const params = useSearchParams();
  const token  = params.get('token') ?? '';

  const [status, setStatus] = useState<TokenStatus>('verifying');
  const [email, setEmail]   = useState<string | null>(null);

  const [pw1, setPw1] = useState('');
  const [pw2, setPw2] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone]   = useState(false);
  const [error, setError] = useState('');

  // Verify token on mount
  useEffect(() => {
    if (!token) {
      setStatus('invalid');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/auth/verify-reset-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (!res.ok) {
          setStatus('invalid');
          return;
        }
        const data = await res.json();
        setStatus('valid');
        setEmail(data.email ?? null);
      } catch {
        if (!cancelled) setStatus('invalid');
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (pw1 !== pw2) {
      setError('Hai mật khẩu không khớp');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: pw1 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail ?? 'Đặt lại mật khẩu thất bại');
      }
      setDone(true);
      setTimeout(() => router.push('/business/login'), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi không xác định');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md" data-page>
      <div className="text-center mb-8 animate-section">
        <div className="inline-grid place-items-center w-16 h-16 rounded-2xl mb-4"
          style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 8px 24px rgba(15,81,50,0.12)' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aminra-mark.svg" alt="AMINRA" className="w-11 h-11" />
        </div>
        <h1 className="text-2xl font-bold" style={{ color: '#0F5132' }}>Đặt lại mật khẩu</h1>
        {email && (
          <p className="mt-1 text-sm" style={{ color: '#6B7280' }}>
            Tài khoản: <strong>{email}</strong>
          </p>
        )}
      </div>

      <div
        className="rounded-2xl p-8 animate-section"
        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}
      >
        {status === 'verifying' && (
          <p className="text-center text-sm" style={{ color: '#6B7280' }}>
            Đang xác thực liên kết...
          </p>
        )}

        {status === 'invalid' && (
          <div className="text-center space-y-4">
            <div className="inline-grid place-items-center w-12 h-12 rounded-full" style={{ background: 'rgba(239,68,68,0.1)' }}>
              <span style={{ color: '#ef4444', fontSize: 20 }}>!</span>
            </div>
            <p className="text-sm" style={{ color: '#0F5132' }}>
              Liên kết đặt lại không hợp lệ hoặc đã hết hạn (60 phút).
            </p>
            <Link
              href="/forgot-password"
              className="inline-block mt-2 text-sm font-medium py-2 -my-2 underline"
              style={{ color: '#0F5132' }}
            >
              Yêu cầu liên kết mới →
            </Link>
          </div>
        )}

        {status === 'valid' && done && (
          <div role="status" className="text-center space-y-4">
            <div className="inline-grid place-items-center w-12 h-12 rounded-full bg-[#E8F5EF]">
              <span className="text-[#0F5132] text-xl">✓</span>
            </div>
            <p className="text-sm" style={{ color: '#0F5132' }}>
              Mật khẩu đã được đặt lại thành công. Đang chuyển về đăng nhập...
            </p>
          </div>
        )}

        {status === 'valid' && !done && (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>
                Mật khẩu mới
              </label>
              <input
                type="password" required autoFocus minLength={10}
                value={pw1} onChange={e => setPw1(e.target.value)}
                placeholder="••••••••••"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }}
                onFocus={e => (e.target.style.borderColor = '#0F5132')}
                onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
              />
              <p className="text-xs mt-1.5" style={{ color: '#94A3B8' }}>
                Ít nhất 10 ký tự, có chữ hoa, chữ thường và số.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>
                Xác nhận mật khẩu mới
              </label>
              <input
                type="password" required
                value={pw2} onChange={e => setPw2(e.target.value)}
                placeholder="••••••••••"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }}
                onFocus={e => (e.target.style.borderColor = '#0F5132')}
                onBlur={e  => (e.target.style.borderColor = '#E2E8F0')}
              />
            </div>

            {error && (
              <p
                className="text-xs px-3 py-2 rounded-lg"
                style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting || !pw1 || !pw2}
              className="w-full py-3 rounded-xl font-semibold text-sm transition-all"
              style={{
                background: submitting || !pw1 || !pw2 ? '#E2E8F0' : '#0F5132',
                color: submitting || !pw1 || !pw2 ? '#6B7280' : 'white',
                cursor: submitting || !pw1 || !pw2 ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Đang đặt lại...' : 'Đặt lại mật khẩu'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
