'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

export default function BusinessRegisterPage() {
  const router = useRouter();
  const { loginBusiness } = useUserAuth();

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
    if (form.password.length < 8) {
      setError('Mật khẩu tối thiểu 8 ký tự'); return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/business/register', {
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
      // Auto-login after register
      await loginBusiness(form.email.trim(), form.password);
      router.replace('/dashboard/business');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    background: '#0f1e35', border: '1px solid #1e3a5f',
  };
  const inputClass = "w-full px-4 py-3 rounded-xl text-sm text-white outline-none transition-all";

  return (
    <div className="w-full max-w-lg">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-green-600 mb-4">
          <span className="text-white font-bold text-2xl">A</span>
        </div>
        <h1 className="text-2xl font-bold text-white">Đăng ký doanh nghiệp</h1>
        <p className="text-slate-400 mt-1 text-sm">
          Bắt đầu hành trình chứng nhận Halal cho doanh nghiệp của bạn
        </p>
      </div>

      <div className="rounded-2xl p-8" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Company info */}
          <div>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">Tên công ty *</label>
            <input required value={form.company_name} onChange={set('company_name')}
              placeholder="Công ty TNHH ABC"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
              onBlur={e  => (e.target.style.borderColor = '#1e3a5f')} />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">
              Mã số thuế / Mã đăng ký kinh doanh
            </label>
            <input value={form.company_code} onChange={set('company_code')}
              placeholder="0123456789 (tuỳ chọn)"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
              onBlur={e  => (e.target.style.borderColor = '#1e3a5f')} />
          </div>

          <div style={{ borderTop: '1px solid #1e3a5f', paddingTop: '1rem', marginTop: '0.5rem' }}>
            <label className="block text-xs font-medium mb-1.5 text-slate-400">Email đăng nhập *</label>
            <input type="email" required value={form.email} onChange={set('email')}
              placeholder="email@congtycua.com"
              className={inputClass} style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#22c55e')}
              onBlur={e  => (e.target.style.borderColor = '#1e3a5f')} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1.5 text-slate-400">Mật khẩu *</label>
              <input type="password" required value={form.password} onChange={set('password')}
                placeholder="Tối thiểu 8 ký tự"
                className={inputClass} style={inputStyle}
                onFocus={e => (e.target.style.borderColor = '#22c55e')}
                onBlur={e  => (e.target.style.borderColor = '#1e3a5f')} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-slate-400">Xác nhận mật khẩu *</label>
              <input type="password" required value={form.confirm_password} onChange={set('confirm_password')}
                placeholder="Nhập lại mật khẩu"
                className={inputClass} style={inputStyle}
                onFocus={e => (e.target.style.borderColor = '#22c55e')}
                onBlur={e  => (e.target.style.borderColor = '#1e3a5f')} />
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
              background: loading ? '#1e3a5f' : '#16a34a',
              color: loading ? '#475569' : 'white',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang đăng ký...' : 'Đăng ký ngay'}
          </button>
        </form>

        <div className="mt-6 pt-5 text-center" style={{ borderTop: '1px solid #1e3a5f' }}>
          <p className="text-sm text-slate-400">
            Đã có tài khoản?{' '}
            <Link href="/business/login" className="text-green-400 font-medium hover:text-green-300 transition-colors">
              Đăng nhập
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
