'use client';

import { useState } from 'react';
import Link from 'next/link';

type Step = 'form' | 'success';

export default function ProviderRegisterPage() {
  const [step, setStep]       = useState<Step>('form');
  const [pendingEmail, setPendingEmail] = useState('');
  const [form, setForm] = useState({
    email: '', password: '', confirm_password: '',
    company_name: '', company_code: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm_password) {
      setError('Mật khẩu xác nhận không khớp'); return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/provider/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email.trim(),
          password: form.password,
          company_name: form.company_name.trim(),
          company_code: form.company_code.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Đăng ký thất bại');
      }
      setPendingEmail(form.email.trim());
      setStep('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  if (step === 'success') {
    return (
      <div className="w-full max-w-md text-center" data-page>
        <div className="rounded-2xl p-10 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
          <div className="w-16 h-16 rounded-full grid place-items-center mx-auto mb-5"
            style={{ background: 'rgba(8,118,83,0.1)', border: '1px solid rgba(8,118,83,0.25)' }}>
            <svg className="w-8 h-8" style={{ color: '#087653' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold mb-3" style={{ color: '#1A2332' }}>Đăng ký thành công!</h2>
          <p className="text-sm mb-2" style={{ color: '#5F6F80' }}>
            Tài khoản <strong style={{ color: '#1A2332' }}>{pendingEmail}</strong> đang chờ xét duyệt.
          </p>
          <p className="text-sm" style={{ color: '#5B6B7D' }}>
            Đội ngũ AMINRA sẽ xem xét hồ sơ của tổ chức bạn. Sau khi được phê duyệt, bạn có thể đăng nhập.
          </p>
          <Link href="/provider/login"
            className="inline-block mt-6 px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:opacity-90"
            style={{ background: '#087653' }}>
            Về trang đăng nhập
          </Link>
        </div>
      </div>
    );
  }

  const inputStyle = { background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' };
  const inputClass = "w-full px-4 py-3 rounded-xl text-sm outline-none transition-all";

  return (
    <div className="w-full max-w-lg" data-page>
      <div className="text-center mb-8 animate-section">
        <div className="inline-grid place-items-center w-14 h-14 rounded-2xl mb-4"
          style={{ background: '#64748b' }}>
          <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold" style={{ color: '#1A2332' }}>Đăng ký tổ chức</h1>
        <p className="mt-1 text-sm" style={{ color: '#5F6F80' }}>
          Dành cho JAKIM, HDC, MUI và các tổ chức chứng nhận Halal
        </p>
      </div>

      <div className="rounded-2xl p-8 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Tên tổ chức *</label>
            <input required value={form.company_name} onChange={set('company_name')}
              placeholder="VD: JAKIM, HDC, MUI Vietnam"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#087653')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')} />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>
              Mã công nhận / Số giấy phép
            </label>
            <input value={form.company_code} onChange={set('company_code')}
              placeholder="Số giấy phép hoạt động (tuỳ chọn)"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#087653')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')} />
          </div>

          <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '1rem' }}>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Email đại diện *</label>
            <input type="email" required value={form.email} onChange={set('email')}
              placeholder="official@organization.org"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#087653')}
              onBlur={e  => (e.target.style.borderColor = '#E2E8F0')} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Mật khẩu *</label>
              <input type="password" required value={form.password} onChange={set('password')}
                placeholder="Tối thiểu 8 ký tự"
                className={inputClass} style={inputStyle}
                onFocus={e => (e.target.style.borderColor = '#087653')}
                onBlur={e  => (e.target.style.borderColor = '#E2E8F0')} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Xác nhận *</label>
              <input type="password" required value={form.confirm_password} onChange={set('confirm_password')}
                placeholder="Nhập lại"
                className={inputClass} style={inputStyle}
                onFocus={e => (e.target.style.borderColor = '#087653')}
                onBlur={e  => (e.target.style.borderColor = '#E2E8F0')} />
            </div>
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
              {error}
            </p>
          )}

          <button
            type="submit" disabled={loading}
            className="w-full py-3 rounded-xl font-semibold text-sm transition-all mt-2"
            style={{
              background: loading ? '#E2E8F0' : '#087653',
              color: loading ? '#5B6B7D' : 'white',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang gửi hồ sơ...' : 'Nộp hồ sơ đăng ký'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #E2E8F0' }}>
          <p className="text-sm" style={{ color: '#5F6F80' }}>
            Đã đăng ký?{' '}
            <Link href="/provider/login" className="font-medium hover:opacity-80 transition-opacity" style={{ color: '#087653' }}>
              Đăng nhập
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
